"""Print source facts alongside local IDs without modifying their content.

Run this file for sample output, or pass a grouped resolved JSON file.
This module needs neither QLever nor CampusAI.
"""
import argparse
import json
from pathlib import Path
import sys
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from functions.resolved_models import ResolvedExtraction


def print_results(facts: ResolvedExtraction | dict | list, as_json: bool = False) -> None:
    """Print grouped keyboards/properties; retain reading of old flat exports.

    JSON preserves empty groups and all matching candidates. Readable output
    shows populated groups, with value QIDs only for entity-valued properties.
    """
    if isinstance(facts, ResolvedExtraction):
        facts = facts.model_dump(mode="json")
    if as_json:
        print(json.dumps(facts, indent=2, ensure_ascii=False))
        return
    if isinstance(facts, dict):
        result = ResolvedExtraction.model_validate(facts)
        if not result.entities:
            print("No supported musical keyboard facts found in the input.")
        for number, entity in enumerate(result.entities, 1):
            print(f"\nKeyboard {number}: {entity.name}\n" + "-" * 48)
            print(f"Subject QID: {entity.subject_id or 'unresolved'}")
            for warning in entity.warnings:
                print(f"Review: {warning}")
            if len(entity.subject_candidates) > 1:
                print("Subject candidates: " + ", ".join(c.id for c in entity.subject_candidates))
            for prop in entity.properties.values():
                if not prop.claims:
                    continue
                print(f"\n  {prop.label} ({prop.property_id})")
                for i, claim in enumerate(prop.claims, 1):
                    print(f"    Claim {i} value: {claim.value}")
                    if prop.value_type == "Quantity":
                        print(f"    Unit: {claim.unit if claim.unit is not None else 'not stated'}")
                    if prop.value_type == "WikibaseItem":
                        print(f"    Value QID: {claim.value_id or 'unresolved'}")
                        if len(claim.value_candidates) > 1:
                            print("    Value candidates: " + ", ".join(c.id for c in claim.value_candidates))
                    print(f"    Evidence: {claim.evidence}")
                    for warning in claim.warnings:
                        print(f"    Review: {warning}")
        return
    # Compatibility for previously saved flat JSON; the handler never uses this.
    if not facts:
        print("No supported musical keyboard facts found in the input.")
    for number, fact in enumerate(facts, 1):
        print(f"\nFact {number}\n" + "-" * 48)
        for title, key in [("Subject", "subject"), ("Subject QID", "subject_id"),
                           ("Property", "property"), ("Property PID", "property_id"),
                           ("Value", "value"), ("Value QID", "value_id"),
                           ("Unit", "unit"), ("Evidence", "evidence")]:
            value = fact.get(key)
            if value is None:
                value = "not linked" if key.endswith("_id") else "not stated"
            print(f"{title:14}: {value}")
        for warning in fact.get("warnings", []):
            print(f"{'Review':14}: {warning}")


def main():
    """Preview formatting with a sample or a saved list of resolved claims."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", nargs="?", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    facts = json.loads(args.file.read_text()) if args.file else {"entities": [{
        "name": "Yamaha P-150", "subject_id": "Q1", "properties": {"width": {
            "property_id": "P2", "label": "width", "value_type": "Quantity",
            "claims": [{"value": "999", "unit": "cm",
                        "evidence": "The Yamaha P-150 has a width of 999 cm."}]}}}]}
    print_results(facts, args.json)


if __name__ == "__main__":
    main()
