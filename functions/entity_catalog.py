"""Choose readable entity labels from graph data."""

from rdflib import RDFS
from functions.rdf_models import KB


def display_name(graph, subject):
    """Prefer an English label, with deterministic fallback to another language."""
    labels = sorted(
        graph.objects(subject, RDFS.label), key=lambda v: (v.language != "en", str(v))
    )
    return str(labels[0]) if labels else str(subject).removeprefix(str(KB))
