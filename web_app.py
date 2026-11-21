"""Local review UI: python web_app.py, then visit http://localhost:8000.

Runs the unchanged CLI pipeline in an isolated subprocess. Browser edits are
review drafts only. No endpoint writes RDF or creates entities. Bind locally;
this development server is not intended for public deployment.
"""
import argparse
import json
import re
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import httpx
from local_rdf import SPARQL_ENDPOINT
from functions.similar_names import add_name_suggestions

ROOT = Path(__file__).resolve().parent


def inspect_entity(qid):
    """Read direct properties and available quantity units for one local QID.

    Direct claims omit qualifiers and references. Return raw RDF terms alongside
    English labels so missing labels and units do not hide stored information.
    """
    if not re.fullmatch(r"Q[1-9][0-9]*", qid):
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
    response = httpx.post(SPARQL_ENDPOINT, data={"query": query},
                          headers={"Accept": "application/sparql-results+json"}, timeout=20)
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
    result = subprocess.run([sys.executable, "-u", "-c", runner], input=text, text=True,
                            stdout=subprocess.PIPE, cwd=ROOT, timeout=300)
    if result.returncode:
        try:
            detail = json.loads(result.stdout).get("error")
        except (ValueError, AttributeError):
            detail = None
        raise ValueError(detail or "The pipeline failed. Check the server terminal for details.")
    return json.loads(result.stdout)


class Handler(BaseHTTPRequestHandler):
    """Serve a fixed asset list and two read-only application endpoints."""
    def send(self, status, body, mime="application/json"):
        data = json.dumps(body).encode() if mime == "application/json" else body
        self.send_response(status)
        self.send_header("Content-Type", mime + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        assets = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"), "/comparison.js": ("comparison.js", "text/javascript"), "/style.css": ("style.css", "text/css")}
        try:
            if path in assets:
                name, mime = assets[path]
                return self.send(200, (ROOT / "frontend" / name).read_bytes(), mime)
            if path.startswith("/api/entities/"):
                return self.send(200, inspect_entity(path.rsplit("/", 1)[-1]))
            self.send(404, {"error": "Not found"})
        except ValueError as error:
            self.send(400, {"error": str(error)})
        except httpx.HTTPError:
            self.send(502, {"error": "Cannot read QLever. Check the local server and retry."})

    def do_POST(self):
        # Require same-origin JSON; other websites cannot trigger LLM requests.
        origin = self.headers.get("Origin")
        if origin and origin != "http://" + self.headers.get("Host", ""):
            return self.send(403, {"error": "Cross-origin requests are not allowed."})
        if self.path != "/api/extract":
            return self.send(404, {"error": "Not found"})
        try:
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise ValueError("Expected JSON")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 100000:
                raise ValueError("Request is empty or too large")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Expected a JSON object")
            self.send(200, add_name_suggestions(extract(payload.get("text"))))
        except (ValueError, UnicodeDecodeError) as error:
            self.send(400, {"error": str(error)})
        except subprocess.TimeoutExpired:
            self.send(504, {"error": "Pipeline exceeded five minutes. Try a shorter passage."})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Anywikia review desk: http://localhost:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
