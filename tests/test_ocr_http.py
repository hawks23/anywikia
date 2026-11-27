"""Upload API tests: real multipart requests, mocked CampusAI transcription."""

from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from openai import APITimeoutError
import httpx
from pdf2image.exceptions import PDFInfoNotInstalledError
import web_app


class OCRHTTPTests(unittest.TestCase):
    def setUp(self):
        self.app = web_app.create_app()
        self.client = TestClient(self.app, base_url="http://localhost:8000")
        self.addCleanup(self.client.close)
        self.headers = {"X-Anywikia-CSRF": self.app.state.csrf_token}

    def upload(self, name="scan.png", content=b"image", headers=None):
        return self.client.post(
            "/ocr",
            files={"file": (name, content)},
            headers=self.headers if headers is None else headers,
        )

    def test_image_and_pdf_are_transcribed_and_upload_is_deleted(self):
        paths = []

        def read(path):
            paths.append(path)
            self.assertEqual(path.read_bytes(), b"source")
            return "Page 1\n88 keys"

        with patch("functions.ocr.transcribe_document", side_effect=read):
            for name in ("scan.png", "../../scan.pdf", "photo.JPG"):
                result = self.upload(name, b"source")
                self.assertEqual(result.status_code, 200, result.text)
                self.assertEqual(result.json(), {"text": "Page 1\n88 keys"})
        self.assertTrue(
            all(path.name.startswith("source.") and not path.exists() for path in paths)
        )

    def test_upload_limit_is_separate_from_json_limit(self):
        with patch("functions.ocr.transcribe_document", return_value="text") as ocr:
            self.assertEqual(self.upload(content=b"x" * 600000).status_code, 200)
            ocr.assert_called_once()
        with patch("functions.ocr.transcribe_document") as ocr:
            self.assertEqual(
                self.upload(content=b"x" * (20 * 1024 * 1024 + 1)).status_code, 400
            )
            ocr.assert_not_called()

    def test_invalid_files_and_access_never_call_ocr(self):
        with patch("functions.ocr.transcribe_document") as ocr:
            self.assertEqual(self.upload("bad.txt").status_code, 400)
            self.assertEqual(self.upload(content=b"").status_code, 400)
            self.assertEqual(self.upload(headers={}).status_code, 403)
            self.assertEqual(
                self.upload(
                    headers={**self.headers, "Origin": "https://other.example"}
                ).status_code,
                403,
            )
            self.assertEqual(
                self.client.post("/ocr", json={}, headers=self.headers).status_code, 400
            )
            ocr.assert_not_called()

    def test_errors_are_readable_and_temporary_file_is_deleted(self):
        for error, expected in [
            (ValueError("no complete transcription"), 400),
            (PDFInfoNotInstalledError("missing"), 503),
            (
                APITimeoutError(
                    request=httpx.Request("POST", "https://example.invalid")
                ),
                504,
            ),
        ]:
            paths = []

            def fail(path):
                paths.append(path)
                raise error

            with patch("functions.ocr.transcribe_document", side_effect=fail):
                response = self.upload()
            self.assertEqual(response.status_code, expected)
            self.assertIn("error", response.json())
            self.assertTrue(all(not path.exists() for path in paths))

    def test_schema_documents_multipart_and_token(self):
        route = self.client.get("/openapi.json").json()["paths"]["/ocr"]["post"]
        self.assertIn("multipart/form-data", route["requestBody"]["content"])
        self.assertIn("security", route)


if __name__ == "__main__":
    unittest.main()
