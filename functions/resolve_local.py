"""Attach local IDs to source facts; never retrieve replacement fact values."""
# Allow both `python functions/module.py` and `python -m functions.module`.
import sys
from pathlib import Path
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
import re
import httpx
from rdflib import Literal
from local_rdf import SPARQL_ENDPOINT
from functions.progress import configure_progress, report
from functions.pydantic_models import (
    Extraction, PROPERTY_FIELDS, QuantityClaim, validate_evidence, validate_mapped_property,
)
from functions.resolved_models import (
    Candidate, ResolvedClaim, ResolvedProperty, ResolvedKeyboard, ResolvedExtraction,
)

BASE = "https://keyboards.wikibase.cloud/entity/"


def search_local(label: str, kind: str) -> list[dict]:
    """Return exact label/alias candidates, not a guessed best match.

    Searches local English, Danish, and untagged labels case-insensitively.
    Raises httpx.HTTPError when QLever cannot answer the query.
    """
    if kind not in ("item", "property"):
        raise ValueError("kind must be item or property")
    prefix = "Q" if kind == "item" else "P"
    query = f"""
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX wikibase: <http://wikiba.se/ontology#>
SELECT DISTINCT ?entity ?type WHERE {{
 ?entity (rdfs:label|skos:altLabel) ?label .
 FILTER(STRSTARTS(STR(?entity), "{BASE}{prefix}"))
 FILTER(LANG(?label) IN ("en", "da", ""))
 FILTER(LCASE(STR(?label)) = LCASE({Literal(label.strip()).n3()}))
 OPTIONAL {{ ?entity wikibase:propertyType ?type }}
}} ORDER BY ?entity
"""
    response = httpx.post(SPARQL_ENDPOINT, data={"query": query},
                         headers={"Accept": "application/sparql-results+json"}, timeout=20)
    response.raise_for_status()
    matches = {}
    for row in response.json()["results"]["bindings"]:
        identifier = row["entity"]["value"].removeprefix(BASE)
        if re.fullmatch(prefix + r"\d+", identifier):
            matches[identifier] = {"id": identifier, "type": row.get("type", {}).get("value")}
    return list(matches.values())


def resolve_extraction(extraction: Extraction, source: str) -> ResolvedExtraction:
    """Resolve the grouped model directly, never passing through flat triples.

    Validate evidence and catalog mappings before lookup. Query each keyboard
    name once, and cache successful name searches within this run. Preserve all
    repeated/conflicting claims and candidate IDs; ambiguity is not guessed away.
    Network failures are recorded at the subject or individual value level so a
    failed value lookup does not discard a known subject QID or mapped PID.
    """
    validate_evidence(extraction, source)
    definitions = {field: validate_mapped_property(pid, label)
                   for field, (pid, label) in PROPERTY_FIELDS.items()}
    result = ResolvedExtraction()
    cache = {}

    def lookup(name, context):
        report(f"Looking up {context} ID")
        try:
            if name not in cache:
                cache[name] = [Candidate.model_validate(c) for c in search_local(name, "item")]
            candidates = cache[name]
        except (httpx.HTTPError, ValueError) as error:
            return None, [], [f"{context}: local lookup failed: {error}"]
        report(f"{context.capitalize()} lookup: {len(candidates)} candidate(s)")
        if len(candidates) == 1:
            return candidates[0].id, candidates, []
        warning = (f"{context}: no local match" if not candidates else
                   f"{context}: ambiguous matches: {', '.join(c.id for c in candidates)}")
        return None, candidates, [warning]

    for index, keyboard in enumerate(extraction.entities, 1):
        report(f"Linking keyboard {index}/{len(extraction.entities)}")
        qid, candidates, warnings = lookup(keyboard.name, "subject")
        resolved = ResolvedKeyboard(name=keyboard.name, subject_id=qid,
                                    subject_candidates=candidates, warnings=warnings)
        for field, (pid, label) in PROPERTY_FIELDS.items():
            definition = definitions[field]
            prop = ResolvedProperty(property_id=pid, label=label,
                                    value_type=definition["wikibase_value_type"])
            # Empty properties remain explicit; no claims or units are invented.
            for claim in getattr(keyboard, field):
                item = ResolvedClaim(value=claim.value, evidence=claim.evidence,
                                     unit=claim.unit if isinstance(claim, QuantityClaim) else None)
                if prop.value_type == "WikibaseItem":
                    item.value_id, item.value_candidates, item.warnings = lookup(str(claim.value), "value")
                prop.claims.append(item)
            resolved.properties[field] = prop
        result.entities.append(resolved)
    return result


