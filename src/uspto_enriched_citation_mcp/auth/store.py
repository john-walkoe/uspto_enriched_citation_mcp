"""Registered-user list + OAuth authorization-server state (SQLite).

mcp_users is the authorization source of truth for the dual-IdP login flow:
the upstream IdP (Google / Entra ID) proves WHO the caller is; an active row
here decides WHETHER they may connect and, via role, whether they get the
citations:admin scope (the user-management tool). Rows are managed by the
admin-gated `citations_manage_users` MCP tool or scripts/manage_mcp_users.py.

The three oauth_* tables persist the authorization-server state that must
survive restarts: dynamically registered MCP clients (RFC 7591), single-use
authorization codes, and rotating refresh tokens. Codes and refresh tokens are
stored as SHA-256 hashes only.

Backend is a single SQLite file (CITATIONS_AUTH_DB_PATH, default
``data/mcp_auth.db``) — zero-infrastructure for self-hosters. WAL mode +
busy_timeout are enabled so the same file can be shared by several MCP
containers on ONE host (the paid-tier PFW/PTAB/FPD deployment); a network
filesystem is NOT safe for this. Connections are opened per operation — auth
traffic is a handful of queries per login/refresh, and per-call connections
keep multi-process sharing robust.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, AsyncIterator

import aiosqlite

log = logging.getLogger(__name__)

VALID_ROLES = ("user", "admin")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS mcp_users (
    email          TEXT PRIMARY KEY,
    display_name   TEXT,
    role           TEXT NOT NULL DEFAULT 'user',
    active         INTEGER NOT NULL DEFAULT 1,
    added_at       TEXT NOT NULL,
    last_login_at  TEXT,
    last_login_idp TEXT,
    notes          TEXT
);
CREATE TABLE IF NOT EXISTS oauth_clients (
    client_id  TEXT PRIMARY KEY,
    payload    TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS oauth_codes (
    code_hash  TEXT PRIMARY KEY,
    payload    TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS oauth_refresh_tokens (
    token_hash TEXT PRIMARY KEY,
    client_id  TEXT NOT NULL,
    email      TEXT NOT NULL,
    scopes     TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked    INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (email) REFERENCES mcp_users (email)
);
CREATE INDEX IF NOT EXISTS idx_oauth_refresh_email ON oauth_refresh_tokens (email);
"""


