"""Offline checks for the typed extraction schema and compatibility conversion."""
import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError
from openai.lib._pydantic import to_strict_json_schema
from functions.pydantic_models import (
    Extraction, KeyboardExtraction, QuantityClaim, EntityClaim, TextClaim,
    PROPERTY_FIELDS, to_claims,
)


class ModelTests(unittest.TestCase):
    def test_decimal_precision_and_unit(self):
        claim = QuantityClaim(value="1385.00100", unit="mm", evidence="width 1385.00100 mm")
        self.assertIsInstance(claim.value, Decimal)
        result = to_claims(Extraction(entities=[KeyboardExtraction(name="P-150", width=[claim])]), claim.evidence)
        self.assertEqual(result['items'][0]['value'], '1385.00100')
        self.assertEqual(result['items'][0]['unit'], 'mm')

    def test_multiple_conflicting_claims_survive(self):
        source = 'It weighs 10 kg. Another note says 11 kg.'
        claims = [QuantityClaim(value='10', unit='kg', evidence='It weighs 10 kg.'),
                  QuantityClaim(value='11', unit='kg', evidence='Another note says 11 kg.')]
        result = to_claims(Extraction(entities=[KeyboardExtraction(name='Keyboard', weight=claims)]), source)
        self.assertEqual([r['value'] for r in result['items']], ['10', '11'])

    def test_absent_properties_and_units_are_not_invented(self):
        entity = KeyboardExtraction(name='Keyboard')
        self.assertEqual(to_claims(Extraction(entities=[entity]), 'Keyboard'), {'items': []})
        self.assertIsNone(QuantityClaim(value='88', unit=None, evidence='88').unit)

    def test_manufacturer_name_stays_string(self):
        claim = EntityClaim(value='Yamaha', evidence='Made by Yamaha.')
        result = to_claims(Extraction(entities=[KeyboardExtraction(name='P-150', manufacturer=[claim])]), claim.evidence)
        self.assertEqual(result['items'][0]['value'], 'Yamaha')
        self.assertIsNone(result['items'][0]['unit'])

    def test_invalid_quantities_and_unknown_fields_rejected(self):
        for value in ['wide', 'NaN', 'Infinity']:
            with self.assertRaises(ValidationError):
                QuantityClaim(value=value, unit=None, evidence='test')
        with self.assertRaises(ValidationError):
            KeyboardExtraction(name='Keyboard', seller=[])

    def test_model_fields_match_rdf_catalog(self):
        root = Path(__file__).resolve().parents[1]
        catalog = {p['property_id']: p for p in json.loads((root/'property_list.json').read_text())['properties']}
        self.assertEqual(set(KeyboardExtraction.model_fields) - {'name'}, set(PROPERTY_FIELDS))
        for field, (pid, label) in PROPERTY_FIELDS.items():
            prop = catalog[pid]
            self.assertEqual(prop['property_name'], label)
            claim_type = KeyboardExtraction.model_fields[field].annotation.__args__[0]
            expected = QuantityClaim if prop['wikibase_value_type']=='Quantity' else EntityClaim if prop['wikibase_value_type']=='WikibaseItem' else TextClaim
            self.assertIs(claim_type, expected)

    def test_sdk_can_build_strict_schema(self):
        schema = to_strict_json_schema(Extraction)
        json.dumps(schema)
        entity = schema['$defs']['KeyboardExtraction']
        self.assertFalse(entity['additionalProperties'])
        self.assertEqual(set(entity['required']), set(entity['properties']))


if __name__ == '__main__':
    unittest.main()
