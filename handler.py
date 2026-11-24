"""Run Anywikia: check QLever, extract source facts, attach IDs, display results.

Each step lives in functions/. This module coordinates them and handles CLI
input/errors. The graph supplies IDs only; it never supplies replacement fact
values. The extraction CLI is read-only. graph_action dispatches separately
confirmed writes, queries and rebuilds to functions/. Run
`python handler.py "Source passage"` or `python handler.py --setup-graph`.
"""
import argparse

import httpx
from openai import OpenAIError

from functions.extract_input import extract_entities
from functions.pydantic_models import Extraction, PROPERTY_FIELDS
from functions.resolve_local import resolve_extraction
from functions.resolved_models import ResolvedExtraction
from functions.qlever_checks import check_server, check_dataset
from functions.display_results import print_results
from functions.progress import configure_progress, report, step

SAMPLE_TEXT = "The Yamaha P-150 has a width of 1385 mm."


def run_pipeline(text: str) -> ResolvedExtraction:
    """Return extracted claims with local IDs and review warnings.

    Preflight checks fail before making an LLM request if QLever is unavailable.
    Extraction errors propagate. A lookup failure after preflight preserves the
    source fact with unresolved IDs instead of silently dropping it.
    """
    # 1. Verify query execution, then the intended dataset.
    with step("Checking QLever server"):
        check_server()
    with step("Checking Keyboards dataset"):
        check_dataset()

    # 2. Only the source text supplies claim content and supporting quotations.
    extracted = extract_entities(text)

    # 3. Validate the grouped extraction and enrich it directly; never flatten it.
    extraction = Extraction.model_validate(extracted)
    count = sum(len(getattr(entity, field)) for entity in extraction.entities
                for field in PROPERTY_FIELDS)
    report(f"Extracted {len(extraction.entities)} keyboard(s), {count} claim(s)")
    with step("Resolving grouped keyboards and values"):
        result = resolve_extraction(extraction, text)
    warnings = sum(len(entity.warnings) + sum(len(claim.warnings)
                   for prop in entity.properties.values() for claim in prop.claims)
                   for entity in result.entities)
    report(f"Ready: {len(result.entities)} keyboard(s), {count} claim(s), {warnings} review warning(s)")
    return result


def main():
    """Read one passage and print readable records or JSON; fail clearly."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text", nargs="?", default=SAMPLE_TEXT)
    parser.add_argument("--json", action="store_true", help="Print machine-readable records")
    parser.add_argument("--quiet", action="store_true", help="Hide progress; errors still appear")
    parser.add_argument("--setup-graph", action="store_true", help="Initialize/start the persistent local working graph")
    args = parser.parse_args()
    if args.setup_graph:
        import json
        print(json.dumps(graph_action("setup"), indent=2))
        return
    configure_progress(quiet=args.quiet)
    try:
        facts = run_pipeline(args.text)
    except (httpx.HTTPError, OpenAIError, ValueError) as error:
        raise SystemExit(f"Pipeline failed: {error}") from error
    # 4. Presentation is separate from extraction and resolution.
    report("Printing JSON results" if args.json else "Printing results")
    print_results(facts, as_json=args.json)


def graph_action(action, payload=None):
    """Orchestrate graph functions for the web adapter and setup CLI."""
    from functions import rdf_service
    payload = payload or {}
    routes = {
        "setup": lambda: rdf_service.initialize_graph(),
        "query-ui": lambda: rdf_service.initialize_query_ui(payload.get("port", 8178)),
        "status": lambda: rdf_service.status(),
        "preview": lambda: rdf_service.preview_change(payload),
        "confirm": lambda: rdf_service.confirm_change(payload),
        "inspect": lambda: rdf_service.inspect_graph_entity(payload.get("entity_id")),
        "search": lambda: rdf_service.search_graph_entities(payload.get("text")),
        "verify": lambda: rdf_service.verify_graph(payload),
        "rebuild": lambda: rdf_service.rebuild_graph(payload),
    }
    if action not in routes:
        raise ValueError("Unknown graph action.")
    return routes[action]()


if __name__ == "__main__":
    main()
