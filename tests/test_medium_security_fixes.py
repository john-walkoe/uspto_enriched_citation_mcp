"""Regression tests for Phase 2 (Medium) audit-remediation fixes.

M1 — x-api-key guard fails open: main() now refuses to start HTTP transport
     (SystemExit(1)) when CITATIONS_AUTH_MODE != oauth and no
     INTERNAL_AUTH_SECRET resolves.
M3 — MAX_REQUEST_SIZE_BYTES enforcement: RequestSizeLimitMiddleware caps
     inbound request bodies (413) both via Content-Length and streamed byte
     count.
M5 — get_citation_statistics / get_citation_details validate their inputs
     before any service call; CitationService.get_statistics charges the
     rate limiter for its 6x fan-out cost up front.
M6 — SecurityLogger no longer persists raw query/criteria text.
M2 — per-IP rate limiting on the public OAuth surface (/authorize, /token,
     /auth/callback/{idp}).
"""

from __future__ import annotations

import json
import time

import httpx
import pytest

from uspto_enriched_citation_mcp import main, runtime


# --------------------------------------------------------------------- M1


def test_main_refuses_http_without_secret(monkeypatch):
    """HTTP transport + mode=none + no resolvable secret -> SystemExit(1),
    checked before any other startup work (no USPTO_API_KEY needed)."""
    monkeypatch.setenv("FASTMCP_TRANSPORT", "http")
    monkeypatch.delenv("INTERNAL_AUTH_SECRET", raising=False)
    monkeypatch.setattr(main, "_AUTH_PROVIDER", None)

    import uspto_enriched_citation_mcp.shared_secure_storage as sss

    monkeypatch.setattr(sss, "get_internal_auth_secret", lambda: None)

    with pytest.raises(SystemExit) as exc_info:
        main.main()
    assert exc_info.value.code == 1


def _isolate_service_globals(monkeypatch):
    """Force initialize_services() to run fresh and not leak state: snapshot
    every lazily-initialized global as None so monkeypatch's teardown resets
    them regardless of what the call under test does to them.

    Phase 6B seam switch: the service singletons now live on the `runtime`
    module (tools/* access them via `runtime.<attr>` lookups, not a name
    bound at import time), so they must be patched there — patching
    `main.api_client` etc. would only rebind main.py's back-compat re-export.
    """
    from uspto_enriched_citation_mcp.config import settings as settings_module

    monkeypatch.setattr(settings_module, "settings", None)
    for name in (
        "api_client",
        "oa_client",
        "field_manager",
        "citation_service",
        "oa_citation_service",
    ):
        monkeypatch.setattr(runtime, name, None)


def test_main_starts_http_with_secret(monkeypatch):
    """The same startup gate does not fire once a secret resolves — proven
    by reaching past the gate to the (mocked) uvicorn.run() call."""
    _isolate_service_globals(monkeypatch)
    monkeypatch.setenv("USPTO_API_KEY", "x" * 30)
    monkeypatch.setenv("FASTMCP_TRANSPORT", "http")
    monkeypatch.setenv("INTERNAL_AUTH_SECRET", "shared-secret")
    monkeypatch.setattr(main, "_AUTH_PROVIDER", None)

    import uspto_enriched_citation_mcp.shared_secure_storage as sss

    monkeypatch.setattr(sss, "get_internal_auth_secret", lambda: None)

    called = {}

    def fake_run(app, host, port, access_log):
        called["ran"] = True

    import uvicorn

    monkeypatch.setattr(uvicorn, "run", fake_run)

    main.main()
    assert called.get("ran") is True


def test_main_oauth_mode_exempt_from_secret_gate(monkeypatch):
    """CITATIONS_AUTH_MODE=oauth (_AUTH_PROVIDER set) skips the gate even
    with no INTERNAL_AUTH_SECRET — bearer auth protects the surface instead."""
    _isolate_service_globals(monkeypatch)
    monkeypatch.setenv("USPTO_API_KEY", "x" * 30)
    monkeypatch.setenv("FASTMCP_TRANSPORT", "http")
    monkeypatch.delenv("INTERNAL_AUTH_SECRET", raising=False)

    class _FakeProvider:
        pass

    monkeypatch.setattr(main, "_AUTH_PROVIDER", _FakeProvider())

    import uspto_enriched_citation_mcp.shared_secure_storage as sss

    monkeypatch.setattr(sss, "get_internal_auth_secret", lambda: None)

    called = {}

    def fake_run(app, host, port, access_log):
        called["ran"] = True

    import uvicorn

    monkeypatch.setattr(uvicorn, "run", fake_run)

    main.main()
    assert called.get("ran") is True


# --------------------------------------------------------------------- M3


@pytest.mark.asyncio
async def test_request_size_limit_rejects_large_content_length():
    """Content-Length over the cap -> 413, inner app never invoked."""

    async def inner_app(scope, receive, send):
        raise AssertionError("inner app must not run past the size cap")

    mw = main.RequestSizeLimitMiddleware(inner_app, max_request_size=100)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mw), base_url="http://test"
    ) as http:
        resp = await http.post("/mcp", content=b"x" * 200)
    assert resp.status_code == 413
    assert resp.json()["max_allowed"] == 100


