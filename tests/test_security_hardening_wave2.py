"""Security fixes that had no coverage: headers, auth events, DCR bounds.

- S-23: security headers were appended, so a duplicate X-Frame-Options from
  an inner handler won by order; Referrer-Policy was absent while
  /auth/select carries a capability token in its query string.
- S-26: `auth_failure` was implemented and had no production caller, so in
  mode=none the security log contained no auth events at all.
- S-09: /register wrote a row per unauthenticated call, was unthrottled, and
  cached into a dict with no eviction.
- S-27: the OAuth limiter's bucket table had no eviction.
- S-34: the decrypted API key was written into os.environ.
- S-07: the "secure" store is plaintext on Linux and its mode was set at
  write time only.
"""

import os
import stat

import pytest

from uspto_enriched_citation_mcp import middleware as middleware_module
from uspto_enriched_citation_mcp.auth.provider import _FixedWindowRateLimiter
from uspto_enriched_citation_mcp.middleware import (
    SECURITY_HEADERS,
    APIKeyAuthMiddleware,
    SecurityHeadersMiddleware,
)


def _scope(path="/mcp", headers=None):
    return {
        "type": "http",
        "path": path,
        "method": "POST",
        "headers": headers or [],
        "client": ("10.0.0.1", 51234),
        "query_string": b"",
        "scheme": "https",
        "server": ("testserver", 443),
    }


# ------------------------------------------------------------------ headers


@pytest.mark.asyncio
async def test_security_headers_replace_rather_than_append():
    async def _app(scope, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                # An inner handler setting its own, weaker, value.
                "headers": [(b"x-frame-options", b"SAMEORIGIN")],
            }
        )

    sent = []

    async def _send(message):
        sent.append(message)

    await SecurityHeadersMiddleware(_app)(_scope(), None, _send)

    headers = sent[0]["headers"]
    frame_options = [v for name, v in headers if name.lower() == b"x-frame-options"]
    assert frame_options == [b"DENY"]


@pytest.mark.asyncio
async def test_referrer_policy_and_the_other_added_headers_are_present():
    async def _app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})

    sent = []

    async def _send(message):
        sent.append(message)

    await SecurityHeadersMiddleware(_app)(_scope(), None, _send)

    names = {name.lower() for name, _ in sent[0]["headers"]}
    for expected in (
        b"referrer-policy",
        b"permissions-policy",
        b"cache-control",
        b"content-security-policy",
    ):
        assert expected in names


def test_csp_no_longer_allows_inline_script():
    csp = dict(SECURITY_HEADERS)[b"content-security-policy"]
    assert b"script-src 'self';" in csp
    assert b"'unsafe-inline'" not in csp.split(b"style-src")[0]
    assert b"frame-ancestors 'none'" in csp
    assert b"base-uri 'none'" in csp


# ------------------------------------------------------------- auth events


@pytest.mark.asyncio
async def test_bad_api_key_emits_a_security_event(monkeypatch):
    events = []
    monkeypatch.setattr(
        middleware_module,
        "_emit_auth_event",
        lambda success, reason="": events.append((success, reason)),
    )
    monkeypatch.setenv("INTERNAL_AUTH_SECRET", "s" * 40)
    monkeypatch.setattr(
        "uspto_enriched_citation_mcp.shared_secure_storage.get_internal_auth_secret",
        lambda: None,
    )

    async def _app(scope, receive, send):
        raise AssertionError("must not reach the app")

    sent = []

    async def _send(message):
        sent.append(message)

    await APIKeyAuthMiddleware(_app)(
        _scope(headers=[(b"x-api-key", b"wrong")]), None, _send
    )

    assert sent[0]["status"] == 401
    assert events == [(False, "invalid x-api-key")]


