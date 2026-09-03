"""Audit, erasure and log-permission findings around citations_manage_users.

Three findings from the 2026-09-03 review:

- S-22: add / set_role / activate / deactivate wrote the authorization source
  of truth with no security-log record.
- S-14: `mcp_users` had no deletion path, so the only PII in the system could
  be deactivated but never erased.
- S-16: SecurityLogger never set `propagate = False`, so every event also
  reached the 0640 application and error logs.
"""

import pytest

import uspto_enriched_citation_mcp.tools.admin as admin_module
from uspto_enriched_citation_mcp.auth.store import McpUserStore
from uspto_enriched_citation_mcp.tools.admin import citations_manage_users
from uspto_enriched_citation_mcp.util.security_logger import SecurityLogger


class _FakeUserStore:
    def __init__(self):
        self._users = {}

    async def upsert_user(self, email, role="user", display_name=None,
                          notes=None, active=True):
        self._users[email] = {
            "email": email, "display_name": display_name, "role": role,
            "active": active, "added_at": None, "last_login_at": None,
            "last_login_idp": None, "notes": notes,
        }

    async def get_user(self, email):
        return self._users.get(email)

    async def set_active(self, email, active):
        if email not in self._users:
            return False
        self._users[email]["active"] = active
        return True

    async def delete_user(self, email):
        return self._users.pop(email, None) is not None

    async def list_users(self):
        return list(self._users.values())


@pytest.fixture
def audited(monkeypatch):
    """Fake store plus a capture of every audit event the tool emits."""
    store = _FakeUserStore()
    monkeypatch.setattr(admin_module, "_get_user_store", lambda: store)
    events = []

    class _Recorder:
        def admin_action(self, **kwargs):
            events.append(kwargs)

    monkeypatch.setattr(admin_module, "get_security_logger", _Recorder)
    return events


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action,kwargs",
    [
        ("add", {"role": "admin"}),
        ("set_role", {"role": "admin"}),
        ("activate", {}),
        ("deactivate", {}),
        ("delete", {}),
    ],
)
async def test_every_mutation_is_audited(audited, action, kwargs):
    await citations_manage_users(action="add", email="alice@example.com", role="user")
    audited.clear()

    await citations_manage_users(action=action, email="alice@example.com", **kwargs)

    assert [e["action"] for e in audited] == [action]
    assert audited[0]["target"] == "alice@example.com"
    assert audited[0]["success"] is True


@pytest.mark.asyncio
async def test_list_is_not_audited(audited):
    await citations_manage_users(action="list")

    assert audited == []


@pytest.mark.asyncio
async def test_failed_mutation_is_audited_as_a_failure(audited):
    result = await citations_manage_users(action="delete", email="nobody@example.com")

    assert "error" in result
    assert audited[0]["success"] is False


@pytest.mark.asyncio
async def test_delete_removes_the_user(audited):
    await citations_manage_users(action="add", email="alice@example.com", role="user")

    result = await citations_manage_users(action="delete", email="alice@example.com")

    assert result["users"] == []


@pytest.mark.asyncio
async def test_delete_user_erases_the_row_and_its_refresh_tokens(tmp_path):
    store = McpUserStore(tmp_path / "auth" / "mcp_auth.db")
    await store.upsert_user("jane@firm.com", role="user", notes="pilot")
    await store.put_refresh(
        "tok", client_id="cid", email="jane@firm.com",
        scopes=["citations:user"], ttl_seconds=3600,
    )

    assert await store.delete_user("Jane@Firm.com") is True

    assert await store.get_user("jane@firm.com") is None
    assert await store.get_refresh("tok") is None
    assert await store.delete_user("jane@firm.com") is False


def test_security_logger_does_not_propagate_to_the_application_log(tmp_path):
    security = SecurityLogger(name="propagation-probe", log_dir=str(tmp_path))

    assert security.logger.propagate is False


# ----------------------------------------------------------------------
# CLI surface (scripts/manage_mcp_users.py). The tool and the CLI are two
# doors onto the same authorization table; fleet agent A closed the tool's
# erasure gap and audit trail and handed the CLI over (S-14, S-22).


def _load_cli_module():
    import importlib.util
    from pathlib import Path

    script = Path(__file__).resolve().parent.parent / "scripts" / "manage_mcp_users.py"
    spec = importlib.util.spec_from_file_location("manage_mcp_users_cli", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_exposes_a_delete_subcommand(monkeypatch, tmp_path):
    """`main()` parses argv and dispatches, so an unknown subcommand exits 2."""
    module = _load_cli_module()

    monkeypatch.setenv("CITATIONS_AUTH_DB_PATH", str(tmp_path / "auth.db"))
    monkeypatch.setattr(module, "_audit", lambda *a: None)
    monkeypatch.setattr(
        module.sys, "argv", ["manage_mcp_users.py", "delete", "nobody@x.com"]
    )

    # Reaches the handler (no such user -> 1) rather than argparse's exit 2.
    assert module.main() == 1


@pytest.mark.asyncio
async def test_cli_delete_removes_the_user_and_audits(tmp_path, monkeypatch):
    module = _load_cli_module()
    import argparse

    from uspto_enriched_citation_mcp.auth.store import McpUserStore

    db_path = tmp_path / "auth.db"
    monkeypatch.setenv("CITATIONS_AUTH_DB_PATH", str(db_path))

    events = []
    monkeypatch.setattr(module, "_audit", lambda *a: events.append(a))

    store = McpUserStore(db_path)
    await store.upsert_user("jane@firm.com", role="user")

    rc = await module.run(argparse.Namespace(command="delete", email="jane@firm.com"))

    assert rc == 0
    assert await store.get_user("jane@firm.com") is None
    assert events == [("delete", "jane@firm.com", None, True)]


@pytest.mark.asyncio
async def test_cli_delete_of_a_missing_user_audits_the_failure(tmp_path, monkeypatch):
    module = _load_cli_module()
    import argparse

    monkeypatch.setenv("CITATIONS_AUTH_DB_PATH", str(tmp_path / "auth.db"))
    events = []
    monkeypatch.setattr(module, "_audit", lambda *a: events.append(a))

    rc = await module.run(argparse.Namespace(command="delete", email="nobody@x.com"))

    assert rc == 1
    assert events == [("delete", "nobody@x.com", None, False)]
