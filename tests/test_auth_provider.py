"""Unit tests for the dual-IdP OAuth authorization server (auth/provider.py).

Ported from edgar_mcp tests/unit/test_auth_provider.py. A FakeUserStore stands
in for the SQLite McpUserStore in provider tests; the store itself is covered
against a real temp-file SQLite DB in TestMcpUserStore. Upstream IdP calls are
monkeypatched where a test exercises the callback path.
"""
from __future__ import annotations

import time
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from mcp.server.auth.provider import AuthorizationParams, TokenError
from mcp.shared.auth import OAuthClientInformationFull
from pydantic import AnyUrl
from starlette.requests import Request

from uspto_enriched_citation_mcp.auth.provider import (  # noqa: E402
    SCOPE_ADMIN,
    SCOPE_USER,
    CitationsAuthProvider,
    build_auth_provider,
    scopes_for_role,
)
from uspto_enriched_citation_mcp.auth.store import McpUserStore  # noqa: E402
from uspto_enriched_citation_mcp.config.settings import Settings  # noqa: E402


class FakeUserStore:
    """In-memory stand-in for McpUserStore."""

    def __init__(self) -> None:
        self.users: dict[str, dict[str, Any]] = {}
        self.clients: dict[str, dict[str, Any]] = {}
        self.codes: dict[str, dict[str, Any]] = {}
        self.refresh: dict[str, dict[str, Any]] = {}
        self.logins: list[tuple[str, str]] = []

    async def get_user(self, email: str) -> dict[str, Any] | None:
        return self.users.get(email.strip().lower())

    async def record_login(self, email: str, idp: str) -> None:
        self.logins.append((email, idp))

    async def put_client(self, client_id: str, payload: dict[str, Any]) -> None:
        self.clients[client_id] = payload

    async def get_client(self, client_id: str) -> dict[str, Any] | None:
        return self.clients.get(client_id)

    async def put_code(
        self, code: str, payload: dict[str, Any], ttl_seconds: int
    ) -> None:
        self.codes[code] = payload

    async def take_code(self, code: str) -> dict[str, Any] | None:
        return self.codes.pop(code, None)

    async def put_refresh(
        self, token: str, *, client_id: str, email: str,
        scopes: list[str], ttl_seconds: int,
    ) -> None:
        import datetime

        self.refresh[token] = {
            "client_id": client_id,
            "email": email,
            "scopes": scopes,
            "expires_at": datetime.datetime.now(datetime.UTC)
            + datetime.timedelta(seconds=ttl_seconds),
            "revoked": False,
        }

    async def get_refresh(self, token: str) -> dict[str, Any] | None:
        row = self.refresh.get(token)
        if row is None or row["revoked"]:
            return None
        return dict(row)

    async def revoke_refresh(self, token: str) -> None:
        if token in self.refresh:
            self.refresh[token]["revoked"] = True


def make_settings(**overrides: Any) -> Settings:
    base = dict(
        USPTO_API_KEY="x" * 30,
        CITATIONS_AUTH_MODE="oauth",
        CITATIONS_AUTH_BASE_URL="https://mcp.example.com",
        CITATIONS_AUTH_JWT_SECRET="x" * 48,
        CITATIONS_AUTH_GOOGLE_CLIENT_ID="google-client",
        CITATIONS_AUTH_GOOGLE_CLIENT_SECRET="google-secret",
        CITATIONS_AUTH_MS_CLIENT_ID="ms-client",
        CITATIONS_AUTH_MS_CLIENT_SECRET="ms-secret",
        CITATIONS_AUTH_INTERNAL_TOKEN="internal-static-token",
    )
    base.update(overrides)
    return Settings(_env_file=None, **base)  # type: ignore[call-arg]


def make_provider(
    store: FakeUserStore | None = None, **overrides: Any
) -> tuple[CitationsAuthProvider, FakeUserStore]:
    store = store or FakeUserStore()
    provider = CitationsAuthProvider(make_settings(**overrides), store)  # type: ignore[arg-type]
    return provider, store


def make_client(client_id: str = "client-1") -> OAuthClientInformationFull:
    return OAuthClientInformationFull(
        client_id=client_id,
        redirect_uris=[AnyUrl("http://127.0.0.1:33418/callback")],
    )


