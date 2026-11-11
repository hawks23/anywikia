"""Print source facts alongside local IDs without modifying their content.

Run this file for sample output, or pass a JSON file containing a list of facts.
This module needs neither QLever nor CampusAI.
"""
import argparse
import json
from pathlib import Path


def print_results(facts: list[dict], as_json: bool = False) -> None:
    """Display a readable record per fact, or the complete records as JSON."""
    if as_json:
        print(json.dumps(facts, indent=2, ensure_ascii=False))
        return
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
    facts = json.loads(args.file.read_text()) if args.file else [{
        "subject": "Yamaha P-150", "subject_id": "Q1", "property": "width",
        "property_id": "P2", "value": "999", "unit": "cm", "value_id": None,
        "evidence": "The Yamaha P-150 has a width of 999 cm.", "warnings": []}]
    print_results(facts, args.json)


if __name__ == "__main__":
    main()
