"""Grouped enrichment preserves source claims and avoids repeated subject queries."""
import io
import json
import unittest
from contextlib import redirect_stdout
from decimal import Decimal
from unittest.mock import patch, call

import httpx
import handler
from functions import resolve_local, pydantic_models, display_results
from functions.pydantic_models import Extraction


SOURCE = 'Yamaha P-150 is made by Yamaha, is 999 cm wide, and another note says 1000 cm.'


def extraction(name='Yamaha P-150'):
    return Extraction.model_validate({'entities': [{
        'name': name,
        'width': [{'value': '999', 'unit': 'cm', 'evidence': SOURCE},
                  {'value': '1000', 'unit': 'cm', 'evidence': SOURCE}],
        'manufacturer': [{'value': 'Yamaha', 'evidence': SOURCE}]}]})


class GroupedResolutionTests(unittest.TestCase):
    def test_resolves_subject_once_preserves_conflicts_and_source(self):
        original = extraction()
        before = original.model_dump()
        with patch.object(resolve_local, 'search_local', side_effect=[
            [{'id': 'Q1'}], [{'id': 'Q2'}]]) as search:
            result = resolve_local.resolve_extraction(original, SOURCE)
        self.assertEqual(search.call_args_list, [call('Yamaha P-150', 'item'), call('Yamaha', 'item')])
        entity = result.entities[0]
        self.assertEqual(entity.subject_id, 'Q1')
        self.assertEqual(entity.properties['width'].property_id, 'P2')
        self.assertEqual([c.value for c in entity.properties['width'].claims], [Decimal('999'), Decimal('1000')])
        self.assertTrue(all(c.unit == 'cm' and c.evidence == SOURCE for c in entity.properties['width'].claims))
        self.assertEqual(entity.properties['manufacturer'].claims[0].value_id, 'Q2')
        self.assertEqual(entity.properties['height'].claims, [])
        self.assertEqual(original.model_dump(), before)

    def test_ambiguous_candidates_retained_never_selected(self):
        with patch.object(resolve_local, 'search_local', return_value=[{'id': 'Q1'}, {'id': 'Q2'}]):
            entity = resolve_local.resolve_extraction(extraction(), SOURCE).entities[0]
        self.assertIsNone(entity.subject_id)
        self.assertEqual([c.id for c in entity.subject_candidates], ['Q1', 'Q2'])
        claim = entity.properties['manufacturer'].claims[0]
        self.assertIsNone(claim.value_id)
        self.assertEqual([c.id for c in claim.value_candidates], ['Q1', 'Q2'])
        self.assertTrue(claim.warnings)

    def test_value_lookup_failure_preserves_resolved_subject(self):
        with patch.object(resolve_local, 'search_local', side_effect=[
            [{'id': 'Q1'}], httpx.ConnectError('offline')]):
            entity = resolve_local.resolve_extraction(extraction(), SOURCE).entities[0]
        self.assertEqual(entity.subject_id, 'Q1')
        prop = entity.properties['manufacturer']
        self.assertEqual(prop.property_id, 'P6')
        self.assertEqual(prop.claims[0].value, 'Yamaha')
        self.assertTrue(prop.claims[0].warnings)

    def test_missing_names_do_not_discard_source(self):
        with patch.object(resolve_local, 'search_local', return_value=[]):
            entity = resolve_local.resolve_extraction(extraction(), SOURCE).entities[0]
        self.assertIsNone(entity.subject_id)
        self.assertTrue(entity.warnings)
        self.assertEqual(len(entity.properties['width'].claims), 2)

    def test_evidence_is_preserved_without_source_matching(self):
        with patch.object(resolve_local, 'search_local', return_value=[]) as search:
            result = resolve_local.resolve_extraction(extraction(), 'different source')
        self.assertTrue(search.called)
        self.assertEqual(result.entities[0].properties['width'].claims[0].evidence, SOURCE)

    def test_catalog_drift_fails_before_lookup(self):
        with patch.object(resolve_local, 'validate_mapped_property', side_effect=ValueError('catalog drift')), \
             patch.object(resolve_local, 'search_local') as search:
            with self.assertRaisesRegex(ValueError, 'catalog drift'):
                resolve_local.resolve_extraction(extraction(), SOURCE)
        search.assert_not_called()

    def test_pipeline_never_calls_flattening_and_serializes_grouped(self):
        with patch.object(handler, 'check_server'), patch.object(handler, 'check_dataset'), \
             patch.object(handler, 'extract_entities', return_value=extraction().model_dump(mode='json')), \
             patch.object(pydantic_models, 'to_claims', side_effect=AssertionError('must not flatten')), \
             patch.object(resolve_local, 'extract_ids', side_effect=AssertionError('must not flatten')), \
             patch.object(resolve_local, 'search_local', side_effect=[[{'id': 'Q1'}], [{'id': 'Q2'}]]):
            result = handler.run_pipeline(SOURCE)
        stream = io.StringIO()
        with redirect_stdout(stream):
            display_results.print_results(result, as_json=True)
        output = json.loads(stream.getvalue())
        self.assertEqual(output['entities'][0]['properties']['width']['claims'][0]['value'], '999')
        self.assertEqual(output['entities'][0]['subject_id'], 'Q1')

    def test_alias_records_are_not_merged_and_subject_lookups_are_cached(self):
        data = extraction()
        data.entities += [extraction('P150').entities[0], extraction().entities[0]]
        with patch.object(resolve_local, 'search_local', side_effect=lambda name, kind: [
            {'id': 'Q2' if name == 'Yamaha' else 'Q1'}]) as search:
            result = resolve_local.resolve_extraction(data, SOURCE)
        self.assertEqual(len(result.entities), 3)
        self.assertEqual([e.name for e in result.entities], ['Yamaha P-150', 'P150', 'Yamaha P-150'])
        self.assertEqual(search.call_count, 3)


if __name__ == '__main__':
    unittest.main()
