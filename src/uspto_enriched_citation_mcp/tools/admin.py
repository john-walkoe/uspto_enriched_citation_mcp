"""Registered-user management tool (citations:admin scope in OAuth mode).

Registration-gated by CITATIONS_ENABLE_USER_MANAGEMENT (default off — matches
the PFW/PTAB pattern / neo4j NEO4J_READ_ONLY approach)."""

import os
import re
from typing import Any, Dict, Optional

from fastmcp.apps import AppConfig

from ..app_uris import USER_MANAGEMENT_URI
from ..config.settings import get_settings
from ..shared.error_utils import format_error_response
from ..util.logging import get_logger
from ..util.request_context import RequestContext
from ..util.security_logger import get_security_logger

logger = get_logger(__name__)

# Registration gate for the user-management tool (neo4j NEO4J_READ_ONLY /
# PTAB PTAB_ENABLE_USER_MANAGEMENT pattern: filtered at registration time, so
# it never appears in tools/list when off). Default OFF: stdio doesn't need
# it (seed admins with scripts/manage_mcp_users.py), and outside OAuth mode
# it would be protected only by the shared INTERNAL_AUTH_SECRET. Prod OAuth
# compose must set CITATIONS_ENABLE_USER_MANAGEMENT=true.
USER_MANAGEMENT_ENABLED = (
    os.getenv("CITATIONS_ENABLE_USER_MANAGEMENT", "false").lower() == "true"
)

# Set by register(): the OAuth provider's user store is reused when present
_auth_provider = None

# Basic shape check only (one "@", a dot in the domain, no whitespace) — the
# authoritative identity comes from the IdP; this just rejects obvious typos.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _get_user_store():
    """User store for the management tool: reuse the auth provider's store in
    OAuth mode; otherwise open the configured SQLite path directly (stdio /
    plain-HTTP use, e.g. seeding before OAuth is switched on)."""
    if _auth_provider is not None:
        return _auth_provider._users
    from ..auth.store import McpUserStore

    return McpUserStore(get_settings().auth_db_path)


def _actor() -> str:
    """Authenticated identity of the caller, for the audit record.

    Returns "local-process" outside OAuth mode, where the transport itself is
    the identity."""
    try:
        from fastmcp.server.dependencies import get_access_token
        token = get_access_token()
        if token is not None:
            claims = getattr(token, "claims", None) or {}
            return claims.get("email") or getattr(token, "client_id", None) or "internal"
    except Exception:
        pass
    return "local-process"


def _audit_user_management(actor: str, action: str, target: str, role: str,
                          success: bool, detail: Optional[str] = None) -> None:
    """Emit a security-log record for every mcp_users mutation (S-22).

    `list` is a read and is not audited. Never raises: a failed audit write
    must not turn a successful grant into a tool error, but it is logged."""
    if action == "list":
        return
    try:
        get_security_logger().admin_action(
            actor=actor,
            action=action,
            target=target,
            success=success,
            role=role if action in ("add", "set_role") else None,
            detail=detail,
        )
    except Exception as audit_error:
        logger.error("Admin audit write failed: %s", type(audit_error).__name__)


# -----------------------------------------------------------------------
# citations_manage_users action handlers.
#
# Each handler has the uniform signature (store, email, role, display_name,
# notes) -> (message, error). On success it returns (message_string, None);
# on failure it returns (None, error_response_dict) — mirroring the
# early-return `{"error": ...}` shape of the original inline chain.
# -----------------------------------------------------------------------


async def _handle_list(store, email, role, display_name, notes):
    return "", None


async def _handle_add(store, email, role, display_name, notes):
    if role not in ("user", "admin"):
        return None, {"error": f"role must be 'user' or 'admin', got {role!r}"}
    await store.upsert_user(
        email,
        role=role,
        display_name=display_name or None,
        notes=notes or None,
    )
    return f"Added/updated {email} with role '{role}'.", None


async def _handle_set_role(store, email, role, display_name, notes):
    if role not in ("user", "admin"):
        return None, {"error": f"role must be 'user' or 'admin', got {role!r}"}
    existing = await store.get_user(email)
    if existing is None:
        return None, {"error": f"no such user: {email}"}
    await store.upsert_user(email, role=role, active=existing["active"])
    return f"{email} role set to '{role}'.", None


async def _set_active_message(store, email, active):
    if not await store.set_active(email, active):
        return None, {"error": f"no such user: {email}"}
    return f"{email} is now {'active' if active else 'deactivated'}.", None


async def _handle_activate(store, email, role, display_name, notes):
    return await _set_active_message(store, email, True)


async def _handle_deactivate(store, email, role, display_name, notes):
    return await _set_active_message(store, email, False)