@pytest.mark.asyncio
async def test_a_valid_api_key_emits_no_event(monkeypatch):
    """One record per accepted request would be the loudest line in the log."""
    events = []
    monkeypatch.setattr(
        middleware_module,
        "_emit_auth_event",
        lambda success, reason="": events.append((success, reason)),
    )
    secret = "s" * 40
    monkeypatch.setenv("INTERNAL_AUTH_SECRET", secret)
    monkeypatch.setattr(
        "uspto_enriched_citation_mcp.shared_secure_storage.get_internal_auth_secret",
        lambda: None,
    )

    reached = []

    async def _app(scope, receive, send):
        reached.append(True)

    await APIKeyAuthMiddleware(_app)(
        _scope(headers=[(b"x-api-key", secret.encode())]), None, lambda m: None
    )

    assert reached == [True]
    assert events == []


# ------------------------------------------------------- limiter and cache


def test_oauth_limiter_prunes_expired_windows():
    limiter = _FixedWindowRateLimiter(max_requests=100, window_seconds=0.0)
    limiter._MAX_TRACKED_KEYS = 10

    for i in range(30):
        limiter.allow(f"key-{i}")

    # Every window expires immediately, so the sweep keeps the table bounded.
    assert len(limiter._buckets) <= limiter._MAX_TRACKED_KEYS


def test_oauth_limiter_still_rejects_over_budget():
    limiter = _FixedWindowRateLimiter(max_requests=3, window_seconds=60.0)
    assert [limiter.allow("one-ip") for _ in range(4)] == [True, True, True, False]


# -------------------------------------------------------------- key storage


def test_settings_does_not_write_the_key_into_the_environment(monkeypatch):
    from uspto_enriched_citation_mcp.config.settings import Settings

    monkeypatch.delenv("USPTO_API_KEY", raising=False)
    monkeypatch.setattr(
        "uspto_enriched_citation_mcp.shared_secure_storage.get_uspto_api_key",
        lambda: "k" * 40,
    )

    settings = Settings.load_from_env()

    assert settings.uspto_ecitation_api_key == "k" * 40
    assert "USPTO_API_KEY" not in os.environ


@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes")
def test_plaintext_key_file_is_refused_when_world_readable(tmp_path, monkeypatch):
    from uspto_enriched_citation_mcp.shared_secure_storage import UnifiedSecureStorage

    key_file = tmp_path / ".uspto_api_key"
    key_file.write_text("k" * 40, encoding="utf-8")
    key_file.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)

    storage = UnifiedSecureStorage()
    assert storage._load_single_key(key_file, "USPTO API key") is None

    key_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
    assert storage._load_single_key(key_file, "USPTO API key") == "k" * 40


# ------------------------------------------------------- U-1: SDK-side PKCE


def test_the_sdk_rejects_an_unregistered_redirect_uri():
    """U-1: three reports flagged PKCE verification and redirect_uri
    allowlisting as UNVERIFIED because both live in the MCP SDK's auth
    handlers, not in this repo. They ARE enforced — this pins the half that
    is reachable from a unit test, so an SDK upgrade that dropped it fails
    here rather than in production."""
    from pydantic import AnyUrl

    from mcp.shared.auth import (
        InvalidRedirectUriError,
        OAuthClientInformationFull,
    )

    registered = AnyUrl("https://claude.ai/api/mcp/auth_callback")
    client = OAuthClientInformationFull(client_id="c1", redirect_uris=[registered])

    assert str(client.validate_redirect_uri(registered)).startswith(
        "https://claude.ai/"
    )

    with pytest.raises(InvalidRedirectUriError):
        client.validate_redirect_uri(AnyUrl("https://attacker.example/cb"))


def test_the_sdk_token_handler_verifies_the_pkce_challenge():
    """The other half of U-1. The comparison lives in the SDK's token
    handler; assert the handler still performs it, since this server stores
    `code_challenge` on the authorization code and relies on that check."""
    import inspect

    from mcp.server.auth.handlers import token as token_handler

    source = inspect.getsource(token_handler)
    assert "hashed_code_verifier != auth_code.code_challenge" in source
    assert "redirect_uri did not match the one used when creating auth code" in source
