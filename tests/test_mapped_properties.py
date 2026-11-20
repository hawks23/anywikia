"""Mapped properties bypass network lookup without changing entity resolution."""
import unittest
from unittest.mock import patch, call

from functions import pydantic_models, resolve_local


class MappedPropertyTests(unittest.TestCase):
    def fact(self, **changes):
        return {"subject": "Yamaha P-150", "property": "width", "property_id": "P2",
                "value": "1385", "unit": "mm",
                "evidence": "The Yamaha P-150 is 1385 mm wide.", **changes}

    def test_quantity_only_queries_subject(self):
        source = self.fact()
        with patch.object(resolve_local, "search_local", return_value=[{"id": "Q1"}]) as search:
            result = resolve_local.extract_ids(source)
        search.assert_called_once_with("Yamaha P-150", "item")
        self.assertEqual(result["property_id"], "P2")
        self.assertIsNone(result["value_id"])
        self.assertEqual({k: result[k] for k in source}, source)
        self.assertNotIn("subject_id", source)

    def test_entity_property_uses_catalog_type_for_value_lookup(self):
        source = self.fact(property="manufacturer", property_id="P6", value="Yamaha", unit=None)
        with patch.object(resolve_local, "search_local", side_effect=[
                [{"id": "Q1"}], [{"id": "Q2"}]]) as search:
            result = resolve_local.extract_ids(source)
        self.assertEqual(search.call_args_list, [call("Yamaha P-150", "item"), call("Yamaha", "item")])
        self.assertEqual(result["property_id"], "P6")
        self.assertEqual(result["value_id"], "Q2")

    def test_invalid_pid_or_label_is_rejected_without_search(self):
        with patch.object(resolve_local, "search_local") as search:
            for pid in ("P6", "P999", None):
                with self.assertRaises(ValueError):
                    resolve_local.extract_ids(self.fact(property_id=pid))
        search.assert_not_called()

    def test_catalog_type_drift_is_rejected(self):
        catalog = {"P2": {"property_name": "width", "wikibase_value_type": "WikibaseItem"}}
        with patch.object(pydantic_models, "_property_catalog", return_value=catalog):
            with self.assertRaisesRegex(ValueError, "datatype"):
                pydantic_models.validate_mapped_property("P2", "width")


if __name__ == "__main__":
    unittest.main()