async def _handle_delete(store, email, role, display_name, notes):
    # Erasure, not deactivation (S-14): mcp_users holds the only PII in the
    # system and 'deactivate' leaves the row, the notes and the login history
    # behind, so there was no way to answer a data-subject erasure request.
    if not await store.delete_user(email):
        return None, {"error": f"no such user: {email}"}
    return f"{email} and its refresh tokens were deleted.", None


_MANAGE_USERS_ACTION_HANDLERS = {
    "list": _handle_list,
    "add": _handle_add,
    "set_role": _handle_set_role,
    "activate": _handle_activate,
    "deactivate": _handle_deactivate,
    "delete": _handle_delete,
}


async def citations_manage_users(
    action: str = "list",
    email: str = "",
    role: str = "user",
    display_name: str = "",
    notes: str = "",
) -> Dict[str, Any]:
    """Manage the registered-user list for OAuth sign-in (ADMIN ONLY).
    Users, accounts, admin, permissions, roles, access, allowlist, add user, deactivate, sign-in.

    Lists, adds, activates, deactivates, deletes, or changes the role of
    registered users. A user may sign in via Google / Microsoft only while
    their row is active; role 'admin' additionally grants this
    user-management tool. 'delete' erases the row and its refresh tokens
    outright, unlike 'deactivate' which keeps the record.
    Changes take effect at the user's next token refresh (up to 1 hour).

    Args:
        action: One of: list, add, set_role, activate, deactivate, delete
        email: Target user email (required for all actions except list)
        role: 'user' or 'admin' (for add / set_role)
        display_name: Optional display name (for add)
        notes: Optional notes (for add)

    Returns:
        The full user table after the action, plus a confirmation message.
    """
    with RequestContext():
        return await _manage_users_body(action, email, role, display_name, notes)


async def _manage_users_body(
    action: str, email: str, role: str, display_name: str, notes: str
) -> Dict[str, Any]:
    valid_actions = ("list", "add", "set_role", "activate", "deactivate", "delete")
    if action not in valid_actions:
        return {"error": f"action must be one of {valid_actions}, got {action!r}"}

    store = _get_user_store()
    actor = _actor()
    try:
        if action != "list":
            email = email.strip().lower()
            if not _EMAIL_RE.match(email):
                return {"error": f"invalid email address: {email!r}"}

        handler = _MANAGE_USERS_ACTION_HANDLERS[action]
        message, error = await handler(store, email, role, display_name, notes)
        if error is not None:
            _audit_user_management(actor, action, email, role, False, error.get("error"))
            return error
        _audit_user_management(actor, action, email, role, True)

        users = await store.list_users()
        return {
            "action": action,
            "message": message or f"{len(users)} registered user(s).",
            "users": [
                {
                    "email": u["email"],
                    "display_name": u["display_name"],
                    "role": u["role"],
                    "active": u["active"],
                    "added_at": u["added_at"].isoformat() if u["added_at"] else None,
                    "last_login_at": (
                        u["last_login_at"].isoformat() if u["last_login_at"] else None
                    ),
                    "last_login_idp": u["last_login_idp"],
                    "notes": u["notes"],
                }
                for u in users
            ],
        }
    except Exception as e:
        _audit_user_management(actor, action, email, role, False, type(e).__name__)
        return format_error_response("User management failed", 500, exception=e)


def register(mcp, auth_provider=None) -> None:
    """Register citations_manage_users when the gate allows it."""
    global _auth_provider
    _auth_provider = auth_provider
    if USER_MANAGEMENT_ENABLED:
        if _auth_provider is None and os.getenv("FASTMCP_TRANSPORT", "stdio") == "http":
            # Enabled on the HTTP surface without OAuth, the only protection on
            # this tool would be the shared INTERNAL_AUTH_SECRET — anyone
            # holding that ecosystem-wide secret could self-grant admin via the
            # user DB. Refuse to start rather than register it ungated (this
            # used to log a warning and continue). stdio stays allowed: there
            # the OS process boundary is the gate.
            raise RuntimeError(
                "CITATIONS_ENABLE_USER_MANAGEMENT=true requires CITATIONS_AUTH_MODE=oauth "
                "in HTTP mode; the shared INTERNAL_AUTH_SECRET is not a per-identity "
                "gate. Use scripts/manage_mcp_users.py for out-of-band administration."
            )
        mcp.tool(
            name="citations_manage_users",
            app=AppConfig(resource_uri=USER_MANAGEMENT_URI),
            annotations={"defer_loading": True},
        )(citations_manage_users)
    else:
        logger.info(
            "citations_manage_users not registered (CITATIONS_ENABLE_USER_MANAGEMENT is "
            "off; default). Use scripts/manage_mcp_users.py for user administration."
        )