@pytest.mark.asyncio
async def test_request_size_limit_rejects_streamed_body_without_content_length():
    """Chunked body (no Content-Length) is still capped via running byte count."""

    async def inner_app(scope, receive, send):
        # A real app would read the body via `receive` in a loop; reading
        # once is enough to trigger the wrapped receive's cap check.
        while True:
            message = await receive()
            if not message.get("more_body", False):
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    mw = main.RequestSizeLimitMiddleware(inner_app, max_request_size=10)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/mcp",
        "headers": [],  # no content-length: only the streamed count applies
        "query_string": b"",
    }
    chunks = [b"a" * 5, b"b" * 5, b"c" * 5]  # 15 bytes total > cap of 10

    async def receive():
        if chunks:
            body = chunks.pop(0)
            return {
                "type": "http.request",
                "body": body,
                "more_body": bool(chunks),
            }
        return {"type": "http.request", "body": b"", "more_body": False}

    sent = []

    async def send(message):
        sent.append(message)

    await mw(scope, receive, send)

    assert sent[0]["type"] == "http.response.start"
    assert sent[0]["status"] == 413


@pytest.mark.asyncio
async def test_request_size_limit_allows_small_body():
    async def inner_app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    mw = main.RequestSizeLimitMiddleware(inner_app, max_request_size=100)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mw), base_url="http://test"
    ) as http:
        resp = await http.post("/mcp", content=b"small")
    assert resp.status_code == 200


# --------------------------------------------------------------------- M5


class _NetworkGuard:
    """Raises on any use — proves a tool returned before touching a
    service/client."""

    def __getattr__(self, name):
        raise AssertionError(f"unexpected service/network access: {name!r}")


@pytest.fixture()
def _no_network(monkeypatch):
    # Phase 6B seam switch: patch on `runtime`, not `main` — see
    # _isolate_service_globals above for why.
    guard = _NetworkGuard()
    monkeypatch.setattr(runtime, "api_client", guard)
    monkeypatch.setattr(runtime, "oa_client", guard)
    monkeypatch.setattr(runtime, "citation_service", guard)
    monkeypatch.setattr(runtime, "oa_citation_service", guard)
    monkeypatch.setattr(runtime, "field_manager", guard)


@pytest.mark.asyncio
async def test_get_citation_statistics_rejects_invalid_criteria(_no_network):
    result = await main.get_citation_statistics(criteria="techCenter:(unbalanced")
    assert result["status"] == "error"
    assert result["code"] == 400