def make_params(**overrides: Any) -> AuthorizationParams:
    base: dict[str, Any] = dict(
        state="client-state",
        scopes=[SCOPE_USER],
        code_challenge="challenge",
        redirect_uri=AnyUrl("http://127.0.0.1:33418/callback"),
        redirect_uri_provided_explicitly=True,
    )
    base.update(overrides)
    return AuthorizationParams(**base)


def get_request(path: str, query: str, path_params: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "query_string": query.encode(),
        "headers": [],
        "path_params": path_params,
    }
    return Request(scope)


# --------------------------------------------------------------------- config


def test_build_auth_provider_rejects_http_base_url() -> None:
    with pytest.raises(ValueError, match="https"):
        build_auth_provider(
            make_settings(CITATIONS_AUTH_BASE_URL="http://fellow.example.com"),
            FakeUserStore(),  # type: ignore[arg-type]
        )


def test_build_auth_provider_rejects_short_secret() -> None:
    with pytest.raises(ValueError, match="32"):
        build_auth_provider(
            make_settings(CITATIONS_AUTH_JWT_SECRET="short"),
            FakeUserStore(),  # type: ignore[arg-type]
        )


def test_provider_requires_at_least_one_idp() -> None:
    with pytest.raises(ValueError, match="at least one IdP"):
        make_provider(
            CITATIONS_AUTH_GOOGLE_CLIENT_ID="", CITATIONS_AUTH_MS_CLIENT_ID=""
        )


def test_scopes_for_role() -> None:
    assert scopes_for_role("user") == [SCOPE_USER]
    assert scopes_for_role("admin") == [SCOPE_USER, SCOPE_ADMIN]


# ------------------------------------------------------------------ authorize


@pytest.mark.asyncio
async def test_authorize_returns_chooser_url_with_txn() -> None:
    provider, _ = make_provider()
    url = await provider.authorize(make_client(), make_params())
    parsed = urlparse(url)
    assert parsed.path == "/auth/select"
    txn = parse_qs(parsed.query)["txn"][0]
    assert txn in provider._txns
    assert provider._txns[txn]["client_state"] == "client-state"


@pytest.mark.asyncio
async def test_authorize_single_idp_skips_chooser() -> None:
    provider, _ = make_provider(CITATIONS_AUTH_MS_CLIENT_ID="")
    url = await provider.authorize(make_client(), make_params())
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    q = parse_qs(urlparse(url).query)
    assert q["client_id"] == ["google-client"]
    assert q["redirect_uri"] == ["https://mcp.example.com/auth/callback/google"]


@pytest.mark.asyncio
async def test_start_endpoint_redirects_to_upstream() -> None:
    # Default tenant is "common" (any-org + personal MSA — matches the
    # staging Entra app registration).
    provider, _ = make_provider()
    url = await provider.authorize(make_client(), make_params())
    txn = parse_qs(urlparse(url).query)["txn"][0]
    resp = await provider._start_endpoint(
        get_request("/auth/start/microsoft", f"txn={txn}", {"idp": "microsoft"})
    )
    assert resp.status_code == 302
    target = resp.headers["location"]
    assert target.startswith(
        "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?"
    )
    assert parse_qs(urlparse(target).query)["state"] == [txn]


@pytest.mark.asyncio
async def test_select_endpoint_rejects_unknown_txn() -> None:
    provider, _ = make_provider()
    resp = await provider._select_endpoint(
        get_request("/auth/select", "txn=nope", {})
    )
    assert resp.status_code == 400


# ------------------------------------------------------------------- callback


async def run_callback(
    provider: CitationsAuthProvider,
    monkeypatch: pytest.MonkeyPatch,
    claims: dict[str, Any],
    idp: str = "google",
):
    url = await provider.authorize(make_client(), make_params())
    txn = parse_qs(urlparse(url).query)["txn"][0]

    async def fake_exchange(idp_: str, code: str, nonce: str) -> dict[str, Any]:
        return claims

    monkeypatch.setattr(provider, "_exchange_and_verify", fake_exchange)
    return await provider._callback_endpoint(
        get_request(f"/auth/callback/{idp}", f"state={txn}&code=upstream", {"idp": idp})
    )


@pytest.mark.asyncio
async def test_callback_registered_user_redirects_with_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider, store = make_provider()
    store.users["jane@firm.com"] = {
        "email": "jane@firm.com", "role": "user", "active": True,
        "display_name": None, "last_login_idp": None,
    }
    resp = await run_callback(
        provider, monkeypatch,
        {"email": "Jane@Firm.com", "email_verified": True, "name": "Jane"},
    )
    assert resp.status_code == 302
    target = urlparse(resp.headers["location"])
    q = parse_qs(target.query)
    assert q["state"] == ["client-state"]
    code = q["code"][0]
    assert store.codes[code]["email"] == "jane@firm.com"
    assert store.codes[code]["scopes"] == [SCOPE_USER]
    assert store.logins == [("jane@firm.com", "google")]


