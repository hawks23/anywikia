"""Read-only review helpers used by handler.review_action.

Keep SPARQL construction and isolated extraction here; web_app.py only handles
HTTP requests/responses. The child extraction process calls handler.run_pipeline
and streams progress on stderr while returning machine-readable JSON on stdout.
"""

import json
import re
import subprocess
import sys

import httpx

from local_rdf import PROJECT_DIR, SPARQL_ENDPOINT

ROOT = PROJECT_DIR


def inspect_entity(qid):
    """Read direct properties and available quantity units for one local QID.

    Direct claims omit qualifiers and references. Return raw RDF terms alongside
    English labels so missing labels and units do not hide stored information.
    """
    if not isinstance(qid, str) or not re.fullmatch(r"Q[1-9][0-9]*", qid):
        raise ValueError("Invalid local entity ID")
    query = f"""
PREFIX kb: <https://keyboards.wikibase.cloud/entity/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX wb: <http://wikiba.se/ontology#>
SELECT DISTINCT ?property ?propertyLabel ?value ?valueLabel ?unit WHERE {{
 kb:{qid} ?predicate ?value .
 ?property wb:directClaim ?predicate .
 OPTIONAL {{ ?property rdfs:label ?propertyLabel . FILTER(LANG(?propertyLabel) = "en") }}
 OPTIONAL {{ ?value rdfs:label ?valueLabel . FILTER(LANG(?valueLabel) = "en") }}
 OPTIONAL {{
  ?property wb:claim ?claimPredicate ; wb:statementProperty ?statementPredicate ; wb:statementValue ?valuePredicate .
  kb:{qid} ?claimPredicate ?statement .
  ?statement ?statementPredicate ?value ; ?valuePredicate ?node .
  ?node wb:quantityUnit ?unit .
 }}
}} ORDER BY ?property ?value
"""
    response = httpx.post(
        SPARQL_ENDPOINT,
        data={"query": query},
        headers={"Accept": "application/sparql-results+json"},
        timeout=20,
    )
    response.raise_for_status()
    return {"id": qid, "properties": response.json()["results"]["bindings"]}


def extract(text):
    """Keep CLI behavior isolated; return its grouped JSON without modification."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Enter some source text first.")
    if len(text) > 20000:
        raise ValueError("Use at most 20,000 characters per passage.")
    # Keep JSON on stdout for the browser and stream progress/errors directly to
    # the server terminal on inherited stderr. Library calls do not enable logs
    # themselves, so configure them explicitly inside this isolated child.
    runner = """
import json
import sys
import traceback
from functions.progress import configure_progress
from handler import run_pipeline

configure_progress()
try:
    result = run_pipeline(sys.stdin.read())
except Exception as error:
    traceback.print_exc()
    print(json.dumps({"error": str(error)}))
    sys.exit(1)
print(result.model_dump_json())
"""
    result = subprocess.run(
        [sys.executable, "-u", "-c", runner],
        input=text,
        text=True,
        stdout=subprocess.PIPE,
        cwd=ROOT,
        timeout=300,
    )
    if result.returncode:
        try:
            detail = json.loads(result.stdout).get("error")
        except (ValueError, AttributeError):
            detail = None
        raise ValueError(
            detail or "The pipeline failed. Check the server terminal for details."
        )
    return json.loads(result.stdout)
