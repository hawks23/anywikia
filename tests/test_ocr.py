"""Simple OCR checks. CampusAI requests are mocked; PDF rendering is real."""

import base64
from contextlib import redirect_stderr
from io import StringIO
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image
from functions import ocr


class OCRTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.image = Path(self.temp.name) / "image.png"
        Image.new("RGB", (100, 100), "white").save(self.image)
        self.env = patch.dict(
            os.environ, {"CAMPUSAI_API_KEY": "test", "CAMPUSAI_MODEL": "vision"}
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.dotenv = patch.object(ocr, "load_dotenv")
        self.dotenv.start()
        self.addCleanup(self.dotenv.stop)

    def test_image_request_uses_png_and_returns_text(self):
        client = Mock()
        client.chat.completions.create.return_value.choices = [
            Mock(finish_reason="stop", message=Mock(content="88 keys", refusal=None))
        ]
        with Image.open(self.image) as image:
            self.assertEqual(ocr.transcribe_image(client, "vision", image), "88 keys")
        args = client.chat.completions.create.call_args.kwargs
        self.assertEqual(args["model"], "vision")
        url = args["messages"][0]["content"][1]["image_url"]["url"]
        self.assertTrue(url.startswith("data:image/png;base64,"))
        self.assertTrue(base64.b64decode(url.split(",")[1]).startswith(b"\x89PNG"))

    def test_real_pdf_pages_are_numbered_and_logged_in_order(self):
        if not shutil.which("pdftoppm") or not shutil.which("pdfinfo"):
            self.skipTest("Poppler is not installed")
        pdf = Path(self.temp.name) / "input.pdf"
        with Image.open(self.image) as first:
            second = Image.new("RGB", (100, 100), "black")
            first.save(pdf, save_all=True, append_images=[second])
            second.close()
        logs = StringIO()
        with patch.object(ocr, "OpenAI"), patch.object(
            ocr, "transcribe_image", side_effect=["first", "second"]
        ) as request, redirect_stderr(logs):
            result = ocr.transcribe_document(pdf)
        self.assertEqual(result, "Page 1\n\nfirst\n\nPage 2\n\nsecond")
        self.assertEqual(request.call_count, 2)
        self.assertEqual(
            logs.getvalue().splitlines(),
            [
                "Starting OCR on page 1 of 2",
                "OCR complete on page 1 of 2",
                "Starting OCR on page 2 of 2",
                "OCR complete on page 2 of 2",
            ],
        )

    def test_numbering_restarts_for_each_image_input(self):
        with patch.object(ocr, "OpenAI"), patch.object(
            ocr, "transcribe_image", return_value="text"
        ), redirect_stderr(StringIO()):
            self.assertEqual(ocr.transcribe_document(self.image), "Page 1\n\ntext")
            self.assertEqual(ocr.transcribe_document(self.image), "Page 1\n\ntext")

    def test_failure_does_not_log_page_as_complete(self):
        logs = StringIO()
        with patch.object(ocr, "OpenAI"), patch.object(
            ocr, "transcribe_image", side_effect=ValueError("failed")
        ), redirect_stderr(logs):
            with self.assertRaisesRegex(ValueError, "failed"):
                ocr.transcribe_document(self.image)
        self.assertNotIn("OCR complete", logs.getvalue())

    def test_incomplete_or_refused_response_is_not_success(self):
        client = Mock()
        for finish, text, refusal in [
            ("length", "partial", None),
            ("stop", None, None),
            ("stop", None, "refused"),
        ]:
            client.chat.completions.create.return_value.choices = [
                Mock(finish_reason=finish, message=Mock(content=text, refusal=refusal))
            ]
            with Image.open(self.image) as image, self.assertRaises(ValueError):
                ocr.transcribe_image(client, "vision", image)


if __name__ == "__main__":
    unittest.main()
