"""Shared paths and endpoint for the local Keyboards snapshot."""
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
INDEX_DIR = PROJECT_DIR / "keyboards-index"
RDF_PATH = INDEX_DIR / "keyboards.nt"
# The managed writable graph is deliberately separate from the old 7071 server.
SPARQL_ENDPOINT = "http://127.0.0.1:7072"
RUNTIME_DIR = PROJECT_DIR / ".anywikia"
