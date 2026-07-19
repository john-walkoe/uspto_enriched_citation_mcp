"""Manage the mcp_users registered-user list (OAuth authorization source).

  uv run python scripts/manage_mcp_users.py list
  uv run python scripts/manage_mcp_users.py add jane@firm.com --name "Jane Doe"
  uv run python scripts/manage_mcp_users.py add john@x.com --role admin
  uv run python scripts/manage_mcp_users.py set-role jane@firm.com admin
  uv run python scripts/manage_mcp_users.py deactivate jane@firm.com
  uv run python scripts/manage_mcp_users.py activate jane@firm.com

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
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


async def run(args: argparse.Namespace) -> int:
    from uspto_enriched_citation_mcp.auth.store import McpUserStore

    db_path = os.getenv("CITATIONS_AUTH_DB_PATH", "data/mcp_auth.db")
    store = McpUserStore(db_path)

    if args.command == "list":
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

    email = args.email.strip().lower()
    if args.command == "add":
        await store.upsert_user(
            email, role=args.role, display_name=args.name, notes=args.notes
        )
        print(f"added/updated {email} role={args.role}")
    elif args.command == "set-role":
        user = await store.get_user(email)
        if user is None:
            print(f"no such user: {email}", file=sys.stderr)
            return 1
        await store.upsert_user(email, role=args.role, active=user["active"])
        print(f"{email} role -> {args.role}")
    elif args.command in ("activate", "deactivate"):
        active = args.command == "activate"
        if not await store.set_active(email, active):
            print(f"no such user: {email}", file=sys.stderr)
            return 1
        print(f"{email} active -> {active}")
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

    for cmd in ("activate", "deactivate"):
        p = sub.add_parser(cmd)
        p.add_argument("email")

    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
