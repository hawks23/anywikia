"""Start the saved local QLever graph and its query UI; no test RDF is written."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ui-port", type=int, default=8178, help="Query UI port (default: 8178)")
    args = parser.parse_args()
    from handler import graph_action
    try:
        result = graph_action("query-ui", {"port": args.ui_port})
    except Exception as error:
        raise SystemExit(f"Could not start QLever UI: {error}\nCheck Docker Desktop. If the UI port is occupied, retry with --ui-port 8179.") from error
    print(f"\nQLever UI ready: {result['url']}\nQuery endpoint: {result['endpoint']}")
    print("Both services run in Docker; you can close this terminal. No rebuild is needed to query saved changes.")
    print("\nPaste this into the UI and click Execute to check Q13's keys:\n")
    print("PREFIX kb: <https://keyboards.wikibase.cloud/entity/>\n"
          "PREFIX kbt: <https://keyboards.wikibase.cloud/prop/direct/>\n"
          "SELECT ?keys WHERE { kb:Q13 kbt:P1 ?keys . }")


if __name__ == "__main__":
    main()
