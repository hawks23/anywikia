"""Targeted inspection must preserve editing decisions without a full snapshot."""
import unittest
from unittest.mock import patch

from rdflib import Literal, RDFS, URIRef

from functions.rdf_models import KB, WB, PROV
from functions.rdf_store import add_statement, predicate, records
from tests import test_rdf_writes as fixtures
from tests.test_rdf_writes import payload


class EntityInspectionTests(unittest.TestCase):
    setUp = fixtures.RDFWriteTests.setUp
    save = fixtures.RDFWriteTests.save
    def test_scoped_inspection_preserves_statements_and_excludes_other_entities(self):
        self.save(payload())
        self.save(dict(mode="existing", target_id="Q1", name="Keyboard", confirmed=True,
                       claims=[dict(property_id="P25", value="900", unit="EUR", evidence="Offer")]))
        graph = self.runtime.graph
        statement = next(graph.objects(KB.Q1, predicate("", "P2")))
        graph.add((statement, predicate("qualifier/", "P1"), Literal(1)))
        graph.add((KB.Q999, RDFS.label, Literal("Unrelated")))
        add_statement(graph, KB.Q999, "P2", Literal(500), KB.Q2, "Other", URIRef("urn:other"), "Other", False)
        expected = records(graph, KB.Q1)
        queries = []
        returned = []
        query = self.runtime.query

        def capture(sparql):
            queries.append(sparql)
            result = query(sparql)
            returned.extend(result["results"]["bindings"])
            return result

        with patch.object(self.runtime, "snapshot", side_effect=AssertionError("Full snapshot forbidden")), \
             patch.object(self.runtime, "query", side_effect=capture), \
             patch("functions.rdf_store.revision", side_effect=AssertionError("Global digest forbidden")):
            actual = self.store.inspect("Q1")
        self.assertEqual(len(queries), 1)
        self.assertEqual(actual["name"], "Keyboard")
        self.assertCountEqual(actual["statements"], expected)
        self.assertFalse(next(r for r in actual["statements"] if r["property_id"] == "P2")["replaceable"])
        self.assertTrue(any(r["property_id"] == "P25" for r in actual["statements"]))
        self.assertFalse(any(row["s"]["value"] == str(KB.Q999) for row in returned))
        self.assertTrue(any(row["p"]["value"] == str(PROV.wasDerivedFrom) for row in returned))

    def test_missing_and_invalid_entity(self):
        with self.assertRaisesRegex(ValueError, "No such entity"):
            self.store.inspect("Q999")
        with patch.object(self.runtime, "query") as query:
            with self.assertRaises(ValueError):
                self.store.inspect("Q1> ?s ?p ?o")
            query.assert_not_called()

    def test_ambiguous_quantity_stays_protected(self):
        self.save(payload())
        graph = self.runtime.graph
        statement = next(graph.objects(KB.Q1, predicate("", "P2")))
        node = next(graph.objects(statement, predicate("statement/value/", "P2")))
        graph.add((node, WB.quantityUnit, KB.Q2))
        self.assertCountEqual(self.store.inspect("Q1")["statements"], records(graph, KB.Q1))
        self.assertFalse(self.store.inspect("Q1")["statements"][0]["replaceable"])

    def test_oversized_result_is_rejected_instead_of_truncated(self):
        with patch.object(self.runtime, "query", return_value={"results": {"bindings": [{}] * 100001}}):
            with self.assertRaisesRegex(ValueError, "exceeds"):
                self.store.inspect("Q1")

    def test_repository_rdf_matches_full_graph_inspection(self):
        from local_rdf import RDF_PATH
        self.runtime.graph.parse(RDF_PATH, format="nt")
        for qid in ("Q1", "Q13", "Q34"):
            with self.subTest(qid=qid):
                self.assertCountEqual(
                    self.store.inspect(qid)["statements"],
                    records(self.runtime.graph, KB[qid]),
                )


