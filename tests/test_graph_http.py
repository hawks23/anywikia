"""FastAPI HTTP contracts: real routing and middleware, no external services."""

import asyncio
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
import web_app
from api_http import MAX_BODY_BYTES


class GraphHTTPTests(unittest.TestCase):
    def setUp(self):
        self.app = web_app.create_app()
        self.client = TestClient(self.app, base_url="http://localhost:8000")
        self.addCleanup(self.client.close)
        self.headers = {"X-Anywikia-CSRF": self.app.state.csrf_token}

    def post(self, action, payload, headers=None):
        return self.client.post(
            "/api/graph/" + action,
            json=payload,
            headers=self.headers if headers is None else headers,
        )

    def test_graph_routes_delegate_to_main_handler(self):
        cases = {
            "preview": {
                "mode": "existing",
                "confirmed": True,
                "target_id": "Q1",
                "name": "Keyboard",
                "claims": [{"property_id": "P1", "value": "88"}],
            },
            "confirm": {"preview_id": "a" * 32, "confirmed": True},
            "verify": {"entity_id": "Q1", "property_id": ""},
            "rebuild": {"confirmed": True},
            "inspect": {"entity_id": "Q1"},
            "search": {"text": "Yamaha"},
        }
        for action, payload in cases.items():
            with self.subTest(action=action), patch(
                "web_app.graph_action", return_value={"ok": True}
            ) as dispatch:
                response = self.post(action, payload)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json(), {"ok": True})
                self.assertEqual(dispatch.call_args.args[0], action)
                for key, value in payload.items():
                    if key != "claims":
                        self.assertEqual(dispatch.call_args.args[1][key], value)

    def test_cross_origin_missing_token_and_foreign_host_rejected(self):
        for changed in (
            {"X-Anywikia-CSRF": ""},
            {"Origin": "https://other.example"},
            {"Host": "other.example:8000"},
            {"Host": "localhost:9999"},
        ):
            with self.subTest(changed=changed), patch(
                "web_app.graph_action"
            ) as dispatch:
                response = self.post(
                    "rebuild", {"confirmed": True}, {**self.headers, **changed}
                )
                self.assertEqual(response.status_code, 403)
                dispatch.assert_not_called()

    def test_errors_have_compatible_status_and_shape(self):
        errors = [
            (ValueError("width requires a length unit"), 400),
            (RuntimeError("Update status uncertain"), 503),
            (OSError("runtime unavailable"), 503),
            (httpx.ConnectError("offline"), 502),
            (subprocess.TimeoutExpired("pipeline", 300), 504),
        ]
        for error, status in errors:
            with self.subTest(error=error), patch(
                "web_app.graph_action", side_effect=error
            ):
                response = self.post("inspect", {"entity_id": "Q1"})
                self.assertEqual(response.status_code, status)
                self.assertIsInstance(response.json()["error"], str)

    def test_strict_confirmation_and_invalid_ids_do_not_dispatch(self):
        with patch("web_app.graph_action") as dispatch:
            for action, payload in [
                ("confirm", {"preview_id": "a" * 32, "confirmed": "true"}),
                ("rebuild", {"confirmed": 1}),
                ("inspect", {"entity_id": "Q1 . }"}),
                ("confirm", {"preview_id": "../secret", "confirmed": True}),
            ]:
                self.assertEqual(self.post(action, payload).status_code, 400)
            dispatch.assert_not_called()

    def test_invalid_json_content_type_and_size_do_not_dispatch(self):
        with patch("web_app.extract") as extract:
            for content, content_type in [
                (b"{", "application/json"),
                (b"[]", "application/json"),
                (b"", "application/json"),
                (b"{}", "text/plain"),
                (b"x" * (MAX_BODY_BYTES + 1), "application/json"),
            ]:
                response = self.client.post(
                    "/api/extract",
                    content=content,
                    headers={"Content-Type": content_type},
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.json())
            extract.assert_not_called()

    def test_chunked_limit_counts_received_bytes_before_dispatch(self):
        messages = iter(
            [
                {
                    "type": "http.request",
                    "body": b"x" * MAX_BODY_BYTES,
                    "more_body": True,
                },
                {"type": "http.request", "body": b"x", "more_body": False},
            ]
        )
        sent = []

        async def run():
            async def receive():
                return next(messages)

            async def send(message):
                sent.append(message)

            await self.app(
                {
                    "type": "http",
                    "asgi": {"version": "3.0"},
                    "http_version": "1.1",
                    "method": "POST",
                    "scheme": "http",
                    "path": "/api/extract",
                    "raw_path": b"/api/extract",
                    "query_string": b"",
                    "root_path": "",
                    "server": ("localhost", 8000),
                    "client": ("127.0.0.1", 1),
                    "headers": [
                        (b"host", b"localhost:8000"),
                        (b"content-type", b"application/json"),
                    ],
                },
                receive,
                send,
            )

        with patch("web_app.extract") as extract:
            asyncio.run(run())
            extract.assert_not_called()
        self.assertEqual(sent[0]["status"], 400)

    def test_extraction_then_suggestions_preserves_output(self):
        result = {"entities": []}
        with patch("web_app.extract", return_value=result) as extract, patch(
            "web_app.add_name_suggestions", return_value=result
        ) as suggest:
            response = self.client.post("/api/extract", json={"text": "source"})
            self.assertEqual(response.json(), result)
            extract.assert_called_once_with("source")
            suggest.assert_called_once_with(result)

    def test_empty_or_oversize_source_never_extracts(self):
        with patch("web_app.extract") as extract:
            for value in (None, "", "   ", "x" * 20001):
                self.assertEqual(
                    self.client.post("/api/extract", json={"text": value}).status_code,
                    400,
                )
            extract.assert_not_called()

    def test_status_token_and_comparison(self):
        with patch("web_app.graph_action", return_value={"ready": True}):
            response = self.client.get("/api/graph/status")
            self.assertEqual(response.json()["csrf"], self.app.state.csrf_token)
        with patch("web_app.inspect_entity", return_value={"id": "Q1"}) as inspect:
            self.assertEqual(self.client.get("/api/entities/Q1").json(), {"id": "Q1"})
            inspect.assert_called_once_with("Q1")

    def test_static_files_docs_and_private_paths(self):
        schema = self.client.get("/openapi.json").json()
        operation = schema["paths"]["/api/graph/confirm"]["post"]
        self.assertIn("security", operation)
        self.assertIn("default", operation["responses"])
        self.assertNotIn("422", operation["responses"])
        for path in (
            "/",
            "/app.js",
            "/comparison.js",
            "/review-plan.js",
            "/rdf-review.js",
            "/style.css",
            "/docs",
            "/openapi.json",
        ):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        for path in (
            "/.env",
            "/.anywikia/config.json",
            "/keyboards-index/keyboards.nt",
            "/unknown",
        ):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 404)
            self.assertIn("error", response.json())

    def test_custom_port_and_foreign_get_host(self):
        with TestClient(self.app, base_url="http://127.0.0.1:8012") as client:
            self.assertEqual(client.get("/").status_code, 200)
            self.assertEqual(
                client.get("/", headers={"Host": "evil.example:8012"}).status_code, 403
            )

    def test_http_preview_confirm_retry_replace_and_verify_with_real_store(self):
        """Keep the domain path real; replace only the external graph runtime."""
        from functions import rdf_service
        from functions.rdf_store import RDFStore
        from tests.test_rdf_writes import MemoryRuntime

        with tempfile.TemporaryDirectory() as directory:
            runtime = MemoryRuntime(directory)
            with patch.object(rdf_service, "runtime", runtime), patch.object(
                rdf_service, "store", RDFStore(runtime)
            ):
                payload = {
                    "mode": "new",
                    "confirmed": True,
                    "name": "HTTP Test Keyboard",
                    "claims": [{"property_id": "P1", "value": "61"}],
                }
                preview = self.post("preview", payload)
                self.assertEqual(preview.status_code, 200, preview.text)
                self.assertEqual(runtime.updates, 0)
                approval = {
                    "preview_id": preview.json()["preview_id"],
                    "confirmed": True,
                }
                saved = self.post("confirm", approval)
                self.assertEqual(saved.status_code, 200, saved.text)
                self.assertTrue(saved.json()["verified"])
                qid = saved.json()["entity_id"]
                retry = self.post("confirm", approval)
                self.assertEqual(retry.json()["status"], "already_applied")
                self.assertEqual(runtime.updates, 1)
                inspected = self.post("inspect", {"entity_id": qid}).json()
                statement = inspected["statements"][0]["statement"]
                payload.update(mode="existing", target_id=qid)
                payload["claims"] = [
                    {
                        "property_id": "P1",
                        "value": "73",
                        "action": "replace",
                        "statement": statement,
                    }
                ]
                preview = self.post("preview", payload)
                self.assertEqual(preview.status_code, 200, preview.text)
                saved = self.post(
                    "confirm",
                    {"preview_id": preview.json()["preview_id"], "confirmed": True},
                )
                self.assertTrue(saved.json()["verified"])
                result = self.post("verify", {"entity_id": qid, "property_id": "P1"})
                self.assertEqual(result.status_code, 200, result.text)
                self.assertIn("query", result.json())
                self.assertEqual(
                    result.json()["results"]["results"]["bindings"][0]["value"][
                        "value"
                    ],
                    "73",
                )


if __name__ == "__main__":
    unittest.main()
