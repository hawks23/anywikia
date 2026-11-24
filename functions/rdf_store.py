"""Preview, confirm, persist and verify small local graph changes.

The browser never supplies SPARQL or trusted property types. Previews are saved
server-side with a graph revision, an operation ID and exact RDF deltas. Retry
after a network timeout verifies that operation instead of allocating another ID.
"""

import json
import re
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from rdflib import BNode, Graph, Literal, RDF, RDFS, SKOS, URIRef, XSD
from rdflib.compare import to_isomorphic

from functions.qlever_runtime import atomic_json
from functions.entity_catalog import display_name
from functions.rdf_models import (
    APP,
    BASE,
    KB,
    PROV,
    WB,
    WriteRequest,
    entity_uri,
    property_catalog,
    value_terms,
)


def predicate(kind, pid):
    return URIRef(BASE + "prop/" + kind + pid)


def revision(graph):
    return str(to_isomorphic(graph).graph_digest())


def verification_triples(triples):
    """QLever may return decimal 90 as 90.0; compare numeric value on read-back."""

    def term_key(term):
        if isinstance(term, Literal) and term.datatype == XSD.decimal:
            return ("decimal", Decimal(str(term)))
        if (
            isinstance(term, Literal)
            and not term.language
            and term.datatype in (None, XSD.string)
        ):
            return ("string", str(term))
        return term

    return {tuple(term_key(term) for term in triple) for triple in triples}


def verification_report(additions, deletions, graph):
    """Compare expected deltas to read-back and summarize any mismatch."""
    expected, removed, actual = map(verification_triples, (additions, deletions, graph))
    missing = expected - actual
    remaining = (removed - expected) & actual
    return {
        "verified": not missing and not remaining,
        "missing_triples": len(missing),
        "remaining_deleted_triples": len(remaining),
        "mismatched_predicates": sorted({str(t[1]) for t in missing | remaining}),
    }


def triples_text(triples):
    if any(isinstance(term, BNode) for triple in triples for term in triple):
        raise ValueError("Editing statements with blank-node terms is not supported.")
    graph = Graph()
    for triple in triples:
        graph.add(triple)
    return graph.serialize(format="nt")


def records(graph, target):
    """Full statement identities, including prices on linked offers."""
    rows = []
    for spec in property_catalog():
        pid = spec["property_id"]
        subjects = {target}
        if pid == "P25":
            subjects.update(graph.subjects(predicate("direct/", "P24"), target))
        for subject in subjects:
            for statement in graph.objects(subject, predicate("", pid)):
                values = list(graph.objects(statement, predicate("statement/", pid)))
                for value in values:
                    nodes = list(
                        graph.objects(statement, predicate("statement/value/", pid))
                    )
                    units = (
                        list(graph.objects(nodes[0], WB.quantityUnit))
                        if len(nodes) == 1
                        else []
                    )
                    unit = units[0] if len(units) == 1 else None
                    quantity_ok = spec["value_type"] != "Quantity" or (
                        len(nodes) == 1
                        and len(units) == 1
                        and set(graph.objects(nodes[0], WB.quantityAmount)) == {value}
                    )
                    qualifiers = any(
                        str(p).startswith(BASE + "prop/qualifier/")
                        for p in graph.predicates(statement)
                    )
                    ranks = set(graph.objects(statement, WB.rank))
                    rows.append(
                        {
                            "statement": str(statement),
                            "subject": str(subject),
                            "property_id": pid,
                            "label": spec["label"],
                            "value": str(value),
                            "unit_uri": str(unit) if unit else None,
                            "value_id": (
                                str(value).removeprefix(str(KB))
                                if isinstance(value, URIRef)
                                and str(value).startswith(str(KB))
                                else None
                            ),
                            "replaceable": not qualifiers
                            and ranks == {WB.NormalRank}
                            and len(values) == 1
                            and quantity_ok,
                        }
                    )
    return rows


