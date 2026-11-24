"""Read-only web adapter contract tests; no CampusAI requests."""

import json
import subprocess
import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import web_app


class WebAdapterTests(unittest.TestCase):
    def test_invalid_input_never_calls_pipeline(self):
        with patch("functions.web_review.subprocess.run") as run:
            for text in (None, "", "   ", "x" * 20001):
                with self.assertRaises(ValueError):
                    web_app.extract(text)
            run.assert_not_called()

    def test_pipeline_receives_text_on_stdin_and_preserves_grouped_output(self):
        result = {"entities": [{"name": "Keyboard", "properties": {}}]}
        with patch(
            "functions.web_review.subprocess.run",
            return_value=Mock(returncode=0, stdout=json.dumps(result)),
        ) as run:
            self.assertEqual(web_app.extract("source text"), result)
            self.assertEqual(run.call_args.kwargs["input"], "source text")
            self.assertNotIn("source text", run.call_args.args[0])
            self.assertEqual(run.call_args.kwargs["stdout"], subprocess.PIPE)
            self.assertNotIn("stderr", run.call_args.kwargs)
            self.assertNotIn("capture_output", run.call_args.kwargs)

    def test_pipeline_errors_are_reported(self):
        with patch(
            "functions.web_review.subprocess.run",
            return_value=Mock(
                returncode=1, stdout=json.dumps({"error": "unavailable"})
            ),
        ):
            with self.assertRaisesRegex(ValueError, "unavailable"):
                web_app.extract("source")

    def test_child_enables_progress_and_keeps_json_separate(self):
        # Exercise the real child runner with a local fake pipeline; no services.
        real_run = subprocess.run
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "handler.py").write_text(
                "from functions.progress import report\n"
                "class Result:\n"
                "    def model_dump_json(self): return '{\"entities\": []}'\n"
                "def run_pipeline(text):\n"
                "    report('Checking test pipeline...')\n"
                "    return Result()\n"
            )
            (root / "functions").mkdir()
            (root / "functions" / "__init__.py").write_text("")
            (root / "functions" / "progress.py").write_text(
                (web_app.ROOT / "functions" / "progress.py").read_text()
            )
            captured = []

            def run_child(*args, **kwargs):
                kwargs.update(cwd=root, stderr=subprocess.PIPE)
                result = real_run(*args, **kwargs)
                captured.append(result)
                return result

            with patch("functions.web_review.subprocess.run", side_effect=run_child):
                self.assertEqual(web_app.extract("source"), {"entities": []})
            self.assertIn("[anywikia] Checking test pipeline...", captured[0].stderr)
            self.assertEqual(json.loads(captured[0].stdout), {"entities": []})

    def test_entity_query_rejects_injection_before_network(self):
        with patch("functions.web_review.httpx.post") as post:
            with self.assertRaises(ValueError):
                web_app.inspect_entity("Q1 . } UNION {")
            post.assert_not_called()

    def test_entity_query_preserves_rdf_terms(self):
        rows = [{"value": {"type": "literal", "value": "1385"}}]
        response = Mock()
        response.json.return_value = {"results": {"bindings": rows}}
        with patch("functions.web_review.httpx.post", return_value=response) as post:
            self.assertEqual(
                web_app.inspect_entity("Q1"), {"id": "Q1", "properties": rows}
            )
            query = post.call_args.kwargs["data"]["query"]
            self.assertIn("SELECT DISTINCT", query)
            self.assertIn("wb:quantityUnit", query)


if __name__ == "__main__":
    unittest.main()
