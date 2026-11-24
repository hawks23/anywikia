"""Derived entity-name JSON; QLever remains the authoritative source of identity."""

import re
from rdflib import RDFS, SKOS
from functions.rdf_models import KB
from functions.qlever_runtime import atomic_json


def display_name(graph, subject):
    """Prefer an English label, with deterministic fallback to another language."""
    labels = sorted(
        graph.objects(subject, RDFS.label), key=lambda v: (v.language != "en", str(v))
    )
    return str(labels[0]) if labels else str(subject).removeprefix(str(KB))


def write_entity_catalog(graph, runtime_root):
    """Atomically refresh all labeled local QIDs, including new value entities."""
    subjects = {
        s
        for s in graph.subjects(RDFS.label, None)
        if re.fullmatch(re.escape(str(KB)) + r"Q[1-9][0-9]*", str(s))
    }
    entities = [
        {
            "id": str(s).removeprefix(str(KB)),
            "name": display_name(graph, s),
            "aliases": sorted({str(v) for v in graph.objects(s, SKOS.altLabel)}),
        }
        for s in sorted(subjects, key=lambda s: int(str(s).removeprefix(str(KB) + "Q")))
    ]
    path = runtime_root / "entity_list.json"
    atomic_json(path, {"entities": entities})
    return str(path)
