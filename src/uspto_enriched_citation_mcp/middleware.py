"""HTTP-mode ASGI middleware for the MCP surface (module split, SD-1).

Stack order is composed in server_bootstrap.run_server():
SecurityHeaders -> APIKeyAuth -> SizeLimit -> CORS -> mcp app.
"""

import os
from typing import Optional

from .config.constants import MAX_REQUEST_SIZE_BYTES
from .util.logging import get_logger

logger = get_logger(__name__)


class APIKeyAuthMiddleware:
    """Validates X-API-KEY header on all non-health requests in HTTP mode.

    Checks against INTERNAL_AUTH_SECRET (the shared cross-MCP secret),
    not the external USPTO API key.  Health endpoint is intentionally
    open for load balancer probes.

    Auth is opt-in: if INTERNAL_AUTH_SECRET is not set (via secure
    storage or env var), all requests are allowed through.  Set the
    secret to enforce authentication.

    Not wired in OAuth mode (CITATIONS_AUTH_MODE=oauth): the MCP surface
    is bearer-protected by FastMCP and the OAuth routes must be public.
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        from starlette.requests import Request
        request = Request(scope, receive)
        if request.url.path == "/health":
            await self.app(scope, receive, send)
            return
        key = request.headers.get("x-api-key")
        from .shared_secure_storage import get_internal_auth_secret as _get_secret
        import secrets as _secrets
        expected = (
            _get_secret()
            or os.environ.get("INTERNAL_AUTH_SECRET")
        )
        if expected and not _secrets.compare_digest(key or "", expected):
            # Log the event only — never the presented key or the path
            logger.warning("HTTP auth failed (x-api-key missing or mismatch)")
            from starlette.responses import JSONResponse
            response = JSONResponse({"error": "Unauthorized"}, status_code=401)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


class _BodyTooLarge(Exception):
    """Internal signal: streamed request body exceeded the cap (M3)."""

    def __init__(self, received: int):
        self.received = received


class RequestSizeLimitMiddleware:
    """ASGI middleware capping inbound request body size (M3, CWE-770/400).

    Ported from uspto_ptab_mcp's proxy/server.py::RequestSizeLimitMiddleware.
    Checks Content-Length when present AND keeps a running byte count while
    the body streams in, so a chunked request (no Content-Length) can't
    bypass the cap. Pure ASGI so it wraps the MCP HTTP stack cleanly.
    """

    def __init__(self, app, max_request_size: int = MAX_REQUEST_SIZE_BYTES):
        self.app = app
        self.max_request_size = max_request_size

    async def _send_413(self, send) -> None:
        import json as _json

        body = _json.dumps(
            {
                "error": True,
                "message": f"Request body too large. Maximum size: {self.max_request_size} bytes",
                "max_allowed": self.max_request_size,
            }
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("latin-1")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

    @staticmethod
    def _content_length(headers) -> Optional[int]:
        for name, value in headers:
            if name == b"content-length":
                try:
                    return int(value)
                except ValueError:
                    return None
        return None

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        content_length = self._content_length(scope.get("headers", []))
        if content_length is not None and content_length > self.max_request_size:
            logger.warning("Request body too large (Content-Length over cap)")
            await self._send_413(send)
            return

        received = 0
        response_started = False

        async def counting_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_request_size:
                    raise _BodyTooLarge(received)
            return message

        async def tracking_send(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except _BodyTooLarge:
            logger.warning("Request body too large (streamed bytes over cap)")
            if not response_started:
                await self._send_413(send)
            # If the response already started there is nothing safe to send;
            # the connection is torn down by the server.


class SecurityHeadersMiddleware:
    """Adds browser security headers to all HTTP responses."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        _SECURITY_HEADERS = [
            (b"x-content-type-options", b"nosniff"),
            (b"x-frame-options", b"DENY"),
            (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
            (
                b"content-security-policy",
                b"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
            ),
        ]

        async def patched_send(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(_SECURITY_HEADERS)
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, patched_send)