def extract_ids(fact: dict) -> dict:
    """Legacy flat-record helper; the handler uses resolve_extraction instead.

    Input has subject/property/value strings plus unit and evidence. A supplied
    property_id is validated against our model/catalog and skips property search.
    Legacy facts without a PID retain label lookup; entity resolution is unchanged. Output keeps
    every source field and adds subject_id, property_id, value_id, knowledge_base,
    and warnings. Only entity-valued properties trigger value-name resolution.
    Missing or ambiguous candidates stay unresolved; HTTP errors propagate for
    the handler to report. Existing database fact values are never retrieved.
    """
    result = {**fact, "subject_id": None, "property_id": None, "value_id": None,
              "knowledge_base": "https://keyboards.wikibase.cloud", "warnings": []}

    def resolve(field, kind):
        report(f"Looking up {field} ID")
        matches = search_local(fact[field], kind)
        report(f"{field.capitalize()} lookup: {len(matches)} candidate(s)")
        if len(matches) == 1:
            result[field + "_id"] = matches[0]["id"]
            return matches[0]
        result["warnings"].append(
            f"{field}: no local match" if not matches else
            f"{field}: ambiguous matches: {', '.join(m['id'] for m in matches)}")
        return None

    if "property_id" in fact:
        prop = validate_mapped_property(fact["property_id"], fact["property"])
        result["property_id"] = prop["property_id"]
        prop = {"type": prop["wikibase_value_type_uri"]}
        report(f"Using mapped property ID: {result['property_id']}")
    else:
        prop = None
    resolve("subject", "item")
    if "property_id" not in fact:
        prop = resolve("property", "property")
    if prop and prop["type"] == "http://wikiba.se/ontology#WikibaseItem":
        resolve("value", "item")
    return result


def main():
    """Resolve grouped extraction from a JSON file, or a built-in source sample.

    --fact-json remains available for older flat records; it is not the main path.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fact-json", help="JSON object with subject, property, value, unit and evidence")
    parser.add_argument("--extraction-file", type=Path, help="Grouped Extraction JSON")
    parser.add_argument("--source-file", type=Path, help="Original text for evidence validation")
    parser.add_argument("--quiet", action="store_true", help="Hide progress messages")
    args = parser.parse_args()
    configure_progress(quiet=args.quiet)
    if args.fact_json and (args.extraction_file or args.source_file):
        parser.error("Use --fact-json or the grouped file options, not both")
    if bool(args.extraction_file) != bool(args.source_file):
        parser.error("--extraction-file and --source-file must be supplied together")
    try:
        if args.fact_json:
            output = extract_ids(json.loads(args.fact_json))
        else:
            source = (args.source_file.read_text() if args.source_file else
                      "The Yamaha P-150 has a width of 999 cm.")
            extraction = (Extraction.model_validate_json(args.extraction_file.read_text())
                          if args.extraction_file else Extraction.model_validate({"entities": [{
                              "name": "Yamaha P-150", "width": [
                                  {"value": "999", "unit": "cm", "evidence": source}]}]}))
            output = resolve_extraction(extraction, source).model_dump(mode="json")
        print(json.dumps(output, indent=2, ensure_ascii=False))
    except (httpx.HTTPError, ValueError) as error:
        raise SystemExit(f"Local resolution failed: {error}") from error


if __name__ == "__main__":
    main()
