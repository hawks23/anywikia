"""Offline regression checks: source facts survive linking unchanged."""
import unittest
from unittest.mock import patch
import extract_input
import resolve_local


def fact(**changes):
    return dict(subject="Yamaha P-150", property="width", value="999",
                unit="cm", evidence="The Yamaha P-150 has a width of 999 cm.", **changes)


class PipelineTests(unittest.TestCase):
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
