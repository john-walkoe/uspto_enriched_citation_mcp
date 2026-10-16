"""HTTP-mode ASGI middleware for the MCP surface (module split, SD-1).

Stack order is composed in server_bootstrap.run_server():
SecurityHeaders -> APIKeyAuth -> SizeLimit -> CORS -> mcp app.
"""

import os
from typing import Optional

from .config.constants import MAX_REQUEST_SIZE_BYTES
from .util.logging import get_logger

logger = get_logger(__name__)


def _matches_any_candidate(presented, candidates) -> bool:
    """Constant-time membership test against every rotation candidate.

    INTERNAL_AUTH_SECRET may be a comma-separated list (current secret
    first, then any secret still being retired) — a rotation overlap window
    instead of a synchronized four-service restart (S-06). Every candidate
    is compared, never short-circuited on the first match, so the timing
    does not reveal how many secrets are in the rotation window or which
    one (if any) validated.
    """
    if not presented:
        return False
    import secrets as _secrets

    matched = False
    for candidate in candidates:
        if _secrets.compare_digest(presented, candidate):
            matched = True
    return matched


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
        from .shared_secure_storage import (
            get_internal_auth_secret as _get_secret,
            split_secret_candidates,
        )
        expected_raw = (
            _get_secret()
            or os.environ.get("INTERNAL_AUTH_SECRET")
        )
        candidates = split_secret_candidates(expected_raw)
        if candidates and not _matches_any_candidate(key, candidates):
            # Log the event only — never the presented key or the path
            logger.warning("HTTP auth failed (x-api-key missing or mismatch)")
            # auth_failure was implemented in the security-event vocabulary
            # and had no production caller, so in mode=none the security log
            # contained no auth events at all and a credential-guessing run
            # produced no signal an operator would see (S-26).
            _emit_auth_event(
                success=False,
                reason="missing x-api-key" if not key else "invalid x-api-key",
            )
            from starlette.responses import JSONResponse
            response = JSONResponse({"error": "Unauthorized"}, status_code=401)
            await response(scope, receive, send)
            return
        # Deliberately no auth_success event: one record per accepted request
        # would be the highest-volume line in the security log and would make
        # the retention window meaningless. Detection is the gap S-26 names,
        # and failures are what carry that signal.
        await self.app(scope, receive, send)


def _emit_auth_event(success: bool, reason: str = "") -> None:
    """Record an x-api-key authentication outcome in the security log.

    Never raises and never carries the presented key: the value of this event
    is the count and the timing, not the credential.
    """
    try:
        from .util.security_logger import get_security_logger

        security_logger = get_security_logger()
        if success:
            security_logger.auth_success(method="x-api-key")
        else:
            security_logger.auth_failure(method="x-api-key", reason=reason)
    except Exception:
        # A security-log failure must not turn a 401 into a 500.
        pass


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


