"""Rotate INTERNAL_AUTH_SECRET with a two-step overlap window (S-06, PT-14).

  uv run python scripts/rotate_internal_auth_secret.py

INTERNAL_AUTH_SECRET is the x-api-key transport-gate credential shared by
all four USPTO MCPs (plus, in FPD/PTAB, the HMAC root for the inter-MCP
service tokens they use to register documents with PFW's centralized
proxy; Citations does not mint or verify those). It has always been one
value, generated once by whichever MCP installs first and copied by the
others ("first MCP wins"), with no key id and no rotation path -- rotating
meant deleting the stored file on every host and restarting all four
servers in the same instant, which in practice meant it never happened.

This generates a new root, writes "new,old" into this MCP's secure store
(the existing DPAPI / systemd-creds-backed single-key-per-file store --
it stores whatever string it is given; a comma just makes that string a
rotation list), and prints the INTERNAL_AUTH_SECRET env line every one of
the four MCPs' HTTP deployments should be updated to. The x-api-key gate
accepts ANY listed candidate, so the fleet does not need to restart in the
same instant.

Two-step rotation:
  1. Run this script once (on any one of the four hosts -- they do not need
     to agree on WHERE the secret lives, only on its value). Deploy the
     printed "new,old" value to all four MCPs and roll them one at a time;
     each keeps accepting both values while the others are mid-rollout.
  2. Once every MCP is confirmed on the new deploy, set INTERNAL_AUTH_SECRET
     to just the new value (drop the old one, printed below too) and roll
     again to close the overlap window. Leaving both values in place
     indefinitely keeps the retired secret live.
"""
from __future__ import annotations

import base64
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def main() -> int:
    from uspto_enriched_citation_mcp.shared_secure_storage import (
        get_internal_auth_secret,
        split_secret_candidates,
        store_internal_auth_secret,
    )

    existing = get_internal_auth_secret()
    current_roots = split_secret_candidates(existing)
    if not current_roots:
        print(
            "No existing INTERNAL_AUTH_SECRET in secure storage. Run the "
            "installer (or set INTERNAL_AUTH_SECRET directly) to provision "
            "one before rotating.",
            file=sys.stderr,
        )
        return 1

    new_secret = base64.b64encode(secrets.token_bytes(32)).decode("utf-8")
    current = current_roots[0]
    combined = f"{new_secret},{current}"

    if not store_internal_auth_secret(combined):
        print(
            "Failed to write the rotated secret to secure storage.",
            file=sys.stderr,
        )
        return 1

    print("Rotated INTERNAL_AUTH_SECRET (overlap window: new + previous).")
    print()
    print("Step 1 -- deploy this to ALL FOUR USPTO MCPs and roll each one:")
    print(f"  INTERNAL_AUTH_SECRET={combined}")
    print()
    print(
        "Step 2 -- once every MCP is confirmed on the new deploy, drop the "
        "overlap window:"
    )
    print(f"  INTERNAL_AUTH_SECRET={new_secret}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
