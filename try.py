"""Experimental SPARQL helpers requiring an external logger, HTTP client and endpoint."""
def simplify_bindings(bindings: list[dict]) -> list[dict]:
    """Convert SPARQL bindings into dictionaries containing plain values."""
    simplified = []
    for binding in bindings:
        simple_binding = {}
        for key, value in binding.items():
            simple_binding[key] = value["value"]
        simplified.append(simple_binding)
    return simplified


def run_sparql(query: str) -> list[dict]:
    """Execute a SPARQL query and return its simplified result bindings."""
    logger.debug(f"Running SPARQL query: {query}")
    with httpx2.Client(timeout=20) as client:
        r = client.get(SPARQL_ENDPOINT, params={"query": query, "format": "json"})
        r.raise_for_status()
        logger.debug(f"SPARQL response: {r.json()}")
        bindings = r.json()["results"]["bindings"]
        result = simplify_bindings(bindings)  # Optional reformatting
        return result

def get_qid(uri: str) -> str:
    """Extract a keyboard knowledge-base item ID from an entity URI."""
    logger.debug(f"Extracting QID from URI: {uri}")
    if "entity" in uri:
        return uri.split("/")[-1]
    else:
        raise ValueError(f"Invalid URI for QID extraction: {uri}")


def get_pid(uri: str) -> str:
    """Extract a keyboard knowledge-base property ID from a property URI."""
    logger.debug(f"Extracting PID from URI: {uri}")
    if "prop" in uri:
        return uri.split("/")[-1]
    else:
        raise ValueError(f"Invalid URI for PID extraction: {uri}")


def lookup_item(text: str) -> str:
    """Find the item ID whose English label or alias matches ``text``."""
    sparql = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT ?item {{
            ?item rdfs:label | skos:altLabel "{text}"@en
        }}
    """
    results = run_sparql(sparql)
    logger.debug(f"SPARQL results for item lookup: {results}")
    for result in results:
        if "item" in result:
            logger.debug(f"Found item: {result.get('item')}")
            return get_qid(result.get("item"))
    return ""


def lookup_property(text: str) -> str:
    """Find the property ID whose English label or alias matches ``text``."""
    sparql = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX wikibase: <http://wikiba.se/ontology#>
        SELECT ?property {{
            ?property_item rdfs:label | skos:altLabel "{text}"@en ;
        wikibase:directClaim ?property .
    }}"""
    results = run_sparql(sparql)
    logger.debug(f"SPARQL results for property lookup: {results}")
    for result in results:
        if "property" in result:
            return get_pid(result.get("property"))
    return ""