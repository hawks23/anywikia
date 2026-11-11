"""Read-only checks for SPARQL availability and the expected Keyboards data.

Run this file with --check server, --check data, or --check both (default).
Neither check starts Docker, calls an LLM, or modifies the graph.
"""
import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from local_rdf import SPARQL_ENDPOINT


def check_server(endpoint: str = SPARQL_ENDPOINT) -> dict:
    """Confirm query execution, even for an empty graph; raise on failure."""
    response = httpx.post(endpoint, data={"query": "SELECT (1 AS ?ok) WHERE {}"},
                         headers={"Accept": "application/sparql-results+json"}, timeout=5)
    response.raise_for_status()
    rows = response.json().get("results", {}).get("bindings", [])
    if not rows or rows[0].get("ok", {}).get("value") != "1":
        raise ValueError("Endpoint did not return the expected SPARQL result.")
    return {"check": "server", "ok": True, "endpoint": endpoint}


def check_dataset(endpoint: str = SPARQL_ENDPOINT) -> dict:
    """Check known item/property definitions, not every triple or fact value.

    Detects an empty or wrong dataset. Does not require a fixed triple count,
    allowing the snapshot to grow. Raises ValueError if expected data is absent.
    """
    query = '''
PREFIX kb: <https://keyboards.wikibase.cloud/entity/>
PREFIX kbt: <https://keyboards.wikibase.cloud/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX wikibase: <http://wikiba.se/ontology#>
ASK { kb:Q1 rdfs:label "Yamaha P-150"@en .
      kb:P2 wikibase:directClaim kbt:P2 . }
'''
    response = httpx.post(endpoint, data={"query": query},
                         headers={"Accept": "application/sparql-results+json"}, timeout=5)
    response.raise_for_status()
    if response.json().get("boolean") is not True:
        raise ValueError("Expected Keyboards item/property definitions were not found.")
    return {"check": "dataset", "ok": True, "endpoint": endpoint}


def main():
    """Run either check independently; failures exit with a nonzero status."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", choices=["server", "data", "both"], default="both")
    parser.add_argument("--endpoint", default=SPARQL_ENDPOINT)
    args = parser.parse_args()
    try:
        if args.check in ("server", "both"):
            print(json.dumps(check_server(args.endpoint)))
        if args.check in ("data", "both"):
            print(json.dumps(check_dataset(args.endpoint)))
    except (httpx.HTTPError, ValueError) as error:
        raise SystemExit(f"QLever check failed: {error}") from error


if __name__ == "__main__":
    main()
