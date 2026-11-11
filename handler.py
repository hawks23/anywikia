"""Run Anywikia: check QLever, extract source facts, attach IDs, display results.

Each step lives in functions/. This module coordinates them and handles CLI
input/errors. The graph supplies IDs only; it never supplies replacement fact
values. No statements are written. Run `python handler.py "Source passage"`.
"""
import argparse

import httpx
from openai import OpenAIError

from functions.extract_input import extract_entities
from functions.resolve_local import extract_ids, BASE
from functions.qlever_checks import check_server, check_dataset
from functions.display_results import print_results

SAMPLE_TEXT = "The Yamaha P-150 has a width of 1385 mm."


def run_pipeline(text: str) -> list[dict]:
    """Return extracted claims with local IDs and review warnings.

    Preflight checks fail before making an LLM request if QLever is unavailable.
    Extraction errors propagate. A lookup failure after preflight preserves the
    source fact with unresolved IDs instead of silently dropping it.
    """
    # 1. Verify query execution, then the intended dataset.
    check_server()
    check_dataset()

    # 2. Only the source text supplies claim content and supporting quotations.
    extracted = extract_entities(text)

    # 3. Resolve each claim independently; never replace its values from the RDF.
    facts = []
    for fact in extracted["items"]:
        try:
            facts.append(extract_ids(fact))
        except (httpx.HTTPError, ValueError) as error:
            facts.append({**fact, "subject_id": None, "property_id": None,
                          "value_id": None, "knowledge_base": BASE.removesuffix("/entity/"),
                          "warnings": [f"Local lookup failed: {error}"]})
    return facts


def main():
    """Read one passage and print readable records or JSON; fail clearly."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text", nargs="?", default=SAMPLE_TEXT)
    parser.add_argument("--json", action="store_true", help="Print machine-readable records")
    args = parser.parse_args()
    try:
        facts = run_pipeline(args.text)
    except (httpx.HTTPError, OpenAIError, ValueError) as error:
        raise SystemExit(f"Pipeline failed: {error}") from error
    # 4. Presentation is separate from extraction and resolution.
    print_results(facts, as_json=args.json)


if __name__ == "__main__":
    main()