@pytest.mark.asyncio
async def test_callback_unregistered_user_403(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider, store = make_provider()
    resp = await run_callback(
        provider, monkeypatch,
        {"email": "stranger@example.com", "email_verified": True},
    )
    assert resp.status_code == 403
    assert not store.codes


@pytest.mark.asyncio
async def test_callback_inactive_user_403(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider, store = make_provider()
    store.users["jane@firm.com"] = {
        "email": "jane@firm.com", "role": "user", "active": False,
        "display_name": None, "last_login_idp": None,
    }
    resp = await run_callback(
        provider, monkeypatch,
        {"email": "jane@firm.com", "email_verified": True},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_callback_admin_gets_admin_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider, store = make_provider()
    store.users["boss@firm.com"] = {
        "email": "boss@firm.com", "role": "admin", "active": True,
        "display_name": None, "last_login_idp": None,
    }
    resp = await run_callback(
        provider, monkeypatch,
        {"email": "boss@firm.com", "email_verified": True},
    )
    assert resp.status_code == 302
    code = parse_qs(urlparse(resp.headers["location"]).query)["code"][0]
    assert store.codes[code]["scopes"] == [SCOPE_USER, SCOPE_ADMIN]


@pytest.mark.asyncio
async def test_callback_replay_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    provider, store = make_provider()
    store.users["jane@firm.com"] = {
        "email": "jane@firm.com", "role": "user", "active": True,
        "display_name": None, "last_login_idp": None,
    }
    url = await provider.authorize(make_client(), make_params())
    txn = parse_qs(urlparse(url).query)["txn"][0]

    async def fake_exchange(idp_: str, code: str, nonce: str) -> dict[str, Any]:
        return {"email": "jane@firm.com", "email_verified": True}

    monkeypatch.setattr(provider, "_exchange_and_verify", fake_exchange)
    req = get_request(
        "/auth/callback/google", f"state={txn}&code=up", {"idp": "google"}
    )
    first = await provider._callback_endpoint(req)
    assert first.status_code == 302
    # The transaction is consumed: replaying the same callback fails.
    second = await provider._callback_endpoint(req)
    assert second.status_code == 400


def test_email_from_claims_microsoft_upn_fallback() -> None:
    f = CitationsAuthProvider._email_from_claims
    assert f("microsoft", {"preferred_username": "John@Firm.COM"}) == "john@firm.com"
    assert f("microsoft", {"preferred_username": "not-an-email"}) == ""
    assert f("google", {"email": "A@B.com"}) == "a@b.com"
    assert f("google", {"preferred_username": "x@y.com"}) == ""


# ------------------------------------------------------- code and token flows


@pytest.mark.asyncio
async def test_code_exchange_issues_verifiable_tokens() -> None:
    provider, store = make_provider()
    client = make_client()
    store.codes["the-code"] = {
        "client_id": client.client_id,
        "redirect_uri": "http://127.0.0.1:33418/callback",
        "redirect_uri_provided_explicitly": True,
        "code_challenge": "challenge",
        "resource": None,
        "scopes": [SCOPE_USER],
        "email": "jane@firm.com",
        "idp": "google",
        "display_name": "Jane",
        "role": "user",
    }
    code = await provider.load_authorization_code(client, "the-code")
    assert code is not None
    assert code.email == "jane@firm.com"
    # Single use: the row is consumed at load.
    assert await provider.load_authorization_code(client, "the-code") is None

    token = await provider.exchange_authorization_code(client, code)
    assert token.token_type.lower() == "bearer"
    access = await provider.load_access_token(token.access_token)
    assert access is not None
    assert access.scopes == [SCOPE_USER]
    assert access.subject == "jane@firm.com"
    assert access.claims["idp"] == "google"
    assert token.refresh_token in store.refresh


@pytest.mark.asyncio
async def test_load_authorization_code_wrong_client() -> None:
    provider, store = make_provider()
    store.codes["c"] = {"client_id": "someone-else"}
    assert await provider.load_authorization_code(make_client(), "c") is None


@pytest.mark.asyncio
async def test_load_access_token_rejects_garbage_and_internal() -> None:
    provider, _ = make_provider()
    assert await provider.load_access_token("garbage") is None

    internal = await provider.load_access_token("internal-static-token")
    assert internal is not None
    assert SCOPE_ADMIN in internal.scopes

    no_internal, _ = make_provider(CITATIONS_AUTH_INTERNAL_TOKEN="")
    assert await no_internal.load_access_token("internal-static-token") is None


@pytest.mark.asyncio
async def test_wrong_audience_token_rejected() -> None:
    """A JWT minted by a sibling server (different base URL) must not verify."""
    provider_a, _ = make_provider()
    provider_b, store_b = make_provider(
        CITATIONS_AUTH_BASE_URL="https://other.example.com"
    )
    client = make_client()
    store_b.codes["c"] = {
        "client_id": client.client_id,
        "redirect_uri": "http://127.0.0.1:33418/callback",
        "redirect_uri_provided_explicitly": True,
        "code_challenge": "challenge",
        "resource": None,
        "scopes": [SCOPE_USER],
        "email": "jane@firm.com",
        "idp": "google",
        "display_name": None,
        "role": "user",
    }
    code = await provider_b.load_authorization_code(client, "c")
    assert code is not None
    token = await provider_b.exchange_authorization_code(client, code)
    # Valid at its own issuer, rejected at the sibling.
    assert await provider_b.load_access_token(token.access_token) is not None
    assert await provider_a.load_access_token(token.access_token) is None


@pytest.mark.asyncio
async def test_refresh_rotation_and_deactivation() -> None:
    provider, store = make_provider()
    client = make_client()
    store.users["jane@firm.com"] = {
        "email": "jane@firm.com", "role": "admin", "active": True,
        "display_name": None, "last_login_idp": "google",
    }
    await store.put_refresh(
        "refresh-1", client_id=client.client_id, email="jane@firm.com",
        scopes=[SCOPE_USER], ttl_seconds=3600,
    )
    loaded = await provider.load_refresh_token(client, "refresh-1")
    assert loaded is not None

    token = await provider.exchange_refresh_token(client, loaded, [])
    # Rotation: the old token is spent, a new one exists.
    assert store.refresh["refresh-1"]["revoked"] is True
    assert token.refresh_token != "refresh-1"
    # Scopes are recomputed from the CURRENT role (promoted to admin).
    access = await provider.load_access_token(token.access_token)
    assert access is not None
    assert SCOPE_ADMIN in access.scopes

    # Deactivated user: next refresh fails even with a valid token.
    store.users["jane@firm.com"]["active"] = False
    loaded2 = await provider.load_refresh_token(client, token.refresh_token)
    assert loaded2 is not None
    with pytest.raises(TokenError):
        await provider.exchange_refresh_token(client, loaded2, [])


@pytest.mark.asyncio
async def test_txn_pruning() -> None:
    provider, _ = make_provider()
    await provider.authorize(make_client(), make_params())
    for txn in provider._txns.values():
        txn["created_at"] = time.time() - 3600
    provider._prune_txns()
    assert not provider._txns


# --------------------------------------------------------- client persistence


@pytest.mark.asyncio
async def test_client_registration_roundtrip() -> None:
    provider, store = make_provider()
    client = make_client("abc")
    await provider.register_client(client)
    provider._client_cache.clear()  # force the store path
    loaded = await provider.get_client("abc")
    assert loaded is not None
    assert loaded.client_id == "abc"
    assert await provider.get_client("missing") is None


# ------------------------------------------------------------ SQLite store


class TestMcpUserStore:
    """The real store against a temp-file SQLite DB."""

    @pytest.fixture()
    def store(self, tmp_path) -> McpUserStore:
        return McpUserStore(tmp_path / "auth" / "mcp_auth.db")

    @pytest.mark.asyncio
    async def test_user_roundtrip(self, store: McpUserStore) -> None:
        assert await store.get_user("jane@firm.com") is None
        await store.upsert_user(
            "Jane@Firm.com", role="user", display_name="Jane", notes="pilot"
        )
        user = await store.get_user("jane@firm.com")
        assert user is not None
        assert user["email"] == "jane@firm.com"  # lowercased
        assert user["role"] == "user"
        assert user["active"] is True
        assert user["display_name"] == "Jane"

        # Upsert preserves display_name when not re-supplied, updates role.
        await store.upsert_user("jane@firm.com", role="admin")
        user = await store.get_user("jane@firm.com")
        assert user["role"] == "admin"
        assert user["display_name"] == "Jane"

        assert await store.set_active("jane@firm.com", False) is True
        assert (await store.get_user("jane@firm.com"))["active"] is False
        assert await store.set_active("missing@x.com", False) is False

        await store.set_active("jane@firm.com", True)
        await store.record_login("jane@firm.com", "google")
        user = await store.get_user("jane@firm.com")
        assert user["last_login_idp"] == "google"
        assert user["last_login_at"] is not None

        users = await store.list_users()
        assert [u["email"] for u in users] == ["jane@firm.com"]

    @pytest.mark.asyncio
    async def test_invalid_role_rejected(self, store: McpUserStore) -> None:
        with pytest.raises(ValueError, match="role"):
            await store.upsert_user("x@y.com", role="superuser")

    @pytest.mark.asyncio
    async def test_client_roundtrip(self, store: McpUserStore) -> None:
        await store.put_client("cid", {"client_id": "cid", "client_name": "t"})
        assert (await store.get_client("cid"))["client_name"] == "t"
        await store.put_client("cid", {"client_id": "cid", "client_name": "t2"})
        assert (await store.get_client("cid"))["client_name"] == "t2"
        assert await store.get_client("missing") is None

    @pytest.mark.asyncio
    async def test_code_single_use_and_expiry(self, store: McpUserStore) -> None:
        await store.put_code("code-1", {"email": "a@b.com"}, ttl_seconds=60)
        assert (await store.take_code("code-1"))["email"] == "a@b.com"
        assert await store.take_code("code-1") is None  # single use

        await store.put_code("code-2", {"email": "a@b.com"}, ttl_seconds=-1)
        assert await store.take_code("code-2") is None  # already expired

    @pytest.mark.asyncio
    async def test_refresh_lifecycle(self, store: McpUserStore) -> None:
        # FK (audit L10): oauth_refresh_tokens.email -> mcp_users.email.
        await store.upsert_user("a@b.com")
        await store.put_refresh(
            "tok", client_id="cid", email="a@b.com",
            scopes=["citations:user"], ttl_seconds=3600,
        )
        row = await store.get_refresh("tok")
        assert row is not None
        assert row["scopes"] == ["citations:user"]
        assert row["expires_at"].timestamp() > time.time()

        await store.revoke_refresh("tok")
        assert await store.get_refresh("tok") is None

        await store.put_refresh(
            "tok2", client_id="cid", email="a@b.com",
            scopes=["citations:user"], ttl_seconds=-1,
        )
        assert await store.get_refresh("tok2") is None  # expired


# ------------------------------------------------------------- admin gating


@pytest.mark.asyncio
async def test_admin_tools_scope_gated() -> None:
    from fastmcp import FastMCP
    from fastmcp.server.auth import AuthContext, run_auth_checks
    from fastmcp.server.auth.auth import AccessToken
    from fastmcp.tools.base import Tool

    from uspto_enriched_citation_mcp.main import _attach_admin_scope_checks

    mcp = FastMCP("gating-test")

    @mcp.tool
    def citations_manage_users() -> str:  # same name as the real admin tool
        return "ok"

    @mcp.tool
    def search_citations_minimal() -> str:
        return "ok"

    _attach_admin_scope_checks(mcp)

    tools = {
        c.name: c
        for c in mcp.local_provider._components.values()
        if isinstance(c, Tool)
    }
    assert tools["citations_manage_users"].auth
    assert not tools["search_citations_minimal"].auth

    def token(scopes: list[str]) -> AccessToken:
        return AccessToken(token="t", client_id="c", scopes=scopes)

    gate = tools["citations_manage_users"].auth
    ctx_admin = AuthContext(
        token=token([SCOPE_USER, SCOPE_ADMIN]),
        component=tools["citations_manage_users"],
    )
    ctx_user = AuthContext(
        token=token([SCOPE_USER]), component=tools["citations_manage_users"]
    )
    ctx_anon = AuthContext(token=None, component=tools["citations_manage_users"])
    assert await run_auth_checks(gate, ctx_admin) is True
    assert await run_auth_checks(gate, ctx_user) is False
    assert await run_auth_checks(gate, ctx_anon) is False


# ------------------------------------------------- HTTP surface (in-process)


@pytest.mark.asyncio
async def test_oauth_routes_mounted_on_http_app() -> None:
    """Metadata, DCR, and /authorize all served by the FastMCP HTTP app."""
    import httpx
    from fastmcp import FastMCP

    provider, store = make_provider()
    mcp = FastMCP("route-test", auth=provider)
    app = mcp.http_app(stateless_http=True)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="https://mcp.example.com",
    ) as http:
        meta = await http.get("/.well-known/oauth-authorization-server")
        assert meta.status_code == 200
        doc = meta.json()
        assert doc["issuer"].rstrip("/") == "https://mcp.example.com"
        assert doc["authorization_endpoint"] == "https://mcp.example.com/authorize"
        assert doc["token_endpoint"] == "https://mcp.example.com/token"
        assert "citations:user" in doc.get("scopes_supported", [])

        prm = await http.get("/.well-known/oauth-protected-resource/mcp")
        assert prm.status_code == 200

        # Anonymous MCP call is rejected with a bearer challenge.
        anon = await http.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            headers={
                "content-type": "application/json",
                "accept": "application/json, text/event-stream",
            },
        )
        assert anon.status_code == 401
        assert "www-authenticate" in anon.headers

        reg = await http.post(
            "/register",
            json={
                "redirect_uris": ["http://127.0.0.1:33418/callback"],
                "client_name": "pytest-client",
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "none",
            },
        )
        assert reg.status_code == 201, reg.text
        client_id = reg.json()["client_id"]
        assert client_id in store.clients  # persisted for restart survival

        authz = await http.get(
            "/authorize",
            params={
                "client_id": client_id,
                "response_type": "code",
                "redirect_uri": "http://127.0.0.1:33418/callback",
                "state": "s",
                "code_challenge": "c" * 43,
                "code_challenge_method": "S256",
            },
        )
        assert authz.status_code in (302, 307)
        assert "/auth/select?txn=" in authz.headers["location"]

        chooser = await http.get(authz.headers["location"])
        assert chooser.status_code == 200
        assert "Sign in with Microsoft" in chooser.text
        assert "Sign in with Google" in chooser.text


@pytest.mark.asyncio
async def test_mode_none_stack_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """mode=none regression: x-api-key still enforced, no OAuth routes."""
    import httpx
    from fastmcp import FastMCP
    from starlette.middleware.cors import CORSMiddleware

    import uspto_enriched_citation_mcp.shared_secure_storage as sss
    from uspto_enriched_citation_mcp.main import (
        APIKeyAuthMiddleware,
        SecurityHeadersMiddleware,
    )

    monkeypatch.setattr(sss, "get_internal_auth_secret", lambda: None)
    monkeypatch.setenv("INTERNAL_AUTH_SECRET", "shared-secret")

    plain = FastMCP("none-mode-test")  # no auth provider

    @plain.custom_route("/health", methods=["GET"])
    async def health(request):
        from starlette.responses import PlainTextResponse

        return PlainTextResponse("OK")

    # Mirror main()'s mode=none stack exactly.
    app = SecurityHeadersMiddleware(
        APIKeyAuthMiddleware(
            CORSMiddleware(
                plain.http_app(),
                allow_origins=["http://localhost:8080"],
                allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
                allow_headers=["Content-Type", "Accept", "Mcp-Session-Id"],
                expose_headers=["Mcp-Session-Id"],
            )
        )
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as http:
        # /health open without a key.
        assert (await http.get("/health")).status_code == 200
        # Everything else 401s without the shared secret...
        mcp_headers = {
            "content-type": "application/json",
            "accept": "application/json, text/event-stream",
        }
        no_key = await http.post("/mcp", json={}, headers=mcp_headers)
        assert no_key.status_code == 401
        # ...and the guard opens with it: an unknown path reaches routing
        # (404) instead of the 401 wall. (POSTing /mcp with the key would
        # need the app lifespan/session manager, which ASGITransport does
        # not run — the 404-vs-401 contrast is the guard proof.)
        with_key = await http.get(
            "/no-such-path", headers={"x-api-key": "shared-secret"}
        )
        assert with_key.status_code == 404
        # No OAuth surface in mode=none (past the guard: key supplied).
        assert (
            await http.get(
                "/.well-known/oauth-authorization-server",
                headers={"x-api-key": "shared-secret"},
            )
        ).status_code == 404
        assert (
            await http.get("/authorize", headers={"x-api-key": "shared-secret"})
        ).status_code == 404
