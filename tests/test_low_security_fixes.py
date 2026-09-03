"""Regression tests for Phase 3 (Low) audit-remediation fixes.

L1  — OAuth _txns dict is capped (auth/provider.py).
L2  — refresh-token family revocation on replay (ported from PFW).
L6  — auth SQLite DB file chmod'd 0o600 (+ WAL/SHM siblings).
L10 — PRAGMA foreign_keys=ON + FK from oauth_refresh_tokens.email ->
      mcp_users.email for new databases.
L11 — OAuth login/callback logging routed through the sanitized logger and
      masked emails.
"""

from __future__ import annotations

import stat
import sys
import time
from typing import Any

import pytest

from uspto_enriched_citation_mcp.auth.provider import (
    SCOPE_USER,
    CitationsAuthProvider,
    _mask_email,
)
from uspto_enriched_citation_mcp.auth.store import McpUserStore

from .test_auth_provider import FakeUserStore, make_client, make_params, make_settings


def make_provider(
    store: FakeUserStore | None = None, **overrides: Any
) -> tuple[CitationsAuthProvider, FakeUserStore]:
    store = store or FakeUserStore()
    provider = CitationsAuthProvider(make_settings(**overrides), store)  # type: ignore[arg-type]
    return provider, store


# --------------------------------------------------------------------- L1


@pytest.mark.asyncio
async def test_txns_capped_evicts_oldest_when_full(monkeypatch):
    """The cap holds, and the OLDEST transaction is the one shed.

    This assertion used to require `AuthorizeError("temporarily_unavailable")`
    on the newest request, which encoded S-38: refusing new sign-ins locked
    out every arriving legitimate user while a filler's own entries survived
    for the full 15-minute TTL. Load is now shed from the correct side.
    """
    import uspto_enriched_citation_mcp.auth.provider as provider_mod

    monkeypatch.setattr(provider_mod, "_MAX_TXNS", 3)
    provider, _ = make_provider()

    first_three = []
    for _ in range(3):
        url = await provider.authorize(make_client(), make_params())
        first_three.append(url.split("txn=")[1])
    assert len(provider._txns) == 3

    newest = (await provider.authorize(make_client(), make_params())).split("txn=")[1]

    # The cap held, the new sign-in was accepted, and the oldest was evicted.
    assert len(provider._txns) == 3
    assert newest in provider._txns
    assert first_three[0] not in provider._txns
    assert first_three[-1] in provider._txns


@pytest.mark.asyncio
async def test_txns_cap_recovers_after_pruning(monkeypatch):
    """Expired entries are pruned before the cap is checked, so the limiter
    isn't permanently stuck once transactions age out."""
    import uspto_enriched_citation_mcp.auth.provider as provider_mod

    monkeypatch.setattr(provider_mod, "_MAX_TXNS", 2)
    provider, _ = make_provider()

    await provider.authorize(make_client(), make_params())
    await provider.authorize(make_client(), make_params())
    assert len(provider._txns) == 2

    # Age out both transactions.
    for txn in provider._txns.values():
        txn["created_at"] = time.time() - 3600

    # A new authorize() call prunes first, then succeeds under the cap.
    await provider.authorize(make_client(), make_params())
    assert len(provider._txns) == 1


# --------------------------------------------------------------------- L2


class TestRefreshFamilyRevocation:
    """Real-store test mirroring PFW's test_refresh_replay_revokes_family."""

    @pytest.fixture()
    def store(self, tmp_path) -> McpUserStore:
        return McpUserStore(tmp_path / "auth" / "mcp_auth.db")

    @pytest.mark.asyncio
    async def test_store_revokes_family_on_replay_detection(
        self, store: McpUserStore
    ) -> None:
        await store.upsert_user("fam@b.com")
        for tok in ("fam-a", "fam-b", "fam-c"):
            await store.put_refresh(
                tok, client_id="cid", email="fam@b.com",
                scopes=["citations:user"], ttl_seconds=3600,
            )
        # Rotate fam-a (spent), then detect its replay.
        await store.revoke_refresh("fam-a")
        spent = await store.get_refresh_any("fam-a")
        assert spent is not None and spent["revoked"]

        revoked = await store.revoke_all_refresh_for("cid", "fam@b.com")
        assert revoked == 2  # fam-b and fam-c were live
        assert await store.get_refresh("fam-b") is None
        assert await store.get_refresh("fam-c") is None

    @pytest.mark.asyncio
    async def test_get_refresh_any_returns_none_for_unknown_token(
        self, store: McpUserStore
    ) -> None:
        assert await store.get_refresh_any("never-issued") is None


