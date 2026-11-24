"""Offline HTTP routing tests: no sockets, browser, Docker or network access."""
import io
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import web_app


class GraphHTTPTests(unittest.TestCase):
    def call(self, action="preview", payload=None, host="localhost:8000", origin="http://localhost:8000", token=web_app.WRITE_CSRF):
        handler = object.__new__(web_app.Handler)
        handler.path = "/api/graph/" + action
        handler.server = SimpleNamespace(server_port=8000)
        body = json.dumps(payload or {}).encode()
        handler.headers = {"Host":host,"Origin":origin,"Content-Type":"application/json","Content-Length":str(len(body)),"X-Anywikia-CSRF":token}
        handler.rfile = io.BytesIO(body)
        results = []
        handler.send = lambda *args: results.append(args)
        handler.do_POST()
        return results[0]

    def test_graph_routes_delegate_to_main_handler(self):
        for action in ("preview","confirm","verify","rebuild","inspect","search"):
            with self.subTest(action=action), patch("web_app.graph_action", return_value={"ok":True}) as dispatch:
                result = self.call(action, {"example":123})
                self.assertEqual(result[0],200)
                dispatch.assert_called_once_with(action,{"example":123})

    def test_cross_origin_missing_token_and_foreign_host_rejected(self):
        for args in ({"token":""},{"origin":"https://other.example"},{"host":"other.example:8000","origin":"http://other.example:8000"}):
            with self.subTest(args=args), patch("web_app.graph_action") as dispatch:
                self.assertEqual(self.call(**args)[0],403)
                dispatch.assert_not_called()

    def test_validation_errors_reach_browser_without_success(self):
        with patch("web_app.graph_action", side_effect=ValueError("width requires a length unit")):
            status, body = self.call()
            self.assertEqual(status,400)
            self.assertIn("length unit",body["error"])

    def test_uncertain_update_is_not_reported_as_success(self):
        with patch("web_app.graph_action", side_effect=RuntimeError("Update status uncertain")):
            self.assertEqual(self.call("confirm")[0],503)


if __name__ == "__main__": unittest.main()