def same_value(stored, value):
    if isinstance(value, Literal) and value.datatype == XSD.decimal:
        try:
            return Decimal(stored) == Decimal(str(value))
        except InvalidOperation:
            return False
    return stored == str(value)


def next_ids(graph):
    """Allocate unused local numeric QIDs above those already present in the graph."""
    highest = max(
        (
            int(str(s)[len(str(KB)) + 1 :])
            for s in graph.all_nodes()
            if re.fullmatch(re.escape(str(KB)) + r"Q[1-9][0-9]*", str(s))
        ),
        default=0,
    )
    while True:
        highest += 1
        yield KB["Q" + str(highest)]


def add_statement(
    graph, subject, pid, value, unit, evidence, operation, source, manual
):
    """Attach direct and full statement triples, quantity metadata and review evidence."""
    statement = URIRef(
        BASE + "entity/statement/" + subject.split("/")[-1] + "-" + uuid.uuid4().hex
    )
    graph.add((subject, predicate("", pid), statement))
    graph.add((subject, predicate("direct/", pid), value))
    graph.add((statement, predicate("statement/", pid), value))
    graph.add((statement, WB.rank, WB.NormalRank))
    graph.add((statement, RDF.type, WB.BestRank))
    graph.add((statement, APP.operation, operation))
    reference = URIRef("urn:anywikia:reference:" + uuid.uuid4().hex)
    graph.add((statement, PROV.wasDerivedFrom, reference))
    graph.add((reference, APP.sourceText, Literal(source)))
    graph.add((reference, APP.evidence, Literal(evidence)))
    graph.add(
        (
            reference,
            APP.entryKind,
            Literal("manual" if manual else "reviewed extraction"),
        )
    )
    if unit is not None:
        node = URIRef(BASE + "value/" + uuid.uuid4().hex)
        graph.add((statement, predicate("statement/value/", pid), node))
        graph.add((node, RDF.type, WB.QuantityValue))
        graph.add((node, WB.quantityAmount, value))
        graph.add((node, WB.quantityUnit, unit))
    return statement


