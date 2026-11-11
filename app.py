"""Extract source facts with CampusAI and attach local Keyboards Wikibase IDs."""
import argparse
import json
import sys

from httpx import HTTPError

from resolve_local import extract_ids
from extract_input import extract_entities


def main():
    """Print extracted facts and resolved records, reporting lookup failures on stderr."""
    inp = """
The catalog lists the Yamaha DX7, manufactured by Yamaha and introduced in 1983, as a 61-key digital FM synthesizer measuring 101.8 cm wide and weighing 14.2 kg, and the Roland JUNO-106, manufactured by Roland and introduced in 1984, as a 61-key analog synthesizer with six-voice polyphony; a handwritten note says the latter weighs 10 kg, identifies the nearby Yamaha DX7II-D as a separate model whose weight was never recorded, and lists a 104-key computer keyboard and a sustain pedal among the accessories.
"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text", nargs="?", help="Source passage; defaults to the sample passage.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable records.")
    args = parser.parse_args()
    extracted = extract_entities(args.text if args.text is not None else inp)

    resolved = []
    for triple in extracted["items"]:
        try:
            resolved.append(extract_ids(triple))
        except ValueError as error:
            print(f"Unresolved triple {triple!r}: {error}", file=sys.stderr)

        except HTTPError as error:
            resolved.append({**triple, "subject_id": None, "property_id": None,
                             "value_id": None, "warnings": [f"Local lookup failed: {error}"]})

    if args.json:
        print(json.dumps(resolved, ensure_ascii=False, indent=2))
        return
    if not resolved:
        print("No supported musical keyboard facts found in the input.")
    for fact in resolved:
        print(f"Subject:   {fact['subject']}")
        print(f"Subject ID: {fact['subject_id'] or 'unresolved'}")
        print(f"Property:  {fact['property']}")
        print(f"Property ID: {fact['property_id'] or 'unresolved'}")
        print(f"Value:     {fact['value']}")
        if fact.get('value_id'):
            print(f"Value ID:  {fact['value_id']}")
        print(f"Unit:      {fact['unit'] if fact['unit'] is not None else 'not stated'}")
        print(f"Evidence:  {fact['evidence']}")
        for warning in fact.get('warnings', []):
            print(f"Review:    {warning}")
        print()


if __name__ == "__main__":
    main()
