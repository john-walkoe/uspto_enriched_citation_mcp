"""Direct coverage for `citations_manage_users`.

The tool body was the only registered tool with zero direct invocations: the
`McpUserStore` beneath it and the registration gate above it were both tested
and the 46 lines in between were not, including the serialization block that
formats what an admin actually sees (T-1).
"""

import pytest

from uspto_enriched_citation_mcp.auth.store import McpUserStore
from uspto_enriched_citation_mcp.tools import admin


@pytest.fixture
def store(monkeypatch, tmp_path):
    user_store = McpUserStore(tmp_path / "auth.db")
    monkeypatch.setattr(admin, "_get_user_store", lambda: user_store)
    monkeypatch.setattr(admin, "_audit_user_management", lambda *a, **kw: None)
    return user_store


@pytest.mark.asyncio
async def test_add_then_list_serializes_every_column(store):
    added = await admin.citations_manage_users(
        action="add", email="A@Example.COM", role="admin", display_name="Ada"
    )

    row = added["users"][0]
    assert row["email"] == "a@example.com"  # lowercased before the store sees it
    assert row["role"] == "admin"
    assert row["display_name"] == "Ada"
    assert row["active"] is True
    assert row["added_at"] is not None  # the isoformat branch
    assert row["last_login_at"] is None  # the None branch
    assert row["last_login_idp"] is None
    assert row["notes"] is None

    listed = await admin.citations_manage_users(action="list")
    assert listed["message"] == "1 registered user(s)."
    assert listed["users"] == added["users"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action,email,expected",
    [
        ("bogus", "a@b.com", "action must be one of"),
        ("add", "not-an-email", "invalid email address"),
        ("set_role", "nobody@x.com", "no such user"),
        ("activate", "nobody@x.com", "no such user"),
        ("deactivate", "nobody@x.com", "no such user"),
        ("delete", "nobody@x.com", "no such user"),
    ],
)
async def test_rejects_bad_input(store, action, email, expected):
    result = await admin.citations_manage_users(action=action, email=email)
    assert expected in result["error"]


@pytest.mark.asyncio
async def test_add_rejects_an_unknown_role(store):
    result = await admin.citations_manage_users(
        action="add", email="a@b.com", role="superuser"
    )
    assert "role must be" in result["error"]


@pytest.mark.asyncio
async def test_set_role_preserves_the_active_flag(store):
    await admin.citations_manage_users(action="add", email="a@b.com", role="user")
    await admin.citations_manage_users(action="deactivate", email="a@b.com")

    result = await admin.citations_manage_users(
        action="set_role", email="a@b.com", role="admin"
    )

    row = result["users"][0]
    assert row["role"] == "admin"
    assert row["active"] is False


@pytest.mark.asyncio
async def test_activate_and_deactivate_round_trip(store):
    await admin.citations_manage_users(action="add", email="a@b.com")

    off = await admin.citations_manage_users(action="deactivate", email="a@b.com")
    assert off["users"][0]["active"] is False
    assert "deactivated" in off["message"]

    on = await admin.citations_manage_users(action="activate", email="a@b.com")
    assert on["users"][0]["active"] is True
    assert "active" in on["message"]


@pytest.mark.asyncio
async def test_delete_removes_the_row_entirely(store):
    await admin.citations_manage_users(action="add", email="a@b.com")

    result = await admin.citations_manage_users(action="delete", email="a@b.com")

    assert result["users"] == []
    assert "deleted" in result["message"]
    assert await store.get_user("a@b.com") is None


@pytest.mark.asyncio
async def test_store_failure_becomes_a_sanitized_500(store, monkeypatch):
    async def boom(*args, **kwargs):
        raise RuntimeError("Traceback at /home/john/secret/store.py line 42")

    monkeypatch.setattr(store, "list_users", boom)

    result = await admin.citations_manage_users(action="list")

    assert result["status"] == "error"
    assert result["code"] == 500
    assert "secret" not in str(result)
    assert "/home/john" not in str(result)
