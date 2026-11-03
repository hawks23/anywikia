"""Run the keyboard extractor and resolve its output against Wikidata."""
import json
import sys

from requests import RequestException

from extract_id import extract_ids
from extract_input import extract_entities


def main():
    """Print extracted facts and resolved records, reporting lookup failures on stderr."""
    inp = """
The catalog lists the Yamaha DX7, manufactured by Yamaha and introduced in 1983, as a 61-key digital FM synthesizer measuring 101.8 cm wide and weighing 14.2 kg, and the Roland JUNO-106, manufactured by Roland and introduced in 1984, as a 61-key analog synthesizer with six-voice polyphony; a handwritten note says the latter weighs 10 kg, identifies the nearby Yamaha DX7II-D as a separate model whose weight was never recorded, and lists a 104-key computer keyboard and a sustain pedal among the accessories.
"""
    extracted = extract_entities(inp)
    print(json.dumps(extracted, ensure_ascii=False))

    resolved = []
    for triple in extracted["items"]:
        try:
            resolved.append(extract_ids(triple))
        except ValueError as error:
            print(f"Unresolved triple {triple!r}: {error}", file=sys.stderr)

        except (RequestException, RuntimeError) as error:
            print(f"Wikidata lookup stopped at {triple!r}: {error}", file=sys.stderr)
            break

    print(json.dumps(resolved, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()