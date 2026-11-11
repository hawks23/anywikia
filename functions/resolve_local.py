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


def extract_ids(fact: dict) -> dict:
    """Attach unique local IDs to a fact without mutating the input dictionary.

    Input has subject/property/value strings plus unit and evidence. Output keeps
    every source field and adds subject_id, property_id, value_id, knowledge_base,
    and warnings. Only entity-valued properties trigger value-name resolution.
    Missing or ambiguous candidates stay unresolved; HTTP errors propagate for
    the handler to report. Existing database fact values are never retrieved.
    """
    result = {**fact, "subject_id": None, "property_id": None, "value_id": None,
              "knowledge_base": "https://keyboards.wikibase.cloud", "warnings": []}

    def resolve(field, kind):
        matches = search_local(fact[field], kind)
        if len(matches) == 1:
            result[field + "_id"] = matches[0]["id"]
            return matches[0]
        result["warnings"].append(
            f"{field}: no local match" if not matches else
            f"{field}: ambiguous matches: {', '.join(m['id'] for m in matches)}")
        return None

    resolve("subject", "item")
    prop = resolve("property", "property")
    if prop and prop["type"] == "http://wikiba.se/ontology#WikibaseItem":
        resolve("value", "item")
    return result


def main():
    """Link a source fact without calling CampusAI; read a JSON fact or use a sample."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fact-json", help="JSON object with subject, property, value, unit and evidence")
    args = parser.parse_args()
    fact = json.loads(args.fact_json) if args.fact_json else {
        "subject": "Yamaha P-150", "property": "width", "value": "999", "unit": "cm",
        "evidence": "The Yamaha P-150 has a width of 999 cm."
    }
    try:
        print(json.dumps(extract_ids(fact), indent=2, ensure_ascii=False))
    except (httpx.HTTPError, ValueError) as error:
        raise SystemExit(f"Local resolution failed: {error}") from error


if __name__ == "__main__":
    main()
