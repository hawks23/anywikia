"""Compatibility CLI; graph lifecycle lives in functions/ via handler.py."""
import json
import sys
from pathlib import Path
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from handler import graph_action

def main():
    print("Preparing the dedicated writable graph (Docker required).", flush=True)
    print(json.dumps(graph_action("setup"), indent=2))

if __name__ == "__main__":
    main()
