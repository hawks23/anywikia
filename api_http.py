"""Shared HTTP protections and browser-readable errors for the local API.

This ASGI middleware bounds JSON and multipart bodies before FastAPI parses them.
ASGI is the request/response interface between Uvicorn and FastAPI. A request
body can arrive in several messages, so Content-Length alone is not sufficient.
"""

import secrets
import subprocess

import httpx
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers, MutableHeaders
from starlette.exceptions import HTTPException

MAX_BODY_BYTES = 500000
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def error_response(status, message):
    """Keep the {error: message} contract used by frontend/app.js."""
    return JSONResponse(status_code=status, content={"error": message})


class LocalRequestMiddleware:
    """Reject foreign hosts/origins and unapproved graph requests before dispatch."""

    def __init__(self, app, csrf_token):
        self.app = app
        self.csrf_token = csrf_token

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["Cache-Control"] = "no-store"
                headers["X-Content-Type-Options"] = "nosniff"
            await send(message)

        async def reject(status, message):
            await error_response(status, message)(scope, receive, send_with_headers)

        headers = Headers(scope=scope)
        host = headers.get("host", "")
        port = scope["server"][1]
        allowed = {f"localhost:{port}", f"127.0.0.1:{port}"}
        if port == 80:
            allowed.update({"localhost", "127.0.0.1"})
        if host not in allowed:
            return await reject(403, "Localhost access only.")

        if scope["method"] != "POST":
            return await self.app(scope, receive, send_with_headers)

        origin = headers.get("origin")
        if origin and origin != "http://" + host:
            return await reject(403, "Cross-origin requests are not allowed.")
        is_upload = scope["path"] == "/ocr"
        if is_upload or scope["path"].startswith("/api/graph/"):
            token = headers.get("x-anywikia-csrf", "")
            if not secrets.compare_digest(token.encode(), self.csrf_token.encode()):
                return await reject(403, "Reload the page before using graph actions.")
        expected_type = "multipart/form-data" if is_upload else "application/json"
        content_type = headers.get("content-type", "").split(";")[0].strip().lower()
        if content_type != expected_type:
            return await reject(400, f"Expected {expected_type}")
        # Allow multipart boundary/header overhead in addition to the file bytes.
        body_limit = MAX_UPLOAD_BYTES + 65536 if is_upload else MAX_BODY_BYTES

        # Reject a declared oversize body before receiving it, then also count
        # actual bytes to cover chunked requests and incorrect length headers.
        length = headers.get("content-length")
        if length is not None:
            try:
                if not 0 < int(length) <= body_limit:
                    return await reject(400, "Request is empty or too large")
            except ValueError:
                return await reject(400, "Invalid Content-Length")
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > body_limit:
                return await reject(400, "Request is empty or too large")
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        if not body:
            return await reject(400, "Request is empty or too large")

        delivered = False

        async def receive_body():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, receive_body, send_with_headers)


def install_error_handlers(app):
    """Translate expected application failures without exposing stack traces."""

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        messages = [
            f"{'.'.join(map(str, item['loc']))}: {item['msg']}"
            for item in error.errors()
        ]
        return error_response(400, "Invalid request. " + "; ".join(messages))

    @app.exception_handler(ValueError)
    async def invalid_value(request, error):
        return error_response(400, str(error))

    @app.exception_handler(subprocess.TimeoutExpired)
    async def extraction_timeout(request, error):
        return error_response(
            504, "Pipeline exceeded five minutes. Try a shorter passage."
        )

    @app.exception_handler(httpx.HTTPError)
    async def graph_unreachable(request, error):
        return error_response(
            502, "Cannot reach the working QLever graph. Check its status and retry."
        )

    @app.exception_handler(RuntimeError)
    @app.exception_handler(OSError)
    async def runtime_unavailable(request, error):
        return error_response(503, str(error))

    @app.exception_handler(HTTPException)
    async def http_failure(request, error):
        return error_response(error.status_code, str(error.detail))
