"""Lazy loading, ranking and failure isolation for similar-name suggestions."""
import unittest
from unittest.mock import patch
import httpx
from functions import similar_names as names


def row(qid, name):
    return dict(id=qid, name=name, matched_name=name, normalized=names.normalize(name))


class SimilarNamesTests(unittest.TestCase):
    def setUp(self):
        names.invalidate_name_cache()

    def tearDown(self):
        names.invalidate_name_cache()

    def test_no_cache_for_exact_ambiguous_or_failed_lookup(self):
        result = {"entities": [
            dict(subject_id="Q1", warnings=[]),
            dict(subject_candidates=[{"id":"Q1"}], warnings=[]),
            dict(warnings=["subject: local lookup failed"])]}
        with patch.object(names, "load_names") as load:
            names.add_name_suggestions(result)
            load.assert_not_called()
        self.assertIsNone(names._cache)

    def test_lazy_cache_reused_and_expired_on_demand(self):
        with patch.object(names, "load_names", return_value=[row("Q1", "P150")]) as load, patch.object(names, "monotonic", return_value=10):
            self.assertEqual(names.suggest_names("P151")[0]["id"], "Q1")
            names.suggest_names("P152")
            self.assertEqual(load.call_count, 1)
        with patch.object(names, "load_names", return_value=[]) as load, patch.object(names, "monotonic", return_value=311):
            self.assertEqual(names.suggest_names("P151"), [])
            load.assert_called_once()

    def test_rank_deduplicate_and_threshold(self):
        rows = [row("Q1", "P150"), row("Q1", "P15"), row("Q2", "P151"),
                row("Q3", "P152"), row("Q4", "P153"), row("Q5", "ZZZ")]
        with patch.object(names, "load_names", return_value=rows):
            result = names.suggest_names("p150")
            self.assertEqual([r["id"] for r in result], ["Q1", "Q2", "Q3"])
            self.assertEqual(names.suggest_names("Aurora Testboard X9"), [])
        self.assertEqual(names.distance("abc", "xyz"), 3)

    def test_failed_load_not_cached_or_mistaken_for_no_matches(self):
        entity = dict(name="P151", subject_id=None, warnings=["subject: no local match"])
        with patch.object(names, "load_names", side_effect=httpx.ConnectError("offline")):
            names.add_name_suggestions({"entities":[entity]})
        self.assertIsNone(names._cache)
        self.assertIn("suggestion_error", entity)
        self.assertNotIn("name_suggestions", entity)

    def test_suggestion_does_not_assign_subject_id(self):
        entity = dict(name="P151", subject_id=None, warnings=["subject: no local match"])
        with patch.object(names, "load_names", return_value=[row("Q1", "P150")]):
            names.add_name_suggestions({"entities":[entity]})
        self.assertIsNone(entity["subject_id"])
        self.assertEqual(entity["name_suggestions"][0]["id"], "Q1")


if __name__ == "__main__":
    unittest.main()