def build_change(graph, request, operation_id):
    """Build a new graph and human-readable plan without modifying the input."""
    if not request.confirmed:
        raise ValueError(
            "Confirm the matched entity or confirm creation before previewing changes."
        )
    name = request.name.strip()
    if not name:
        raise ValueError("Entity name cannot be blank.")
    updated = Graph()
    for triple in graph:
        updated.add(triple)
    identifiers = next_ids(graph)
    new = request.mode == "new"
    if new:
        if request.target_id:
            raise ValueError("A new entity must not have an existing target ID.")
        names = {name.casefold(), *(a.strip().casefold() for a in request.aliases)}
        if "" in names:
            raise ValueError("Aliases cannot be blank.")
        for p in (RDFS.label, SKOS.altLabel):
            for s, label in graph.subject_objects(p):
                if (
                    str(s).startswith(str(KB) + "Q")
                    and str(label).strip().casefold() in names
                ):
                    raise ValueError(
                        f"A matching name or alias already exists: {s}. Review that entity first."
                    )
        target = next(identifiers)
        updated.add((target, RDFS.label, Literal(name, lang="en")))
        updated.add((target, RDF.type, APP.Keyboard))
        for alias in request.aliases:
            if len(alias) > 250:
                raise ValueError("Alias is too long.")
            updated.add((target, SKOS.altLabel, Literal(alias.strip(), lang="en")))
    else:
        target = entity_uri(request.target_id)
        if not any(graph.triples((target, RDFS.label, None))):
            raise ValueError(
                "The confirmed entity does not exist in the working graph."
            )
        if not any(str(label) == name for label in graph.objects(target, RDFS.label)):
            raise ValueError(
                "The reviewed name changed after matching. Confirm the entity again."
            )
    operation = URIRef("urn:anywikia:operation:" + operation_id)
    available = {r["statement"]: r for r in records(graph, target)}
    replaced = set()
    summary = []
    created_values = {}
    for claim in request.claims:
        pid = claim.property_id
        if claim.create_value_entity:
            spec = next(
                (p for p in property_catalog() if p["property_id"] == pid), None
            )
            if not spec or spec["value_type"] != "WikibaseItem":
                raise ValueError(
                    "Only entity-valued properties can create a value entity."
                )
            label = claim.value.strip()
            if (
                not claim.value_confirmed
                or claim.value_id
                or not 1 <= len(label) <= 250
            ):
                raise ValueError(
                    f"{spec['label']}: explicitly confirm a new value entity with a name (1–250 characters)."
                )
            key = label.casefold()
            if key not in created_values:
                for pred in (RDFS.label, SKOS.altLabel):
                    for subject_, existing in updated.subject_objects(pred):
                        if (
                            str(subject_).startswith(str(KB) + "Q")
                            and str(existing).strip().casefold() == key
                        ):
                            raise ValueError(
                                f"{spec['label']}: '{label}' already has a local entity ({subject_}). Search and confirm it instead."
                            )
                value_entity = next(identifiers)
                created_values[key] = value_entity
                updated.add((value_entity, RDFS.label, Literal(label, lang="en")))
                updated.add((value_entity, RDF.type, APP.ValueEntity))
                updated.add((value_entity, APP.operation, operation))
                summary.append(
                    {
                        "property": pid,
                        "action": "create value entity",
                        "value": label,
                        "unit": None,
                        "subject": str(value_entity).removeprefix(str(KB)),
                    }
                )
            claim = claim.model_copy(
                update={"value_id": str(created_values[key]).removeprefix(str(KB))}
            )
        value, unit = value_terms(claim, updated)
        subject = target
        if claim.action == "replace":
            row = available.get(claim.statement)
            if new or not row or row["property_id"] != pid or not row["replaceable"]:
                raise ValueError(
                    "Choose an editable stored statement of this property to replace. Qualified or specially ranked statements require separate handling."
                )
            if claim.statement in replaced:
                raise ValueError(
                    "The same stored statement cannot be replaced twice in one save."
                )
            replaced.add(claim.statement)
            subject = URIRef(row["subject"])
        # Don't corrupt truthy direct triples when preferred/deprecated ranks exist.
        for statement in graph.objects(subject, predicate("", pid)):
            if set(graph.objects(statement, WB.rank)) != {WB.NormalRank}:
                raise ValueError(
                    "This property has non-normal ranks; automatic changes are not supported."
                )
        current = records(updated, target)
        duplicate = next(
            (
                r
                for r in current
                if r["property_id"] == pid
                and same_value(r["value"], value)
                and r["unit_uri"] == (str(unit) if unit else None)
                and (
                    pid != "P25"
                    or any(
                        str(e) == claim.evidence
                        for ref in updated.objects(
                            URIRef(r["statement"]), PROV.wasDerivedFrom
                        )
                        for e in updated.objects(ref, APP.evidence)
                    )
                )
            ),
            None,
        )
        if claim.action == "add" and duplicate:
            summary.append(
                {
                    "property": pid,
                    "action": "already exists",
                    "value": str(value),
                    "unit": claim.unit,
                }
            )
            continue
        if claim.action == "replace":
            statement = URIRef(claim.statement)
            old_value = graph.value(statement, predicate("statement/", pid))
            updated.remove((subject, predicate("", pid), statement))
            updated.remove((statement, None, None))
            # Leave shared value/reference nodes intact. Other statements may use them.
            other_values = {
                v
                for st in updated.objects(subject, predicate("", pid))
                for v in updated.objects(st, predicate("statement/", pid))
            }
            if old_value not in other_values:
                updated.remove((subject, predicate("direct/", pid), old_value))
        elif pid == "P25":
            subject = next(identifiers)
            updated.add((subject, RDF.type, APP.Offer))
            updated.add(
                (subject, RDFS.label, Literal("Reviewed offer for " + name, lang="en"))
            )
            add_statement(
                updated,
                subject,
                "P24",
                target,
                None,
                claim.evidence,
                operation,
                request.source,
                claim.manual,
            )
        add_statement(
            updated,
            subject,
            pid,
            value,
            unit,
            claim.evidence,
            operation,
            request.source,
            claim.manual,
        )
        summary.append(
            {
                "property": pid,
                "action": claim.action,
                "value": str(value),
                "unit": claim.unit,
                "subject": str(subject).split("/")[-1],
                "replaces": claim.statement,
            }
        )
    updated.add((operation, RDF.type, APP.ConfirmedChange))
    updated.add((operation, APP.target, target))
    updated.add(
        (
            operation,
            PROV.generatedAtTime,
            Literal(datetime.now(timezone.utc).isoformat(), datatype=XSD.dateTime),
        )
    )
    return updated, str(target).split("/")[-1], summary


