import unittest
from functions.review_validation import validate_units_for_rdf, COUNT_PROPERTIES
from functions.pydantic_models import PROPERTY_FIELDS


class ReviewUnitTests(unittest.TestCase):
    def test_price_requires_one_of_configured_currencies(self):
        for unit in ("DKK", "EUR", "USD", "GBP"):
            validate_units_for_rdf(self.review("price", "0", unit))
        for unit in (None, "", "  ", "$", "JPY", "Q199"):
            with self.subTest(unit=unit), self.assertRaises(ValueError):
                validate_units_for_rdf(self.review("price", "100", unit))
        validate_units_for_rdf(self.review("price", "", None))

    def review(self, field, value, unit):
        return {"entities": [{"name": "Keyboard", "properties": {field: {
            "property_id": PROPERTY_FIELDS[field][0], "value_type": "String",
            "claims": [{"value": value, "unit": unit}]}}}]}

    def test_measurements_require_units_even_if_client_changes_type(self):
        for field in ("width", "depth", "height", "weight", "power_consumption"):
            for unit in (None, "", "  "):
                with self.subTest(field=field, unit=unit), self.assertRaises(ValueError):
                    validate_units_for_rdf(self.review(field, "0", unit))
            validate_units_for_rdf(self.review(field, "12", "mm"))

    def test_counts_and_empty_measurements_allow_no_unit(self):
        for field, (pid, _) in PROPERTY_FIELDS.items():
            if pid in COUNT_PROPERTIES:
                validate_units_for_rdf(self.review(field, "61", None))
        for value in (None, "", "  "):
            validate_units_for_rdf(self.review("width", value, None))

    def test_rejects_changed_property_id(self):
        review = self.review("width", "10", None)
        review["entities"][0]["properties"]["width"]["property_id"] = "P1"
        with self.assertRaises(ValueError):
            validate_units_for_rdf(review)