class InboundRateLimitMiddleware:
    """Per-identity inbound rate limit for the MCP surface (S-xx).

    `main.py`'s health-check docstring said "Rate limiting is applied
    globally via the RateLimiter", but the only RateLimiter in the process
    paced OUTBOUND calls to USPTO. Nothing metered what came IN, so one
    client could drive the whole per-key USPTO quota and the OCR-free
    search surface at will.

    Identity is, in order of preference: the VERIFIED bearer subject in
    OAuth mode (CR-06, review 2026-09-28 — a bearer that does not verify no
    longer mints its own bucket; see below), the presented `x-api-key`
    fingerprint otherwise (already verified upstream by APIKeyAuthMiddleware
    when x-api-key mode is wired — see server_bootstrap.py), else the
    resolved client IP (CR-01: through TRUSTED_PROXY_IPS +
    CF-Connecting-IP, not the raw peer, which behind a reverse proxy is one
    address for every caller). Only a truncated SHA-256 of a credential is ever
    used or logged, never the credential.

    CR-06: an UNVERIFIED bearer used to be keyed on its own fingerprint —
    any string starting with "Bearer " got a fresh, empty bucket, so a
    caller with no real credential could reset its own limit on every
    request just by varying the token text. A bearer is now verified
    against the OAuth provider (`load_access_token`, cheap — a JWT
    signature check or a constant-time compare against the two static
    bearers, no DB round trip) when one is wired; verified tokens key on
    the token's subject (stable across a refresh, unlike the token text
    itself); anything that does not verify falls back to the resolved
    client IP, same as presenting no credential at all.

    Buckets are the repo's own `util.rate_limiter.TokenBucket`, held in a
    dedicated `RateLimiter` instance (NOT the outbound singleton), and the
    bucket table is pruned so a stream of distinct identities cannot grow it
    without bound.
    """

    #: Identities tracked at once. Beyond this, full (idle) buckets are
    #: dropped; an idle bucket is indistinguishable from a fresh one.
    MAX_TRACKED_IDENTITIES = 4096

    def __init__(self, app, requests_per_minute: Optional[int] = None, auth_provider=None):
        from .config.constants import DEFAULT_RATE_LIMIT_RPM
        from .util.rate_limiter import RateLimiter, RateLimitConfig

        if requests_per_minute is None:
            try:
                requests_per_minute = int(
                    os.environ.get("CITATIONS_INBOUND_RATE_LIMIT_RPM", "")
                    or DEFAULT_RATE_LIMIT_RPM
                )
            except ValueError:
                requests_per_minute = DEFAULT_RATE_LIMIT_RPM
        self.app = app
        self.requests_per_minute = requests_per_minute
        # CR-06: the OAuth provider, when wired (OAuth mode only), so a
        # presented bearer can be verified before it is trusted as an
        # identity. None in mode=none — x-api-key is the credential there.
        self._auth_provider = auth_provider
        # Per-identity buckets only: the shared global bucket is set wide
        # open so one busy caller cannot rate-limit everyone else.
        # endpoint_share_divisor=1.0: here the per-identity buckets ARE the
        # control, so each identity gets the full advertised budget rather
        # than the outbound limiter's per-endpoint share of a global ceiling.
        self._limiter = RateLimiter(
            RateLimitConfig(
                requests_per_minute=requests_per_minute,
                endpoint_share_divisor=1.0,
            )
        )
        self._limiter.global_bucket.capacity = float("inf")
        self._limiter.global_bucket.tokens = float("inf")

    @staticmethod
    def _fingerprint(secret: str) -> str:
        import hashlib

        return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:16]

    async def _verify_bearer(self, token: str):
        """The verified AccessToken for `token`, or None when it does not
        verify or there is no provider to check it against. Never raises —
        an unverifiable token just falls back to the IP key."""
        if self._auth_provider is None:
            return None
        try:
            return await self._auth_provider.load_access_token(token)
        except Exception:
            return None

    async def _identity(self, scope) -> str:
        from .shared.client_ip import client_ip_from_scope

        headers = {name: value for name, value in scope.get("headers", [])}
        authorization = headers.get(b"authorization", b"").decode("latin-1")
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
            access_token = await self._verify_bearer(token)
            if access_token is not None:
                subject = getattr(access_token, "subject", None) or getattr(
                    access_token, "client_id", ""
                )
                return "identity:" + self._fingerprint(str(subject))
            # CR-06: an unverified bearer must not mint its own bucket.
            return "ip:" + client_ip_from_scope(scope)
        api_key = headers.get(b"x-api-key", b"").decode("latin-1")
        if api_key:
            return "key:" + self._fingerprint(api_key)
        return "ip:" + client_ip_from_scope(scope)

    def _prune(self) -> None:
        buckets = self._limiter.buckets
        if len(buckets) <= self.MAX_TRACKED_IDENTITIES:
            return
        idle = [key for key, bucket in buckets.items() if bucket.tokens >= bucket.capacity]
        for key in idle:
            del buckets[key]
        if len(buckets) > self.MAX_TRACKED_IDENTITIES:
            # Every tracked identity is mid-window; start a fresh table
            # rather than growing without bound.
            buckets.clear()

    async def _send_429(self, scope, receive, send) -> None:
        from starlette.responses import JSONResponse

        response = JSONResponse(
            {
                "error": "Rate limit exceeded",
                "message": (
                    "Too many requests. This server allows "
                    f"{self.requests_per_minute} requests per minute per client."
                ),
            },
            status_code=429,
            headers={"Retry-After": "60"},
        )
        await response(scope, receive, send)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if scope.get("path") == "/health":
            await self.app(scope, receive, send)
            return

        identity = await self._identity(scope)
        self._prune()
        if not await self._limiter.acquire(endpoint=identity):
            # Identity is a truncated hash or a peer address, never a
            # credential; still logged without the value itself.
            logger.warning("Inbound rate limit exceeded for one client")
            await self._send_429(scope, receive, send)
            return
        await self.app(scope, receive, send)


#: Browser security headers, at module scope (they were rebuilt per request
#: inside __init__ as a function-local UPPER_CASE name, R-1). script-src no
#: longer carries 'unsafe-inline': this server has no inline-script consumer,
#: the MCP App views are served as iframe resources under their own
#: ResourceCSP. Referrer-Policy matters most of the additions — /auth/select
#: carries a capability token in its query string, which a Referer header
#: would hand to Google or Microsoft (S-23).
SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
    (b"referrer-policy", b"no-referrer"),
    (b"permissions-policy", b"geolocation=(), microphone=(), camera=()"),
    (b"cache-control", b"no-store"),
    (
        b"content-security-policy",
        b"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        b"frame-ancestors 'none'; base-uri 'none'",
    ),
]


class SecurityHeadersMiddleware:
    """Adds browser security headers to all HTTP responses."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def patched_send(message):
            if message["type"] == "http.response.start":
                # REPLACE rather than extend: appending meant a duplicate
                # header from an inner handler won by order, so
                # X-Frame-Options could arrive twice with different values
                # and the browser picked the first (S-23).
                names = {name for name, _ in SECURITY_HEADERS}
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() not in names
                ]
                headers.extend(SECURITY_HEADERS)
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, patched_send)