def token_hash(token: str) -> str:
    """SHA-256 hex of a code/refresh token — the only form that hits disk."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime) -> str:
    """Canonical stored timestamp form — lexicographically comparable."""
    return dt.astimezone(UTC).isoformat()


def _parse(ts: str | None) -> datetime | None:
    return datetime.fromisoformat(ts) if ts else None


class McpUserStore:
    """Registered users + OAuth AS state in one SQLite file."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._schema_ready = False
        self._schema_lock = asyncio.Lock()

    @asynccontextmanager
    async def _db(self) -> AsyncIterator[aiosqlite.Connection]:
        if not self._schema_ready:
            async with self._schema_lock:
                if not self._schema_ready:
                    self._db_path.parent.mkdir(parents=True, exist_ok=True)
                    async with aiosqlite.connect(self._db_path) as db:
                        await db.execute("PRAGMA journal_mode=WAL")
                        await db.execute("PRAGMA busy_timeout=5000")
                        await db.executescript(_SCHEMA)
                        await db.commit()
                    self._chmod_db_files()
                    self._schema_ready = True
        db = await aiosqlite.connect(self._db_path)
        try:
            await db.execute("PRAGMA busy_timeout=5000")
            # No FKs enforced anywhere else in this file's queries touch the
            # schema, but the oauth_refresh_tokens.email -> mcp_users.email FK
            # (audit L10) needs enforcement turned on to take effect — SQLite
            # defaults it to OFF per connection.
            await db.execute("PRAGMA foreign_keys=ON")
            db.row_factory = aiosqlite.Row
            yield db
        finally:
            # BEFORE close, not after: SQLite deletes -wal/-shm when the last
            # connection closes cleanly, so the bootstrap-time chmod ran when
            # they did not exist and the ones a later write recreated landed
            # at the process umask, typically 0644, holding recently written
            # refresh-token hashes and emails (S-29).
            self._chmod_db_files()
            await db.close()

    def _chmod_db_files(self) -> None:
        """Restrict the SQLite file (and WAL/SHM siblings) to the owner only
        (audit L6/file-handling-business-logic.md L1). Best-effort: os.chmod
        has no real effect on Windows ACLs, so this is wrapped and never
        blocks startup."""
        try:
            os.chmod(self._db_path, 0o600)
            for suffix in ("-wal", "-shm"):
                sidecar = self._db_path.with_name(self._db_path.name + suffix)
                if sidecar.exists():
                    os.chmod(sidecar, 0o600)
        except OSError:
            pass

    # ------------------------------------------------------------------ users

    async def get_user(self, email: str) -> dict[str, Any] | None:
        async with self._db() as db:
            cur = await db.execute(
                "SELECT email, display_name, role, active, added_at, "
                "last_login_at, last_login_idp, notes "
                "FROM mcp_users WHERE email = ?",
                (email.strip().lower(),),
            )
            row = await cur.fetchone()
        return self._user_dict(row) if row else None

    async def upsert_user(
        self,
        email: str,
        *,
        role: str = "user",
        display_name: str | None = None,
        active: bool = True,
        notes: str | None = None,
    ) -> None:
        if role not in VALID_ROLES:
            raise ValueError(f"role must be one of {VALID_ROLES}, got {role!r}")
        async with self._db() as db:
            await db.execute(
                "INSERT INTO mcp_users (email, display_name, role, active, added_at, notes) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (email) DO UPDATE SET "
                "display_name = COALESCE(excluded.display_name, mcp_users.display_name), "
                "role = excluded.role, active = excluded.active, "
                "notes = COALESCE(excluded.notes, mcp_users.notes)",
                (
                    email.strip().lower(),
                    display_name,
                    role,
                    int(active),
                    _iso(_now()),
                    notes,
                ),
            )
            await db.commit()

    async def set_active(self, email: str, active: bool) -> bool:
        async with self._db() as db:
            cur = await db.execute(
                "UPDATE mcp_users SET active = ? WHERE email = ?",
                (int(active), email.strip().lower()),
            )
            await db.commit()
        return cur.rowcount == 1

    async def delete_user(self, email: str) -> bool:
        """Erase a user row and every refresh token issued to it (S-14).

        `deactivate` leaves the row, its display name, its free-text notes and
        its login history in place, which is not an erasure. Refresh tokens
        carry an `email` foreign key, so they go first.
        """
        normalized = email.strip().lower()
        async with self._db() as db:
            await db.execute(
                "DELETE FROM oauth_refresh_tokens WHERE email = ?", (normalized,)
            )
            cur = await db.execute(
                "DELETE FROM mcp_users WHERE email = ?", (normalized,)
            )
            await db.commit()
        return cur.rowcount == 1

    async def record_login(self, email: str, idp: str) -> None:
        async with self._db() as db:
            await db.execute(
                "UPDATE mcp_users SET last_login_at = ?, last_login_idp = ? "
                "WHERE email = ?",
                (_iso(_now()), idp, email.strip().lower()),
            )
            await db.commit()

    async def list_users(self) -> list[dict[str, Any]]:
        async with self._db() as db:
            cur = await db.execute(
                "SELECT email, display_name, role, active, added_at, "
                "last_login_at, last_login_idp, notes "
                "FROM mcp_users ORDER BY added_at"
            )
            rows = await cur.fetchall()
        return [self._user_dict(r) for r in rows]

    @staticmethod
    def _user_dict(row: aiosqlite.Row) -> dict[str, Any]:
        d = dict(row)
        d["active"] = bool(d["active"])
        d["added_at"] = _parse(d["added_at"])
        d["last_login_at"] = _parse(d["last_login_at"])
        return d

    # ------------------------------------------------- registered MCP clients

    async def put_client(self, client_id: str, payload: dict[str, Any]) -> None:
        async with self._db() as db:
            await db.execute(
                "INSERT INTO oauth_clients (client_id, payload, created_at) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT (client_id) DO UPDATE SET payload = excluded.payload",
                (client_id, json.dumps(payload), _iso(_now())),
            )
            await db.commit()

    async def get_client(self, client_id: str) -> dict[str, Any] | None:
        async with self._db() as db:
            cur = await db.execute(
                "SELECT payload FROM oauth_clients WHERE client_id = ?", (client_id,)
            )
            row = await cur.fetchone()
        return json.loads(row["payload"]) if row else None

    async def sweep_unused_clients(self, max_age_days: int = 30) -> int:
        """Delete registered clients that never completed an authorization.

        `/register` is unauthenticated and writes a row per call, and this
        table was the only one with no cleanup at all — oauth_codes and
        oauth_refresh_tokens both had one (S-09). `created_at` was already
        stored and never read; a client with no refresh token after
        `max_age_days` never finished a sign-in. Returns the row count.
        """
        cutoff = _iso(_now() - timedelta(days=max_age_days))
        async with self._db() as db:
            cur = await db.execute(
                "DELETE FROM oauth_clients WHERE created_at < ? AND client_id NOT IN "
                "(SELECT DISTINCT client_id FROM oauth_refresh_tokens)",
                (cutoff,),
            )
            await db.commit()
            return cur.rowcount or 0

    # ----------------------------------------------------- authorization codes

    async def put_code(
        self, code: str, payload: dict[str, Any], ttl_seconds: int
    ) -> None:
        expires = _now() + timedelta(seconds=ttl_seconds)
        async with self._db() as db:
            await db.execute(
                "INSERT INTO oauth_codes (code_hash, payload, expires_at) "
                "VALUES (?, ?, ?)",
                (token_hash(code), json.dumps(payload), _iso(expires)),
            )
            await db.commit()

    async def take_code(self, code: str) -> dict[str, Any] | None:
        """Fetch AND delete in one statement — a code is single-use even if the
        subsequent PKCE check fails (burning it is the safe failure mode)."""
        now = _iso(_now())
        async with self._db() as db:
            cur = await db.execute(
                "DELETE FROM oauth_codes WHERE code_hash = ? AND expires_at > ? "
                "RETURNING payload",
                (token_hash(code), now),
            )
            row = await cur.fetchone()
            # Opportunistic cleanup of expired codes (tiny table).
            await db.execute("DELETE FROM oauth_codes WHERE expires_at <= ?", (now,))
            await db.commit()
        return json.loads(row["payload"]) if row else None

    # ------------------------------------------------------------ refresh tokens

    async def put_refresh(
        self,
        token: str,
        *,
        client_id: str,
        email: str,
        scopes: list[str],
        ttl_seconds: int,
    ) -> None:
        expires = _now() + timedelta(seconds=ttl_seconds)
        async with self._db() as db:
            await db.execute(
                "INSERT INTO oauth_refresh_tokens "
                "(token_hash, client_id, email, scopes, expires_at, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    token_hash(token),
                    client_id,
                    email,
                    json.dumps(scopes),
                    _iso(expires),
                    _iso(_now()),
                ),
            )
            await db.commit()

    async def get_refresh(self, token: str) -> dict[str, Any] | None:
        async with self._db() as db:
            cur = await db.execute(
                "SELECT token_hash, client_id, email, scopes, expires_at, revoked "
                "FROM oauth_refresh_tokens "
                "WHERE token_hash = ? AND revoked = 0 AND expires_at > ?",
                (token_hash(token), _iso(_now())),
            )
            row = await cur.fetchone()
        if row is None:
            return None
        d = dict(row)
        d["scopes"] = json.loads(d["scopes"])
        d["expires_at"] = _parse(d["expires_at"])
        d["revoked"] = bool(d["revoked"])
        return d

    async def get_refresh_any(self, token: str) -> dict[str, Any] | None:
        """Like get_refresh but includes revoked/expired rows — used to
        distinguish a replayed (spent) token from an unknown one (audit L2)."""
        async with self._db() as db:
            cur = await db.execute(
                "SELECT token_hash, client_id, email, scopes, expires_at, revoked "
                "FROM oauth_refresh_tokens WHERE token_hash = ?",
                (token_hash(token),),
            )
            row = await cur.fetchone()
        if row is None:
            return None
        d = dict(row)
        d["scopes"] = json.loads(d["scopes"])
        d["expires_at"] = _parse(d["expires_at"])
        d["revoked"] = bool(d["revoked"])
        return d

    async def revoke_all_refresh_for(self, client_id: str, email: str) -> int:
        """Revoke every live refresh token for (client_id, email) — the
        practical token family. Called on replay of a spent token (audit L2:
        treat reuse as an incident, not a silent miss)."""
        async with self._db() as db:
            cur = await db.execute(
                "UPDATE oauth_refresh_tokens SET revoked = 1 "
                "WHERE client_id = ? AND email = ? AND revoked = 0",
                (client_id, email),
            )
            await db.commit()
            return cur.rowcount

    async def revoke_refresh(self, token: str) -> None:
        async with self._db() as db:
            await db.execute(
                "UPDATE oauth_refresh_tokens SET revoked = 1 WHERE token_hash = ?",
                (token_hash(token),),
            )
            # Opportunistic cleanup: drop rows long past expiry.
            await db.execute(
                "DELETE FROM oauth_refresh_tokens WHERE expires_at < ?",
                (_iso(_now() - timedelta(days=7)),),
            )
            await db.commit()
