"""FastAPI adapter for Anywikia. Run `python web_app.py` on localhost:8000.

Routes translate HTTP inputs into handler calls. Extraction, name matching and
RDF persistence stay in functions/. Ordinary def routes run blocking work in
FastAPI's thread pool. See backend-guide.md for a complete call walkthrough.
"""

import argparse
from pathlib import Path
import secrets

from fastapi import FastAPI, Request, Security
from fastapi.responses import FileResponse
from fastapi.security import APIKeyHeader
import uvicorn

from api_http import LocalRequestMiddleware, install_error_handlers
from api_models import (
    ConfirmRequest,
    EntityRequest,
    ErrorResponse,
    ExtractionRequest,
    PreviewRequest,
    RebuildRequest,
    SearchRequest,
    VerifyRequest,
)

ROOT = Path(__file__).resolve().parent
csrf_header = APIKeyHeader(
    name="X-Anywikia-CSRF",
    auto_error=False,
    description="Copy csrf from GET /api/graph/status. Required for every graph POST.",
)


# Application adapters: also used by the disposable browser fixture and tests.
def graph_action(action, payload=None):
    """Forward a graph operation to the central application dispatcher."""
    from handler import graph_action as dispatch

    return dispatch(action, payload)


def review_action(action, payload=None):
    """Forward a read-only operation to the central application dispatcher."""
    from handler import review_action as dispatch

    return dispatch(action, payload)


def inspect_entity(qid):
    """Read direct stored properties for the browser's comparison panel."""
    return review_action("inspect", {"entity_id": qid})


def extract(text):
    """Run the isolated extraction pipeline; do not write RDF."""
    return review_action("extract", {"text": text})


def add_name_suggestions(result):
    """Attach optional fuzzy candidates without confirming an identity."""
    return review_action("suggest", result)


def create_app():
    """Build the HTTP app without starting Docker or contacting CampusAI.

    Each app receives a fresh CSRF token. Run one serving worker because graph
    job status and name caches are process-local. Graph setup remains explicit.
    """
    application = FastAPI(
        title="Anywikia local review API",
        description="Extract keyboard facts, review matches, and explicitly save RDF changes.",
        version="1.0.0",
        responses={
            "default": {
                "model": ErrorResponse,
                "description": (
                    "Expected errors: 400 invalid request; 403 local access/token; "
                    "404/405 route/method; 502 backend HTTP; 503 runtime or uncertain "
                    "save; 504 extraction timeout. Validation uses 400, not 422."
                ),
            }
        },
    )
    application.state.csrf_token = secrets.token_urlsafe(32)
    application.add_middleware(
        LocalRequestMiddleware, csrf_token=application.state.csrf_token
    )
    install_error_handlers(application)

    # Read-only routes: source extraction, comparison and graph readiness.
    @application.post("/api/extract", tags=["Extraction"])
    def extract_endpoint(body: ExtractionRequest):
        """Extract typed facts, resolve exact IDs, then suggest similar names."""
        return add_name_suggestions(extract(body.text))

    @application.get("/api/entities/{qid}", tags=["Review"])
    def compare_endpoint(qid: str):
        """Read direct values for comparison; does not confirm the identity."""
        return inspect_entity(qid)

    @application.get("/api/graph/status", tags=["Graph"])
    def status_endpoint(request: Request):
        """Return readiness, editable properties, rebuild progress and the CSRF token."""
        return {**graph_action("status"), "csrf": request.app.state.csrf_token}

    # Graph POST routes all require X-Anywikia-CSRF, checked by middleware.
    @application.post(
        "/api/graph/inspect", tags=["Review"], dependencies=[Security(csrf_header)]
    )
    def inspect_endpoint(body: EntityRequest):
        """Read statement identities needed to select a precise replacement."""
        return graph_action("inspect", body.model_dump())

    @application.post(
        "/api/graph/search", tags=["Review"], dependencies=[Security(csrf_header)]
    )
    def search_endpoint(body: SearchRequest):
        """Find entity-valued property candidates by label, alias or QID."""
        return graph_action("search", body.model_dump())

    @application.post(
        "/api/graph/preview", tags=["Saving"], dependencies=[Security(csrf_header)]
    )
    def preview_endpoint(body: PreviewRequest):
        """Validate edits and persist a 15-minute plan; leave live RDF unchanged."""
        return graph_action("preview", body.model_dump())

    @application.post(
        "/api/graph/confirm", tags=["Saving"], dependencies=[Security(csrf_header)]
    )
    def confirm_endpoint(body: ConfirmRequest):
        """Apply an approved preview once, then verify; retries use the same ID."""
        return graph_action("confirm", body.model_dump())

    @application.post(
        "/api/graph/verify", tags=["Graph"], dependencies=[Security(csrf_header)]
    )
    def verify_endpoint(body: VerifyRequest):
        """Query saved values and return both readable results and generated SPARQL."""
        return graph_action("verify", body.model_dump())

    @application.post(
        "/api/graph/rebuild", tags=["Graph"], dependencies=[Security(csrf_header)]
    )
    def rebuild_endpoint(body: RebuildRequest):
        """Start confirmed export/rebuild in the existing background job; poll status."""
        return graph_action("rebuild", body.model_dump())

    # Explicit asset allowlist: never expose .env, runtime files or repository RDF.
    @application.get("/", include_in_schema=False)
    def home():
        return FileResponse(ROOT / "frontend" / "index.html", media_type="text/html")

    def add_asset_route(name, media_type):
        def asset():
            return FileResponse(ROOT / "frontend" / name, media_type=media_type)

        application.add_api_route(
            "/" + name, asset, methods=["GET"], include_in_schema=False
        )

    for name in ("app.js", "comparison.js", "review-plan.js", "rdf-review.js"):
        add_asset_route(name, "text/javascript")
    add_asset_route("style.css", "text/css")
    return application


app = create_app()


def main():
    """Keep the original launcher and --port option, using one Uvicorn worker."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    uvicorn.run(app, host="127.0.0.1", port=args.port, workers=1, proxy_headers=False)


if __name__ == "__main__":
    main()
