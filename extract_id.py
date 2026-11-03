"""Search Wikidata labels and resolve keyboard triples to ranked item and property IDs."""
import json
import time
from functools import lru_cache

import requests
from urllib3.util.retry import Retry

REQUEST_INTERVAL = 1.0
MAX_ATTEMPTS = 3
WIKIDATA_API = "https://www.wikidata.org/w/api.php"

def search_wikidata(query: str, search_type: str = "item", limit: int = 5):
    """
    Search Wikidata for an entity (QID) or property (PID).

    search_type:
        item     -> QID
        property -> PID
    """

    if search_type not in ("item", "property"):
        raise ValueError("search_type must be 'item' or 'property'")

    params = {
        "action": "wbsearchentities",
        "search": query,
        "language": "en",
        "uselang": "en",
        "type": search_type,
        "limit": limit,
        "format": "json"
    }

    # Pace every network attempt, including the first lookup in a new triple.
    delay = REQUEST_INTERVAL
    for attempt in range(MAX_ATTEMPTS):
        time.sleep(delay)
        response = requests.get(
            WIKIDATA_API,
            params=params,
            headers={"User-Agent": "EntityRetreival_hawks"},
            timeout=15,
        )
        if response.status_code != 429 or attempt + 1 == MAX_ATTEMPTS:
            response.raise_for_status()
            break

        # Retry-After may be a number of seconds or an HTTP date.
        server_delay = Retry().get_retry_after(response)
        delay = max(REQUEST_INTERVAL, server_delay if server_delay is not None else 2 ** (attempt + 1))

    data = response.json()
    if "error" in data:
        raise RuntimeError(f"Wikidata API error: {data['error']}")
    results = data.get("search", [])

    return [
        {
            "id": result["id"],
            "label": result.get("label"),
            "description": result.get("description")
        }
        for result in results
    ]


@lru_cache(maxsize=512)
def _first_id(label: str, search_type: str):
    """Cache the top ID or a miss so repeated facts share one search per label and type."""
    matches = search_wikidata(label, search_type, limit=1)
    return matches[0]["id"] if matches else None


def extract_ids(triple: dict) -> dict:
    """Resolve Wikidata IDs while preserving the input names and value.

    Raises ValueError when a lookup has no matches. Ambiguous names use
    Wikidata's search ranking and may require caller review.
    """
    for field in ("subject", "property", "value"):
        if field not in triple:
            raise ValueError(f"Missing required field: {field}")
    for field in ("subject", "property"):
        if not isinstance(triple[field], str) or not triple[field].strip():
            raise ValueError(f"{field} must be a non-empty string")

    resolved = {}
    for field, search_type in (("subject", "item"), ("property", "property")):
        identifier = _first_id(triple[field], search_type)
        if identifier is None:
            raise ValueError(f"No Wikidata {search_type} found for {triple[field]!r}")
        resolved[field] = identifier

    return {
        "subjectName": triple["subject"],
        "subject": resolved["subject"],
        "propertyName": triple["property"],
        "property": resolved["property"],
        "value": triple["value"]
    }


if __name__ == "__main__":
    triple = {
        "subject": "A100 Blackwell GPU",
        "property": "wider availability date",
        "value": "2026-11-17"
    }
    print(json.dumps(extract_ids(triple), indent=2))