@pytest.mark.asyncio
async def test_get_citation_statistics_rejects_oversized_criteria(_no_network):
    from uspto_enriched_citation_mcp.config.constants import MAX_QUERY_LENGTH

    result = await main.get_citation_statistics(
        criteria="techCenter:2100 " * (MAX_QUERY_LENGTH // 10)
    )
    assert result["status"] == "error"
    assert result["code"] == 400


@pytest.mark.asyncio
async def test_get_citation_details_rejects_malformed_citation_id(_no_network):
    result = await main.get_citation_details(citation_id="not-a-valid-id")
    assert result["status"] == "error"
    assert result["code"] == 400


@pytest.mark.asyncio
async def test_get_citation_details_accepts_well_formed_id_format(monkeypatch):
    """A correctly-formed 32-char hex id passes the format check (it may
    still fail downstream without network access — we only assert the
    format gate itself doesn't reject it before reaching the service)."""

    class _StubService:
        async def get_details(self, citation_id, include_context):
            assert citation_id == "0de7ea10c59e03dab218a40dece9dffd"
            return {"status": "success", "citation": {}}

    # Phase 6B seam switch: patch on `runtime`, not `main` — see
    # _isolate_service_globals above for why.
    monkeypatch.setattr(runtime, "initialize_services", lambda: None)
    monkeypatch.setattr(runtime, "citation_service", _StubService())

    result = await main.get_citation_details(
        citation_id="0de7ea10c59e03dab218a40dece9dffd"
    )
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_citation_service_get_statistics_charges_rate_limiter(monkeypatch):
    """CitationService.get_statistics acquires the 6x fan-out cost from the
    rate limiter up front and never issues a sub-query when denied."""
    from uspto_enriched_citation_mcp.services.citation_service import CitationService
    from uspto_enriched_citation_mcp.util import rate_limiter as rl

    rl.reset_rate_limiter()
    limiter = rl.get_rate_limiter(rl.RateLimitConfig(requests_per_minute=60))

    acquired = {}

    async def fake_acquire(endpoint="default", tokens=1):
        acquired["endpoint"] = endpoint
        acquired["tokens"] = tokens
        return False  # simulate exhausted bucket

    monkeypatch.setattr(limiter, "acquire", fake_acquire)

    class _NoCallClient:
        async def search_citations(self, *args, **kwargs):
            raise AssertionError("must not fan out when the rate limiter denies")

    service = CitationService(_NoCallClient(), field_manager=None)
    result = await service.get_statistics(criteria="techCenter:2100")

    assert result["status"] == "error"
    assert acquired["endpoint"] == "get_citation_statistics"
    assert acquired["tokens"] == 6

    rl.reset_rate_limiter()


# --------------------------------------------------------------------- M6


def test_security_logger_never_persists_raw_query_text(tmp_path):
    """query_validation_failure/excessive_wildcards must not embed the raw
    query text anywhere in the emitted JSON event — only length + a SHA-256
    fingerprint prefix."""
    from unittest.mock import patch

    from uspto_enriched_citation_mcp.util.security_logger import SecurityLogger

    logger = SecurityLogger(name="test_no_raw_query", log_dir=str(tmp_path))
    secret_query = "firstApplicantNameText:\"Confidential Client Matter 12345\""

    with patch.object(logger.logger, "log") as mock_log:
        logger.query_validation_failure(
            query=secret_query, reason="test", severity="medium"
        )
        logged = mock_log.call_args[0][1]
        assert secret_query not in logged
        payload = json.loads(logged)
        assert "query_preview" not in payload
        assert payload["query_len"] == len(secret_query)
        assert len(payload["query_sha"]) == 12

    with patch.object(logger.logger, "log") as mock_log:
        logger.excessive_wildcards(query=secret_query, wildcard_count=99)
        logged = mock_log.call_args[0][1]
        assert secret_query not in logged
        payload = json.loads(logged)
        assert "query_preview" not in payload
        assert payload["query_len"] == len(secret_query)


def test_query_validator_injection_events_never_persist_raw_query():
    """validate_lucene_syntax's injection_attempt / invalid_field_access
    call sites pass fingerprints, not raw criteria."""
    import json as _json
    from unittest.mock import patch

    from uspto_enriched_citation_mcp.util.query_validator import validate_lucene_syntax
    from uspto_enriched_citation_mcp.util.security_logger import get_security_logger

    secret_query = "internalSecretField:<script>confidential-matter-9001</script>"
    logger = get_security_logger()
    with patch.object(logger.logger, "log") as mock_log:
        is_valid, _ = validate_lucene_syntax(secret_query)
        assert is_valid is False
        assert mock_log.called
        for call in mock_log.call_args_list:
            logged = call[0][1]
            assert "confidential-matter-9001" not in logged
            payload = _json.loads(logged)
            assert "query_preview" not in payload


# --------------------------------------------------------------------- M2


def test_fixed_window_limiter_allows_then_denies():
    from uspto_enriched_citation_mcp.auth.provider import _FixedWindowRateLimiter

    limiter = _FixedWindowRateLimiter(max_requests=3, window_seconds=60.0)
    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is False  # 4th request in the window
    # A different key has its own independent budget.
    assert limiter.allow("5.6.7.8") is True


def test_fixed_window_limiter_resets_after_window():
    from uspto_enriched_citation_mcp.auth.provider import _FixedWindowRateLimiter

    limiter = _FixedWindowRateLimiter(max_requests=1, window_seconds=0.1)
    assert limiter.allow("ip") is True
    assert limiter.allow("ip") is False
    time.sleep(0.2)
    assert limiter.allow("ip") is True


@pytest.mark.asyncio
async def test_callback_endpoint_429_after_limit_exceeded():
    """The rate-limit check runs before txn/idp lookup, so a second request
    from the same IP is refused with 429 even with a nonsense txn/code."""
    from uspto_enriched_citation_mcp.auth.provider import _FixedWindowRateLimiter

    from .test_auth_provider import get_request

    provider, _ = _make_provider_for_m2()
    provider._oauth_rate_limiter = _FixedWindowRateLimiter(
        max_requests=1, window_seconds=60.0
    )

    req1 = get_request(
        "/auth/callback/google", "state=nope&code=x", {"idp": "google"}
    )
    req1.scope["client"] = ("9.9.9.9", 12345)
    first = await provider._callback_endpoint(req1)
    assert first.status_code == 400  # unknown txn — but allowed past the limiter

    req2 = get_request(
        "/auth/callback/google", "state=nope2&code=y", {"idp": "google"}
    )
    req2.scope["client"] = ("9.9.9.9", 12345)
    second = await provider._callback_endpoint(req2)
    assert second.status_code == 429


def _make_provider_for_m2():
    from uspto_enriched_citation_mcp.auth.provider import CitationsAuthProvider

    from .test_auth_provider import FakeUserStore, make_settings

    store = FakeUserStore()
    provider = CitationsAuthProvider(make_settings(), store)  # type: ignore[arg-type]
    return provider, store


@pytest.mark.asyncio
async def test_authorize_and_token_routes_wrapped_with_rate_limiter():
    provider, _ = _make_provider_for_m2()
    routes = provider.get_routes()
    from uspto_enriched_citation_mcp.auth.provider import _RateLimitedASGIApp

    wrapped = {
        r.path: r.app for r in routes if getattr(r, "path", None) in ("/authorize", "/token")
    }
    assert set(wrapped) == {"/authorize", "/token"}
    for app in wrapped.values():
        assert isinstance(app, _RateLimitedASGIApp)
