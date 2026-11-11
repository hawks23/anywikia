"""Query the local Keyboards RDF snapshot served by QLever.

Run in WSL: .venv/bin/python test.py
No CampusAI key or public Wikibase API is used.
"""

import argparse
import json

import httpx
from local_rdf import SPARQL_ENDPOINT


# These namespaces and IDs belong to Keyboards Wikibase, not wikidata.org.
# Q1 = Yamaha P-150, P2 = width, P4 = height in keyboards-index/keyboards.nt.
QUERY = """
PREFIX kb: <https://keyboards.wikibase.cloud/entity/>
PREFIX kbt: <https://keyboards.wikibase.cloud/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?keyboard ?label ?width ?height WHERE {
  VALUES ?keyboard { kb:Q1 }
  ?keyboard rdfs:label ?label .
  FILTER(LANG(?label) = "en")
  OPTIONAL { ?keyboard kbt:P2 ?width . }
  OPTIONAL { ?keyboard kbt:P4 ?height . }
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=SPARQL_ENDPOINT)
    args = parser.parse_args()

    print(f"Local SPARQL endpoint: {args.endpoint}\n{QUERY}")
    try:
        response = httpx.post(
            args.endpoint,
            data={"query": QUERY},
            headers={"Accept": "application/sparql-results+json"},
            timeout=35,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise SystemExit(
            f"QLever request failed: {exc}\n"
            "From /home/sweet/anywikia, start the server with: "
            ".venv/bin/python start_qlever.py"
        ) from exc

    bindings = response.json()["results"]["bindings"]
    rows = [{name: term["value"] for name, term in row.items()} for row in bindings]
    print(json.dumps(rows, indent=2, ensure_ascii=False))
    if not rows:
        raise SystemExit("No matching keyboard in the served snapshot.")
    print("Width and height are in millimeters in this snapshot.")


if __name__ == "__main__":
    main()
