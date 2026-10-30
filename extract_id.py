import requests
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

    response = requests.get(
        WIKIDATA_API,
        params=params,
        headers={"User-Agent": "EntityRetreival_hawks"},
        timeout=15
    )
    response.raise_for_status()

    results = response.json().get("search", [])

    return [
        {
            "id": result["id"],
            "label": result.get("label"),
            "description": result.get("description")
        }
        for result in results
    ]


# Example usage
print(search_wikidata("Finn Aarup Nielsen", "item"))
print(search_wikidata("author", "property"))