"""Registration gate for citations_manage_users (PTAB parity).

The tool must be absent from the registered tool set unless
CITATIONS_ENABLE_USER_MANAGEMENT=true (default off — stdio never needs it,
and non-OAuth HTTP would expose it behind only the shared
INTERNAL_AUTH_SECRET).

Registration happens at import time, so each state runs in a subprocess.
"""

import os
import subprocess
import sys

_PROBE = (
    "from uspto_enriched_citation_mcp.main import mcp\n"
    "from fastmcp.tools.base import Tool\n"
    "names = [c.name for c in mcp.local_provider._components.values()"
    " if isinstance(c, Tool)]\n"
    "print('PRESENT' if 'citations_manage_users' in names else 'ABSENT')\n"
    "print('COUNT', len(names))\n"
)


def _probe(extra_env: dict) -> tuple[str, int]:
    env = {**os.environ}
    env.pop("CITATIONS_ENABLE_USER_MANAGEMENT", None)
    env.setdefault("USPTO_API_KEY", "x" * 30)
    env.update(extra_env)
    result = subprocess.run(
        [sys.executable, "-c", _PROBE],
        capture_output=True, text=True, env=env, timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    lines = result.stdout.strip().splitlines()
    present = lines[-2].strip()
    count = int(lines[-1].split()[-1])
    return present, count


def test_manage_users_absent_by_default():
    present, count = _probe({})
    assert present == "ABSENT"
    assert count == 10


def test_manage_users_registered_when_enabled():
    present, count = _probe({"CITATIONS_ENABLE_USER_MANAGEMENT": "true"})
    assert present == "PRESENT"
    assert count == 11


def test_manage_users_refuses_http_without_oauth():
    """HTTP + no OAuth provider must fail startup, not register ungated.

    The shared INTERNAL_AUTH_SECRET is the only gate on that surface and it is
    the same value across the four USPTO MCPs, so registering the tool there
    hands suite-wide user administration to any holder of the transport
    secret. stdio is unaffected (covered by the test above).
    """
    env = dict(os.environ)
    env.setdefault("USPTO_API_KEY", "x" * 30)
    env["CITATIONS_ENABLE_USER_MANAGEMENT"] = "true"
    env["FASTMCP_TRANSPORT"] = "http"
    result = subprocess.run(
        [sys.executable, "-c", _PROBE],
        capture_output=True, text=True, env=env, timeout=120,
    )
    assert result.returncode != 0
    assert "CITATIONS_ENABLE_USER_MANAGEMENT=true requires" in result.stderr
