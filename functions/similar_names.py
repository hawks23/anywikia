"""Suggest up to three keyboard QIDs after exact name lookup fails.

The website process owns this lazy, five-minute, in-memory cache. Nothing is
saved to disk. Candidates have P1 (number of keys) or the application Keyboard
type, so newly created keyboards remain discoverable without a key count.
Suggestions never assign an ID: the user must inspect and confirm a candidate.
"""
import logging
from threading import Lock
from time import monotonic

import httpx
from local_rdf import SPARQL_ENDPOINT

BASE = "https://keyboards.wikibase.cloud/entity/"
CACHE_SECONDS = 300
_cache = None
_loaded_at = 0.0
_lock = Lock()


def normalize(name):
    """Ignore case and repeated whitespace, but preserve model punctuation."""
    return " ".join(name.casefold().split())


def distance(a, b):
    """Levenshtein edit distance using one row of working memory."""
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, 1):
        current = [i]
        for j, char_b in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1,
                               previous[j - 1] + (char_a != char_b)))
        previous = current
    return previous[-1]


def load_names():
    """Read keyboard labels/aliases and display names from the current index."""
    query = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX kbt: <https://keyboards.wikibase.cloud/prop/direct/>
SELECT DISTINCT ?entity ?name ?label WHERE {
 { ?entity kbt:P1 ?keys } UNION { ?entity a <urn:anywikia:Keyboard> }
 ?entity (rdfs:label|skos:altLabel) ?name .
 FILTER(STRSTARTS(STR(?entity), "https://keyboards.wikibase.cloud/entity/Q"))
 FILTER(LANG(?name) IN ("en", "da", ""))
 OPTIONAL { ?entity rdfs:label ?label . FILTER(LANG(?label) = "en") }
} ORDER BY ?entity ?name
"""
    response = httpx.post(SPARQL_ENDPOINT, data={"query": query},
                          headers={"Accept": "application/sparql-results+json"}, timeout=20)
    response.raise_for_status()
    return [{"id": row["entity"]["value"].removeprefix(BASE),
             "name": row.get("label", row["name"])["value"],
             "matched_name": row["name"]["value"],
             "normalized": normalize(row["name"]["value"])}
            for row in response.json()["results"]["bindings"]]


def cached_names():
    """Load only on demand; serialize refreshes across concurrent web requests.

    Failed refreshes propagate and are retried on the next request. Expiration
    does not trigger background requests; refresh waits for another lookup.
    """
    global _cache, _loaded_at
    with _lock:
        if _cache is None or monotonic() - _loaded_at >= CACHE_SECONDS:
            rows = load_names()
            _cache, _loaded_at = rows, monotonic()
        return _cache


def invalidate_name_cache():
    """Discard a loaded cache; do not create or fetch one."""
    global _cache, _loaded_at
    with _lock:
        _cache, _loaded_at = None, 0.0

# Confirmed graph writes invalidate this in-memory cache.


def suggest_names(name):
    """Rank each QID by its best label/alias; keep only distances below three.

    The strict threshold is distance < 3 (0, 1 or 2). Return at most three
    distinct entities, not three aliases of one entity. No automatic linking.
    """
    query = normalize(name)
    if not query:
        return []
    best = {}
    for row in cached_names():
        if abs(len(query) - len(row["normalized"])) >= 3:
            continue
        score = distance(query, row["normalized"])
        if score >= 3:
            continue
        candidate = {key: row[key] for key in ("id", "name", "matched_name")}
        candidate["distance"] = score
        if row["id"] not in best or score < best[row["id"]]["distance"]:
            best[row["id"]] = candidate
    return sorted(best.values(), key=lambda row: (row["distance"], row["id"]))[:3]


def add_name_suggestions(result):
    """Enrich only unmatched keyboard results; preserve successful extraction.

    Exact matches, ambiguous exact matches, and failed exact queries do not
    trigger a cache load. A suggestion-service error is not an empty match list.
    """
    for entity in result["entities"]:
        if entity.get("subject_id") or entity.get("subject_candidates"):
            continue
        if "subject: no local match" not in entity.get("warnings", []):
            continue
        try:
            entity["name_suggestions"] = suggest_names(entity["name"])
        except (httpx.HTTPError, ValueError, KeyError) as error:
            logging.getLogger(__name__).warning("Similar-name lookup failed: %s", error)
            entity["suggestion_error"] = "Similar-name suggestions unavailable. Try extraction again later."
    return result
