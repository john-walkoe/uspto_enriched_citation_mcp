"""
Tests for MCP_APP_EXTRA_DOMAINS CSP domain build logic.

Verifies that _build_csp_domains() correctly:
- Always includes the jsdelivr CDN
- Parses comma-separated MCP_APP_EXTRA_DOMAINS values
- Strips whitespace and skips empty segments
- Returns an immutable result
"""

import os
from pathlib import Path
from unittest import mock

import pytest


# Import the helper directly from main.py for unit testing
# We test at the function level to avoid loading the full FastMCP app
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from uspto_enriched_citation_mcp.main import _build_csp_domains


@pytest.mark.parametrize(
    "env_value,expected",
    [
        pytest.param(
            None,
            ["https://cdn.jsdelivr.net"],
            id="none—no extra domains",
        ),
        pytest.param(
            "example.com",
            ["https://cdn.jsdelivr.net", "example.com"],
            id="single-domain",
        ),
        pytest.param(
            "a.com, b.com",
            ["https://cdn.jsdelivr.net", "a.com", "b.com"],
            id="two-domains-space-after-comma",
        ),
        pytest.param(
            "  a.com  ,  ,  b.com  ",
            ["https://cdn.jsdelivr.net", "a.com", "b.com"],
            id="whitespace-and-empty-segments-stripped",
        ),
    ],
)
def test_build_csp_domains(env_value, expected):
    """
    _build_csp_domains() should return correct domain list for each env var value.
    """
    env_patch = {
        "MCP_APP_EXTRA_DOMAINS": env_value if env_value is not None else ""
    }
    with mock.patch.dict(os.environ, env_patch, clear=False):
        result = _build_csp_domains()

    assert result == expected, f"Expected {expected}, got {result}"


def test_build_csp_domains_returns_list():
    """Result should be a list (not tuple or other type)."""
    with mock.patch.dict(os.environ, {}, clear=False):
        result = _build_csp_domains()
    assert isinstance(result, list)


def test_build_csp_domains_cdn_always_present():
    """CDN should always be first even when env var is empty or unset."""
    with mock.patch.dict(os.environ, {"MCP_APP_EXTRA_DOMAINS": ""}, clear=False):
        result = _build_csp_domains()
    assert result[0] == "https://cdn.jsdelivr.net"


def test_build_server_is_callable_twice():
    """The composition root used to be the module body, so the server could
    not be constructed twice in one process and importing main.py did all of
    it — including a RuntimeError path from _attach_admin_scope_checks (F-4).
    """
    from uspto_enriched_citation_mcp.main import build_server, mcp

    second = build_server()

    assert second is not mcp
    names = {
        c.name
        for c in second.local_provider._components.values()
        if hasattr(c, "name")
    }
    original = {
        c.name for c in mcp.local_provider._components.values() if hasattr(c, "name")
    }
    assert names == original
    assert "Citations_search_citations_minimal" in names
