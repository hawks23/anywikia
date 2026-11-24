"""Local review UI: python web_app.py, then visit http://localhost:8000.

Runs the CLI pipeline in an isolated subprocess and routes reviewed writes
through handler.graph_action. Bind locally;
this development server is not intended for public deployment.
"""

import argparse
import json
import subprocess
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parent
WRITE_CSRF = secrets.token_urlsafe(32)


def graph_action(action, payload=None):
    from handler import graph_action as dispatch

    return dispatch(action, payload)


def review_action(action, payload=None):
    """Forward read-only review operations to the central handler."""
    from handler import review_action as dispatch

    return dispatch(action, payload)


def inspect_entity(qid):
    """HTTP adapter for the stored-value comparison query."""
    return review_action("inspect", {"entity_id": qid})


def extract(text):
    """HTTP adapter for isolated extraction; never writes RDF."""
    return review_action("extract", {"text": text})


def add_name_suggestions(result):
    """HTTP adapter for optional fuzzy identity suggestions."""
    return review_action("suggest", result)


class Handler(BaseHTTPRequestHandler):
    """HTTP adapter; graph functionality is orchestrated by handler.py."""

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
        if not self.valid_host():
            return self.send(403, {"error": "Localhost access only."})
        path = urlparse(self.path).path
        assets = {
            "/": ("index.html", "text/html"),
            "/app.js": ("app.js", "text/javascript"),
            "/comparison.js": ("comparison.js", "text/javascript"),
            "/style.css": ("style.css", "text/css"),
        }
        assets["/review-plan.js"] = ("review-plan.js", "text/javascript")
        assets["/rdf-review.js"] = ("rdf-review.js", "text/javascript")
        try:
            if path in assets:
                name, mime = assets[path]
                return self.send(200, (ROOT / "frontend" / name).read_bytes(), mime)
            if path == "/api/graph/status":
                return self.send(200, {**graph_action("status"), "csrf": WRITE_CSRF})
            if path.startswith("/api/entities/"):
                return self.send(200, inspect_entity(path.rsplit("/", 1)[-1]))
            self.send(404, {"error": "Not found"})
        except ValueError as error:
            self.send(400, {"error": str(error)})
        except httpx.HTTPError:
            self.send(
                502, {"error": "Cannot read QLever. Check the local server and retry."}
            )
        except (RuntimeError, OSError) as error:
            self.send(503, {"error": str(error)})

    def valid_host(self):
        return self.headers.get("Host", "") in {
            f"localhost:{self.server.server_port}",
            f"127.0.0.1:{self.server.server_port}",
        }

    def do_POST(self):
        # Require same-origin JSON; other websites cannot trigger LLM requests.
        origin = self.headers.get("Origin")
        if not self.valid_host() or (
            origin and origin != "http://" + self.headers.get("Host", "")
        ):
            return self.send(403, {"error": "Cross-origin requests are not allowed."})
        graph_routes = {
            "/api/graph/" + action: action
            for action in (
                "preview",
                "confirm",
                "inspect",
                "search",
                "verify",
                "rebuild",
            )
        }
        if self.path != "/api/extract" and self.path not in graph_routes:
            return self.send(404, {"error": "Not found"})
        try:
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise ValueError("Expected JSON")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 500000:
                raise ValueError("Request is empty or too large")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Expected a JSON object")
            if self.path in graph_routes:
                if not secrets.compare_digest(
                    self.headers.get("X-Anywikia-CSRF", ""), WRITE_CSRF
                ):
                    return self.send(
                        403, {"error": "Reload the page before using graph actions."}
                    )
                return self.send(200, graph_action(graph_routes[self.path], payload))
            self.send(200, add_name_suggestions(extract(payload.get("text"))))
        except (ValueError, UnicodeDecodeError) as error:
            self.send(400, {"error": str(error)})
        except subprocess.TimeoutExpired:
            self.send(
                504, {"error": "Pipeline exceeded five minutes. Try a shorter passage."}
            )
        except httpx.HTTPError:
            self.send(
                502,
                {
                    "error": "Cannot reach the working QLever graph. Check its status and retry."
                },
            )
        except (RuntimeError, OSError) as error:
            self.send(503, {"error": str(error)})


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
