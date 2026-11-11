"""Shared paths and endpoint for the local Keyboards snapshot."""
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
INDEX_DIR = PROJECT_DIR / "keyboards-index"
RDF_PATH = INDEX_DIR / "keyboards.nt"
SPARQL_ENDPOINT = "http://127.0.0.1:7071"
