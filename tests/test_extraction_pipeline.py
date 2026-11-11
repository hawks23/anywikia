"""Offline regression checks: source facts survive linking unchanged."""
# Support direct execution from tests/ as well as unittest discovery.
import sys
from pathlib import Path
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


import unittest
import io
import json
from contextlib import redirect_stdout
from unittest.mock import patch
from functions import extract_input, resolve_local
from functions import qlever_checks, display_results
import handler
import httpx


def fact(**changes):
    return dict(subject="Yamaha P-150", property="width", value="999",
                unit="cm", evidence="The Yamaha P-150 has a width of 999 cm.", **changes)


class PipelineTests(unittest.TestCase):
    def test_handler_runs_steps_in_order(self):
        calls = []
        source = fact()
        with patch.object(handler, 'check_server', side_effect=lambda: calls.append('server')), \
             patch.object(handler, 'check_dataset', side_effect=lambda: calls.append('data')), \
             patch.object(handler, 'extract_entities', side_effect=lambda text: (calls.append('extract') or {'items': [source]})), \
             patch.object(handler, 'extract_ids', side_effect=lambda item: (calls.append('resolve') or dict(item))):
            self.assertEqual(handler.run_pipeline(source['evidence']), [source])
        self.assertEqual(calls, ['server', 'data', 'extract', 'resolve'])

    def test_preflight_failure_prevents_llm_call(self):
        with patch.object(handler, 'check_server', side_effect=ValueError('offline')), \
             patch.object(handler, 'extract_entities') as extract:
            with self.assertRaises(ValueError):
                handler.run_pipeline('source')
            extract.assert_not_called()

    def test_lookup_failure_keeps_source_fact(self):
        source = fact()
        with patch.object(handler, 'check_server'), patch.object(handler, 'check_dataset'), \
             patch.object(handler, 'extract_entities', return_value={'items': [source]}), \
             patch.object(handler, 'extract_ids', side_effect=httpx.ConnectError('offline')):
            result = handler.run_pipeline(source['evidence'])[0]
        self.assertEqual({key: result[key] for key in source}, source)
        self.assertIsNone(result['subject_id'])
        self.assertTrue(result['warnings'])

    def test_empty_dataset_check_fails(self):
        response = httpx.Response(200, json={'boolean': False},
                                  request=httpx.Request('POST', 'http://localhost'))
        with patch.object(qlever_checks.httpx, 'post', return_value=response):
            with self.assertRaisesRegex(ValueError, 'not found'):
                qlever_checks.check_dataset()

    def test_bad_server_response_fails(self):
        response = httpx.Response(200, json={'results': {'bindings': []}},
                                  request=httpx.Request('POST', 'http://localhost'))
        with patch.object(qlever_checks.httpx, 'post', return_value=response):
            with self.assertRaises(ValueError):
                qlever_checks.check_server()

    def test_json_display_preserves_values(self):
        source = fact()
        stream = io.StringIO()
        with redirect_stdout(stream):
            display_results.print_results([source], as_json=True)
        self.assertEqual(json.loads(stream.getvalue()), [source])

    def test_source_value_and_unit_are_not_replaced_by_database(self):
        source = fact()
        with patch.object(resolve_local, "search_local", side_effect=[
            [{"id": "Q1", "type": None}],
            [{"id": "P2", "type": "http://wikiba.se/ontology#Quantity"}],
        ]) as search:
            result = resolve_local.extract_ids(source)
        self.assertEqual({key: result[key] for key in source}, source)
        self.assertEqual(result['subject_id'], 'Q1')
        self.assertEqual(result['property_id'], 'P2')
        self.assertEqual(search.call_count, 2)

    def test_ambiguous_and_missing_ids_preserve_fact(self):
        source = fact()
        with patch.object(resolve_local, 'search_local', side_effect=[
            [{'id': 'Q1'}, {'id': 'Q2'}], []]):
            result = resolve_local.extract_ids(source)
        self.assertIsNone(result['subject_id'])
        self.assertIsNone(result['property_id'])
        self.assertEqual(len(result['warnings']), 2)
        self.assertEqual(result['evidence'], source['evidence'])

    def test_entity_value_is_linked_without_replacing_name(self):
        source = fact()
        source.update(property='manufacturer', value='Yamaha', unit=None)
        with patch.object(resolve_local, 'search_local', side_effect=[
            [{'id': 'Q1', 'type': None}],
            [{'id': 'P6', 'type': 'http://wikiba.se/ontology#WikibaseItem'}],
            [{'id': 'Q2', 'type': None}]]):
            result = resolve_local.extract_ids(source)
        self.assertEqual(result['value_id'], 'Q2')
        self.assertEqual(result['value'], 'Yamaha')

    def test_fabricated_evidence_is_rejected(self):
        output = extract_input.EntityList(items=[extract_input.Entity(**fact())])
        with patch.object(extract_input, 'structured_completion', return_value=output):
            with self.assertRaisesRegex(ValueError, 'exact quote'):
                extract_input.extract_entities('This source gives no dimensions.')

    def test_exact_source_evidence_is_accepted(self):
        source = fact()
        output = extract_input.EntityList(items=[extract_input.Entity(**source)])
        with patch.object(extract_input, 'structured_completion', return_value=output):
            self.assertEqual(extract_input.extract_entities(source['evidence'])['items'], [source])


if __name__ == '__main__':
    unittest.main()
