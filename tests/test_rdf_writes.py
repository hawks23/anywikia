"""Exercise real RDF construction and SPARQL updates offline, including retries."""
import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from rdflib import Graph, Literal, RDF, RDFS, SKOS, URIRef, XSD
from rdflib.compare import isomorphic

from functions.rdf_models import APP, BASE, KB, WB, ClaimEdit, WriteRequest, value_terms, property_catalog
from functions.rdf_store import RDFStore, add_statement, build_change, predicate, records


def fixture():
    graph = Graph()
    for spec in property_catalog():
        pid = spec["property_id"]
        graph.add((KB[pid], WB.propertyType, WB[spec["value_type"]]))
        for attr, kind in [("directClaim", "direct/"), ("claim", ""), ("statementProperty", "statement/"), ("statementValue", "statement/value/")]:
            graph.add((KB[pid], WB[attr], predicate(kind, pid)))
    # Price's offer relationship is deliberately not in the user property dropdown.
    graph.add((KB.P24, WB.directClaim, predicate("direct/", "P24")))
    graph.add((KB.Q1, RDFS.label, Literal("Keyboard", lang="en")))
    graph.add((KB.Q2, RDFS.label, Literal("Maker", lang="en")))
    graph.add((KB.Q1, SKOS.altLabel, Literal("P150", lang="en")))
    return graph


def payload(**changes):
    return dict(mode="existing", target_id="Q1", name="Keyboard", confirmed=True,
                claims=[dict(property_id="P2", value="100", unit="cm", evidence="Width is 100 cm.")], **changes)


class MemoryRuntime:
    def __init__(self, root, graph=None):
        self.root = Path(root); self.graph = fixture() if graph is None else graph
        self.updates = 0; self.fail_after_write = False; self.fail_before_write = False
    @contextmanager
    def exclusive(self):
        yield
    def assert_ready(self):
        pass
    def snapshot(self, endpoint=None):
        graph = Graph()
        for triple in self.graph: graph.add(triple)
        return graph
    def update(self, sparql):
        if self.fail_before_write: raise TimeoutError("offline")
        self.updates += 1
        self.graph.update(sparql)
        if self.fail_after_write: raise TimeoutError("response lost")
    def query(self, query):
        return json.loads(self.graph.query(query).serialize(format="json"))


class RDFWriteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runtime = MemoryRuntime(self.temp.name)
        self.store = RDFStore(self.runtime)

    def save(self, request):
        preview = self.store.preview(request)
        return self.store.commit(preview["preview_id"], True)

    def test_new_keyboard_and_new_color_get_distinct_automatic_ids(self):
        data = payload()
        data.update(mode="new", target_id=None, name="New keyboard")
        data['claims'].append(dict(property_id='P9', value='Maroon', create_value_entity=True, value_confirmed=True))
        preview = self.store.preview(data)
        self.assertEqual(preview['entity_id'], 'Q3')
        self.assertTrue(any(row['action'] == 'create value entity' and row['subject'] == 'Q4' for row in preview['summary']))
        self.store.commit(preview['preview_id'], True)
        self.store.commit(preview['preview_id'], True)
        self.assertIn((KB.Q3, predicate('direct/', 'P9'), KB.Q4), self.runtime.graph)
        self.assertIn((KB.Q4, RDFS.label, Literal('Maroon', lang='en')), self.runtime.graph)
        self.assertEqual(self.runtime.updates, 1)

    def test_new_value_rejects_existing_name_and_requires_confirmation(self):
        data = payload()
        data['claims'] = [dict(property_id='P6', value='Maker', create_value_entity=True, value_confirmed=True)]
        with self.assertRaisesRegex(ValueError, 'already has a local entity'):
            self.store.preview(data)
        data['claims'][0].update(value='New maker', value_confirmed=False)
        with self.assertRaisesRegex(ValueError, 'explicitly confirm'):
            self.store.preview(data)
        self.assertEqual(self.runtime.updates,0)

    def test_missing_color_id_identifies_property_in_error(self):
        data = payload(); data['claims'] = [dict(property_id='P9', value='Maroon')]
        with self.assertRaisesRegex(ValueError, "color: 'Maroon'.*keyboard ID is generated automatically"):
            self.store.preview(data)

    def test_confirm_refreshes_entity_json_with_labels_and_aliases(self):
        from functions import rdf_service
        self.runtime.graph.add((KB.Q2,RDFS.label,Literal('Producent',lang='da')))
        data = payload(); data.update(mode='new',target_id=None,name='New keyboard',aliases=['New KB'])
        preview = self.store.preview(data)
        with patch.object(rdf_service,'runtime',self.runtime), patch.object(rdf_service,'store',self.store):
            result = rdf_service.confirm_change({'preview_id':preview['preview_id'],'confirmed':True})
        catalog = json.loads((self.runtime.root/'entity_list.json').read_text())['entities']
        self.assertTrue(result['verified'])
        self.assertIn({'id':'Q3','name':'New keyboard','aliases':['New KB']},catalog)
        self.assertEqual(next(row['name'] for row in catalog if row['id']=='Q2'),'Maker')

    def test_catalog_failure_does_not_misreport_successful_rdf_write(self):
        from functions import rdf_service
        preview = self.store.preview(payload())
        with patch.object(rdf_service,'runtime',self.runtime), patch.object(rdf_service,'store',self.store), patch('functions.entity_catalog.write_entity_catalog',side_effect=OSError('disk full')):
            result = rdf_service.confirm_change({'preview_id':preview['preview_id'],'confirmed':True})
        self.assertTrue(result['verified'])
        self.assertIn('entity_list_warning',result)

    def test_add_persists_complete_quantity_and_verifies(self):
        result = self.save(payload())
        self.assertTrue(result["verified"])
        row = records(self.runtime.graph, KB.Q1)[0]
        self.assertEqual(row["unit_uri"], "http://www.wikidata.org/entity/Q174728")
        self.assertIn((KB.Q1, predicate("direct/", "P2"), Literal("100", datatype=XSD.decimal)), self.runtime.graph)
        self.assertEqual(len(self.store.verify_query("Q1", "P2")["results"]["results"]["bindings"]), 1)

    def test_explicit_confirmation_required_twice(self):
        data = payload(); data["confirmed"] = False
        with self.assertRaises(ValueError): self.store.preview(data)
        preview = self.store.preview(payload())
        with self.assertRaises(ValueError): self.store.commit(preview["preview_id"], False)
        self.assertEqual(self.runtime.updates, 0)

    def test_qlever_decimal_lexical_changes_verify_and_retry(self):
        snapshot = self.runtime.snapshot
        def qlever_snapshot(endpoint=None):
            graph = snapshot(endpoint)
            for subject, predicate_, value in list(graph):
                if isinstance(value, Literal) and value.datatype == XSD.decimal and '.' not in str(value):
                    graph.remove((subject, predicate_, value))
                    graph.add((subject, predicate_, Literal(str(value) + '.0', datatype=XSD.decimal)))
            return graph
        self.runtime.snapshot = qlever_snapshot
        preview = self.store.preview(payload())
        self.assertTrue(self.store.commit(preview['preview_id'], True)['verified'])
        self.assertTrue(self.store.commit(preview['preview_id'], True)['verified'])
        self.assertEqual(self.runtime.updates, 1)

    def test_verification_excludes_semantically_reinserted_direct_values(self):
        data = payload(); data['claims'][0]['value'] = '100.0'
        self.save(data)
        row = records(self.runtime.graph, KB.Q1)[0]
        data['claims'][0].update(value='100', unit='mm', action='replace', statement=row['statement'])
        self.assertTrue(self.save(data)['verified'])

    def test_verification_query_includes_entity_labels(self):
        self.save(payload())
        rows = self.store.verify_query('Q1')['results']['results']['bindings']
        self.assertEqual(rows[0]['subjectLabel']['value'], 'Keyboard')

    def test_explicit_xsd_string_readback_is_equivalent(self):
        snapshot = self.runtime.snapshot
        def typed_snapshot(endpoint=None):
            graph = snapshot(endpoint)
            for s, p, o in list(graph):
                if isinstance(o, Literal) and o.datatype is None and not o.language:
                    graph.remove((s,p,o)); graph.add((s,p,Literal(str(o),datatype=XSD.string)))
            return graph
        self.runtime.snapshot = typed_snapshot
        self.assertTrue(self.save(payload())['verified'])

    def test_recorded_update_with_missing_metadata_reports_difference_without_reapplying(self):
        update = self.runtime.update
        def incomplete_update(sparql):
            update(sparql)
            self.runtime.graph.remove((None, APP.evidence, None))
        self.runtime.update = incomplete_update
        preview = self.store.preview(payload())
        result = self.store.commit(preview['preview_id'], True)
        self.assertEqual(result['status'], 'applied_unverified')
        self.assertFalse(result['verified'])
        self.assertIn(str(APP.evidence),result['mismatched_predicates'])
        self.store.commit(preview['preview_id'], True)
        self.assertEqual(self.runtime.updates,1)

    def test_equivalent_decimal_add_is_not_duplicated(self):
        self.save(payload())
        data = payload()
        data['claims'][0]['value'] = '100.00'
        self.save(data)
        self.assertEqual(len(records(self.runtime.graph, KB.Q1)), 1)

    def test_ambiguous_quantity_cannot_be_replaced(self):
        self.save(payload())
        row = records(self.runtime.graph, KB.Q1)[0]
        node = self.runtime.graph.value(URIRef(row['statement']), predicate('statement/value/', 'P2'))
        self.runtime.graph.add((node, WB.quantityUnit, URIRef('http://www.wikidata.org/entity/Q11573')))
        data = payload()
        data['claims'][0].update(action='replace', statement=row['statement'])
        with self.assertRaisesRegex(ValueError, 'editable'):
            self.store.preview(data)

    def test_entity_properties_reject_measurement_units(self):
        claim = ClaimEdit(property_id='P6', value='Maker', value_id='Q2', value_confirmed=True, unit='cm')
        with self.assertRaisesRegex(ValueError, 'does not take a unit'):
            value_terms(claim, self.runtime.graph)

    def test_new_entity_and_price_linked_offer(self):
        data = payload(); data.update(mode="new", target_id=None, name="New keyboard")
        data["claims"] += [dict(property_id="P25", value="500.00", unit="EUR", evidence="Shop offer")]
        saved = self.save(data); target = KB[saved["entity_id"]]
        self.assertIn((target, RDF.type, APP.Keyboard), self.runtime.graph)
        offers = list(self.runtime.graph.subjects(predicate("direct/", "P24"), target))
        self.assertEqual(len(offers), 1)
        self.assertFalse(list(self.runtime.graph.objects(target, predicate("direct/", "P25"))))
        self.assertEqual(len(self.store.verify_query(saved["entity_id"], "P25")["results"]["results"]["bindings"]), 1)

    def test_replace_one_statement_preserves_another(self):
        self.save(payload())
        data = payload(); data["claims"][0]["value"] = "200"; self.save(data)
        rows = records(self.runtime.graph, KB.Q1)
        selected = next(r for r in rows if r["value"] == "100")
        data["claims"][0].update(action="replace", statement=selected["statement"], value="150")
        self.save(data)
        self.assertEqual({r["value"] for r in records(self.runtime.graph, KB.Q1)}, {"150", "200"})
        self.assertEqual({str(v) for v in self.runtime.graph.objects(KB.Q1, predicate("direct/", "P2"))}, {"150", "200"})

    def test_replacement_cannot_target_other_entity_or_qualified_statement(self):
        self.save(payload())
        row = records(self.runtime.graph, KB.Q1)[0]
        self.runtime.graph.add((URIRef(row["statement"]), predicate("qualifier/", "P26"), Literal("2026")))
        data = payload(); data["claims"][0].update(action="replace", statement=row["statement"])
        with self.assertRaisesRegex(ValueError, "editable"): self.store.preview(data)

    def test_stale_preview_does_not_overwrite(self):
        preview = self.store.preview(payload())
        self.runtime.graph.add((KB.Q2, SKOS.altLabel, Literal("changed")))
        with self.assertRaisesRegex(ValueError, "changed after"): self.store.commit(preview["preview_id"], True)
        self.assertEqual(self.runtime.updates, 0)

    def test_lost_response_and_duplicate_confirmation_are_idempotent(self):
        preview = self.store.preview(payload()); self.runtime.fail_after_write = True
        first = self.store.commit(preview["preview_id"], True)
        second = self.store.commit(preview["preview_id"], True)
        self.assertTrue(first["verified"] and second["verified"])
        self.assertEqual(self.runtime.updates, 1)

    def test_failure_before_update_can_retry_same_preview(self):
        preview = self.store.preview(payload()); self.runtime.fail_before_write = True
        with self.assertRaisesRegex(RuntimeError, "uncertain"): self.store.commit(preview["preview_id"], True)
        self.runtime.fail_before_write = False
        self.assertTrue(self.store.commit(preview["preview_id"], True)["verified"])

    def test_repeated_add_does_not_duplicate_statements(self):
        self.save(payload()); self.save(payload())
        self.assertEqual(len(records(self.runtime.graph, KB.Q1)), 1)

    def test_multiline_evidence_and_sparql_injection_remain_literals(self):
        text = 'Quoted "text"\n }; DELETE WHERE { ?s ?p ?o }; #'
        data = payload(); data["source"] = text; data["claims"][0]["evidence"] = text
        self.save(data)
        self.assertIn((KB.Q2, RDFS.label, Literal("Maker", lang="en")), self.runtime.graph)
        self.assertTrue(list(self.runtime.graph.subjects(APP.evidence, Literal(text))))

    def test_duplicate_alias_creation_rejected(self):
        data = payload(); data.update(mode="new", target_id=None, name="p150")
        with self.assertRaisesRegex(ValueError, "already exists"): self.store.preview(data)

    def test_model_never_mutates_original_graph(self):
        before = self.runtime.snapshot()
        build_change(self.runtime.graph, WriteRequest.model_validate(payload()), "test")
        self.assertTrue(isomorphic(before, self.runtime.graph))

    def test_entity_value_requires_confirmed_existing_qid(self):
        data = payload(); data["claims"] = [dict(property_id="P6", value="Maker", value_id="Q2")]
        with self.assertRaisesRegex(ValueError, "confirm"): self.store.preview(data)
        data["claims"][0]["value_confirmed"] = True
        self.save(data)
        self.assertIn((KB.Q1, predicate("direct/", "P6"), KB.Q2), self.runtime.graph)

    def test_unit_dimension_datatype_and_range_validation(self):
        for pid, value, unit in [("P2","10","kg"),("P7","10","cm"),("P1","1.5",None),("P1","-1",None),("P2","NaN","mm"),("P2","0","mm"),("P25","10","JPY"),("P16","Infinity","W"),("P1","12","kg")]:
            with self.subTest(pid=pid,value=value,unit=unit), self.assertRaises(ValueError):
                value_terms(ClaimEdit(property_id=pid,value=value,unit=unit), self.runtime.graph)

    def test_url_id_media_validation(self):
        for pid, value in [("P5","javascript:alert(1)"),("P17","123"),("P18","https://example.org/image.png")]:
            with self.subTest(pid=pid), self.assertRaises(ValueError):
                value_terms(ClaimEdit(property_id=pid,value=value), self.runtime.graph)

    def test_verification_query_rejects_injection(self):
        with self.assertRaises(ValueError): self.store.verify_query("Q1 } DELETE WHERE {}")
        with self.assertRaises(ValueError): self.store.verify_query("Q1", "P2 } UNION {}")

    def test_server_restart_can_finish_persisted_preview(self):
        preview = self.store.preview(payload())
        restarted = RDFStore(self.runtime)
        self.assertTrue(restarted.commit(preview["preview_id"], True)["verified"])


if __name__ == "__main__": unittest.main()