class RDFStore:
    """Coordinate previews, idempotent writes and verification against one runtime."""

    def __init__(self, runtime):
        self.runtime = runtime

    def inspect(self, qid):
        """Return the entity label, stored statement choices and current graph revision."""
        target = entity_uri(qid)
        graph = self.runtime.snapshot()
        if not any(graph.triples((target, None, None))):
            raise ValueError("No such entity in the working graph.")
        return {
            "id": qid,
            "name": display_name(graph, target),
            "statements": records(graph, target),
            "revision": revision(graph),
        }

    def search(self, text):
        """Return local entity candidates matching a name, alias or QID."""
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 250:
            raise ValueError("Enter a name or local QID to search.")
        needle = text.strip().casefold()
        graph = self.runtime.snapshot()
        found = {}
        for p in (RDFS.label, SKOS.altLabel):
            for subject, label in graph.subject_objects(p):
                qid = str(subject).removeprefix(str(KB))
                if re.fullmatch(r"Q[1-9][0-9]*", qid) and (
                    needle in str(label).casefold() or needle == qid.casefold()
                ):
                    found[qid] = {
                        "id": qid,
                        "name": str(graph.value(subject, RDFS.label) or label),
                    }
        return sorted(
            found.values(), key=lambda r: (r["name"].casefold() != needle, r["name"])
        )[:30]

    def preview(self, payload):
        """Validate a request and persist exact RDF deltas without applying them."""
        request = WriteRequest.model_validate(payload)
        with self.runtime.exclusive():
            self.runtime.assert_ready()
            graph = self.runtime.snapshot()
            preview_id = uuid.uuid4().hex
            changed, qid, summary = build_change(graph, request, preview_id)
            additions, deletions = set(changed) - set(graph), set(graph) - set(changed)
            record = {
                "id": preview_id,
                "created": time.time(),
                "status": "preview",
                "target": qid,
                "revision": revision(graph),
                "additions": triples_text(additions),
                "deletions": triples_text(deletions),
                "summary": summary,
                "request": request.model_dump(),
            }
            atomic_json(self.runtime.root / "changes" / (preview_id + ".json"), record)
            return {
                "preview_id": preview_id,
                "entity_id": qid,
                "summary": summary,
                "new_entity": request.mode == "new",
                "expires_in_seconds": 900,
            }

    def commit(self, preview_id, confirmed):
        """Apply one approved preview, or verify its operation marker on retry."""
        if (
            confirmed is not True
            or not isinstance(preview_id, str)
            or not re.fullmatch(r"[a-f0-9]{32}", preview_id)
        ):
            raise ValueError("Confirm a valid server-generated preview first.")
        with self.runtime.exclusive():
            self.runtime.assert_ready()
            path = self.runtime.root / "changes" / (preview_id + ".json")
            if not path.exists():
                raise ValueError("Preview not found. Prepare it again.")
            record = json.loads(path.read_text(encoding="utf-8"))
            graph = self.runtime.snapshot()
            additions = set(Graph().parse(data=record["additions"], format="nt"))
            deletions = set(Graph().parse(data=record["deletions"], format="nt"))
            operation = URIRef("urn:anywikia:operation:" + preview_id)
            if (operation, RDF.type, APP.ConfirmedChange) in graph:
                # Never reapply an already executed operation, even if later edits superseded it.
                report = verification_report(additions, deletions, graph)
                record["verification"] = report
                record["status"] = (
                    "committed" if report["verified"] else "applied_unverified"
                )
                atomic_json(path, record)
                return {
                    "status": "already_applied",
                    "entity_id": record["target"],
                    "operation_id": preview_id,
                    **report,
                }
            if record["status"] == "committed":
                raise ValueError(
                    "The graph no longer contains this committed change. Inspect it before making a new preview."
                )
            if time.time() - record["created"] > 900 and record["status"] == "preview":
                raise ValueError(
                    "Preview expired; review the current graph and preview again."
                )
            if revision(graph) != record["revision"]:
                raise ValueError(
                    "The graph changed after this preview. Refresh stored values and preview again."
                )
            sparql = f"DELETE {{ {record['deletions']} }} INSERT {{ {record['additions']} }} WHERE {{ }}"
            record["status"] = "submitted"
            atomic_json(path, record)
            update_error = None
            try:
                self.runtime.update(sparql)
            except Exception as error:
                update_error = error
            try:
                after = self.runtime.snapshot()
                report = verification_report(additions, deletions, after)
            except Exception as error:
                after = Graph()
                report = {"verified": False, "read_error": type(error).__name__}
            verified = report["verified"]
            record["verification"] = report
            if not verified and (operation, RDF.type, APP.ConfirmedChange) in after:
                record["status"] = "applied_unverified"
                atomic_json(path, record)
                return {
                    "status": "applied_unverified",
                    "entity_id": record["target"],
                    "operation_id": preview_id,
                    **report,
                }
            if not verified:
                record["status"] = "uncertain"
                atomic_json(path, record)
                raise RuntimeError(
                    "Update status uncertain. Use Verify or retry this same confirmation; do not create another entity. "
                    + (
                        "QLever did not acknowledge the request."
                        if update_error
                        else "Read-back verification failed."
                    )
                )
            record["status"] = "committed"
            atomic_json(path, record)
            return {
                "status": "updated",
                "verified": True,
                "entity_id": record["target"],
                "operation_id": preview_id,
            }

    def verify_query(self, qid, pid=None):
        """Generate and execute a safe entity/property SELECT with display labels."""
        target = entity_uri(qid)
        allowed = {p["property_id"] for p in property_catalog()}
        if pid is not None and pid not in allowed:
            raise ValueError("Unsupported verification property.")
        # Query templates only. No browser-provided SPARQL or credential is forwarded.
        property_filter = f"FILTER(?property = {KB[pid].n3()})" if pid else ""
        query = f"""PREFIX kb: <{KB}>
PREFIX kbt: <{BASE}prop/direct/>
PREFIX wb: <{WB}>
PREFIX rdfs: <{RDFS}>
SELECT DISTINCT ?subject ?subjectLabel ?property ?propertyLabel ?value ?valueLabel ?unit WHERE {{
 {{ BIND({target.n3()} AS ?subject) ?subject ?predicate ?value . }}
 UNION {{ ?subject kbt:P24 {target.n3()} ; kbt:P25 ?value . BIND(kbt:P25 AS ?predicate) }}
 ?property wb:directClaim ?predicate . {property_filter}
 OPTIONAL {{ ?subject rdfs:label ?subjectLabel . FILTER(LANG(?subjectLabel) = "en") }}
 OPTIONAL {{ ?property rdfs:label ?propertyLabel . FILTER(LANG(?propertyLabel) = "en") }}
 OPTIONAL {{ ?value rdfs:label ?valueLabel . FILTER(LANG(?valueLabel) = "en") }}
 OPTIONAL {{ ?property wb:claim ?cp ; wb:statementProperty ?sp ; wb:statementValue ?vp .
 ?subject ?cp ?statement . ?statement ?sp ?value ; ?vp ?node . ?node wb:quantityUnit ?unit . }}
}} LIMIT 200"""
        return {"query": query, "results": self.runtime.query(query)}
