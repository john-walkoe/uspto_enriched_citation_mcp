"""Manage the mcp_users registered-user list (OAuth authorization source).

  uv run python scripts/manage_mcp_users.py list
  uv run python scripts/manage_mcp_users.py add jane@firm.com --name "Jane Doe"
  uv run python scripts/manage_mcp_users.py add john@x.com --role admin
  uv run python scripts/manage_mcp_users.py set-role jane@firm.com admin
  uv run python scripts/manage_mcp_users.py deactivate jane@firm.com
  uv run python scripts/manage_mcp_users.py activate jane@firm.com
  uv run python scripts/manage_mcp_users.py delete jane@firm.com

A user may connect an MCP client through the Google / Entra ID sign-in only
while their row is active; role 'admin' adds the citations:admin scope (the
citations_manage_users tool). Deactivation takes effect at the user's next
token refresh (access tokens live CITATIONS_AUTH_ACCESS_TTL seconds, 1h).

The SQLite file is CITATIONS_AUTH_DB_PATH (default data/mcp_auth.db). On the
deployment box run inside the container against the mounted DB:
`docker exec uspto-enriched-citations-mcp python scripts/manage_mcp_users.py list`.
This is the bootstrap surface — the first admin must be seeded here before
the citations_manage_users MCP tool can be used.
"""
from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _audit(action: str, target: str, role: str | None, success: bool) -> None:
    """Mirror tools/admin.py::_audit_user_management for the CLI.

    Every mutation of the authorization source of truth is audited whichever
    surface performed it; the CLI is the bootstrap surface, so an unaudited
    CLI leaves the first admin grant with no record of who made it (S-22).
    Never raises: a failed audit write must not turn a successful grant into
    a command failure.
    """
    try:
        from uspto_enriched_citation_mcp.util.security_logger import (
            get_security_logger,
        )

        try:
            os_user = getpass.getuser()
        except Exception:
            os_user = "unknown"
        get_security_logger().admin_action(
            actor=f"cli:{os_user}",
            action=action,
            target=target,
            success=success,
            role=role,
            detail=None,
        )
    except Exception as audit_error:
        print(
            f"warning: audit write failed ({type(audit_error).__name__})",
            file=sys.stderr,
        )


async def _print_users(store) -> int:
    users = await store.list_users()
    if not users:
        print("No registered users.")
        return 0
    fmt = "{:<38} {:<6} {:<8} {:<24} {}"
    print(fmt.format("EMAIL", "ROLE", "ACTIVE", "LAST LOGIN", "NAME"))
    for u in users:
        last = (
            f"{u['last_login_at']:%Y-%m-%d %H:%M} {u['last_login_idp'] or ''}"
            if u["last_login_at"]
            else "-"
        )
        print(fmt.format(
            u["email"], u["role"], str(u["active"]), last,
            u["display_name"] or "",
        ))
    return 0


async def run(args: argparse.Namespace) -> int:
    from uspto_enriched_citation_mcp.auth.store import McpUserStore

    db_path = os.getenv("CITATIONS_AUTH_DB_PATH", "data/mcp_auth.db")
    store = McpUserStore(db_path)

    if args.command == "list":
        return await _print_users(store)

    email = args.email.strip().lower()
    if args.command == "add":
        await store.upsert_user(
            email, role=args.role, display_name=args.name, notes=args.notes
        )
        _audit("add", email, args.role, True)
        print(f"added/updated {email} role={args.role}")
    elif args.command == "set-role":
        user = await store.get_user(email)
        if user is None:
            _audit("set_role", email, args.role, False)
            print(f"no such user: {email}", file=sys.stderr)
            return 1
        await store.upsert_user(email, role=args.role, active=user["active"])
        _audit("set_role", email, args.role, True)
        print(f"{email} role -> {args.role}")
    elif args.command in ("activate", "deactivate"):
        active = args.command == "activate"
        if not await store.set_active(email, active):
            _audit(args.command, email, None, False)
            print(f"no such user: {email}", file=sys.stderr)
            return 1
        _audit(args.command, email, None, True)
        print(f"{email} active -> {active}")
    elif args.command == "delete":
        # Erasure path (S-14): removes the row and its refresh tokens. The
        # subscriber list is the only PII in this system, so a data-subject
        # request must not require hand-editing SQLite.
        if not await store.delete_user(email):
            _audit("delete", email, None, False)
            print(f"no such user: {email}", file=sys.stderr)
            return 1
        _audit("delete", email, None, True)
        print(f"deleted {email} and revoked its refresh tokens")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list")

    p_add = sub.add_parser("add")
    p_add.add_argument("email")
    p_add.add_argument("--role", choices=("user", "admin"), default="user")
    p_add.add_argument("--name", default=None, help="display name")
    p_add.add_argument("--notes", default=None)

    p_role = sub.add_parser("set-role")
    p_role.add_argument("email")
    p_role.add_argument("role", choices=("user", "admin"))

    for cmd in ("activate", "deactivate", "delete"):
        p = sub.add_parser(cmd)
        p.add_argument("email")

    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
