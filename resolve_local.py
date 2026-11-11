"""Attach local IDs to source facts; never retrieve replacement fact values."""
import re
import httpx
from rdflib import Literal
from local_rdf import SPARQL_ENDPOINT

BASE = "https://keyboards.wikibase.cloud/entity/"


def search_local(label, kind):
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


def extract_ids(fact):
    """Preserve source fields and leave absent/ambiguous IDs unresolved."""
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