@pytest.mark.asyncio
async def test_provider_load_refresh_token_revokes_family_on_replay(monkeypatch):
    """CitationsAuthProvider.load_refresh_token, given a store that reports
    the presented token as already-revoked, revokes the whole family and
    logs the incident (not a silent miss)."""

    class _FamilyAwareFakeStore(FakeUserStore):
        def __init__(self) -> None:
            super().__init__()
            self.revoke_all_calls: list[tuple[str, str]] = []

        async def get_refresh_any(self, token: str):
            row = self.refresh.get(token)
            return dict(row) if row else None

        async def revoke_all_refresh_for(self, client_id: str, email: str) -> int:
            self.revoke_all_calls.append((client_id, email))
            live = [
                t
                for t, r in self.refresh.items()
                if r["client_id"] == client_id
                and r["email"] == email
                and not r["revoked"]
            ]
            for t in live:
                self.refresh[t]["revoked"] = True
            return len(live)

    store = _FamilyAwareFakeStore()
    provider, _ = make_provider(store)
    client = make_client()

    await store.put_refresh(
        "spent", client_id=client.client_id, email="jane@firm.com",
        scopes=[SCOPE_USER], ttl_seconds=3600,
    )
    await store.put_refresh(
        "still-live", client_id=client.client_id, email="jane@firm.com",
        scopes=[SCOPE_USER], ttl_seconds=3600,
    )
    await store.revoke_refresh("spent")  # simulate: already rotated

    logged = {}
    from uspto_enriched_citation_mcp.util.security_logger import get_security_logger

    monkeypatch.setattr(
        get_security_logger(),
        "suspicious_pattern",
        lambda **kw: logged.update(kw),
    )

    result = await provider.load_refresh_token(client, "spent")
    assert result is None
    assert store.revoke_all_calls == [(client.client_id, "jane@firm.com")]
    assert store.refresh["still-live"]["revoked"] is True
    assert logged.get("pattern_type") == "refresh_token_replay"
    # The email must never appear in plaintext in the log payload.
    assert "jane@firm.com" not in logged.get("description", "")


def test_mask_email():
    assert _mask_email("jane@firm.com") == "j***@firm.com"
    assert _mask_email("") == "***"
    assert _mask_email("not-an-email") == "***"


# --------------------------------------------------------------------- L6


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits only")
@pytest.mark.asyncio
async def test_auth_db_file_chmod_0600(tmp_path):
    db_path = tmp_path / "auth" / "mcp_auth.db"
    store = McpUserStore(db_path)
    await store.upsert_user("a@b.com")  # forces schema init / first _db() call

    mode = stat.S_IMODE(db_path.stat().st_mode)
    assert mode == 0o600


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits only")
@pytest.mark.asyncio
async def test_auth_db_wal_shm_siblings_chmod_if_present(tmp_path):
    db_path = tmp_path / "auth" / "mcp_auth.db"
    store = McpUserStore(db_path)
    await store.upsert_user("a@b.com")

    for suffix in ("-wal", "-shm"):
        sidecar = db_path.with_name(db_path.name + suffix)
        if sidecar.exists():
            assert stat.S_IMODE(sidecar.stat().st_mode) == 0o600


# --------------------------------------------------------------------- L10


@pytest.mark.asyncio
async def test_foreign_keys_pragma_enabled_on_connections(tmp_path):
    db_path = tmp_path / "auth" / "mcp_auth.db"
    store = McpUserStore(db_path)
    await store.upsert_user("a@b.com")  # ensures schema is created

    async with store._db() as db:
        cur = await db.execute("PRAGMA foreign_keys")
        row = await cur.fetchone()
    assert row[0] == 1


@pytest.mark.asyncio
async def test_refresh_token_fk_rejects_unknown_email(tmp_path):
    """New databases declare oauth_refresh_tokens.email -> mcp_users.email;
    inserting a refresh token for a never-registered email must fail once FK
    enforcement is on."""
    import aiosqlite

    db_path = tmp_path / "auth" / "mcp_auth.db"
    store = McpUserStore(db_path)
    await store.upsert_user("registered@b.com")  # create schema, seed one user

    with pytest.raises(aiosqlite.IntegrityError):
        await store.put_refresh(
            "orphan-token", client_id="cid", email="never-registered@b.com",
            scopes=["citations:user"], ttl_seconds=3600,
        )


@pytest.mark.asyncio
async def test_refresh_token_insert_succeeds_for_registered_email(tmp_path):
    db_path = tmp_path / "auth" / "mcp_auth.db"
    store = McpUserStore(db_path)
    await store.upsert_user("registered@b.com")

    await store.put_refresh(
        "ok-token", client_id="cid", email="registered@b.com",
        scopes=["citations:user"], ttl_seconds=3600,
    )
    row = await store.get_refresh("ok-token")
    assert row is not None


# --------------------------------------------------------------------- L11


def test_provider_logger_is_sanitized_not_bare_stdlib():
    """auth/provider.py's module logger must go through the repo's
    get_logger() (SanitizingFilter attached), not a bare
    logging.getLogger(__name__)."""
    from uspto_enriched_citation_mcp.auth import provider as provider_mod
    from uspto_enriched_citation_mcp.util.logging import SanitizingFilter

    assert any(
        isinstance(f, SanitizingFilter) for f in provider_mod.log.filters
    )


@pytest.mark.asyncio
async def test_callback_masks_email_in_log_not_registered(monkeypatch):
    """OAuth callback logging for an unregistered email masks the address."""
    import uspto_enriched_citation_mcp.auth.provider as provider_mod

    provider, store = make_provider()
    logged_messages = []

    def fake_info(msg, *args):
        logged_messages.append(msg % args)

    monkeypatch.setattr(provider_mod.log, "info", fake_info)

    from urllib.parse import parse_qs, urlparse

    from .test_auth_provider import get_request, txn_cookie

    url = await provider.authorize(make_client(), make_params())
    txn = parse_qs(urlparse(url).query)["txn"][0]

    async def fake_exchange(idp_, code, nonce):
        return {"email": "stranger@example.com", "email_verified": True}

    monkeypatch.setattr(provider, "_exchange_and_verify", fake_exchange)
    resp = await provider._callback_endpoint(
        get_request(
            "/auth/callback/google",
            f"state={txn}&code=up",
            {"idp": "google"},
            cookies=txn_cookie(provider, txn),
        )
    )
    assert resp.status_code == 403
    combined = " ".join(logged_messages)
    assert "stranger@example.com" not in combined
    assert "s***@example.com" in combined
