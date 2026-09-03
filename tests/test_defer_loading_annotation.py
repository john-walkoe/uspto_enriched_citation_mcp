"""The `defer_loading` tool annotation must reach the wire.

Two tools are eager (`Citations_search_citations_minimal`,
`Citations_get_guidance`); the other nine are deferred, and that split is the
server's context saving. `defer_loading` is not an MCP spec field, and MCP SDK
2.x sieves non-spec fields out of spec-method results per protocol version —
see `fastmcp_compat` for the mechanism. Without that shim every tool arrives
eagerly loaded, with no error and no log line.

These tests assert against `serialize_server_result`, the SDK call that
actually shapes the tools/list response, rather than against `to_mcp_tool()`:
an incomplete shim passes the latter and still strips the wire.
"""

import pytest

from uspto_enriched_citation_mcp.fastmcp_compat import apply as apply_compat

# main.py applies the shim at import; call it directly so this module also
# passes when run alone.
apply_compat()

# The eager set as served by FastMCP 3.4.2 immediately before the FastMCP 4
# migration, captured from a real stdio tools/list. Pinned here so the upgrade
# cannot quietly change which tools load eagerly.
#
# These are the same three tools SERVER_INSTRUCTIONS now lists as
# "ALWAYS-AVAILABLE"; it used to omit Citations_search_oa_citations_minimal.
EAGER = {
    "Citations_search_citations_minimal",
    "Citations_get_guidance",
    "Citations_search_oa_citations_minimal",
}


def _protocol_versions():
    from mcp_types.methods import SERVER_RESULTS

    return sorted(v for (m, v) in SERVER_RESULTS if m == "tools/list")


def _sieve(version, tools):
    """Shape a tools/list payload exactly as the SDK's ServerRunner does."""
    from mcp_types.methods import serialize_server_result

    payload = {
        "tools": tools,
        # Required by the 2026-07-28 surface (SEP-2549); ignored by older ones.
        "resultType": "complete",
        "ttlMs": 0,
        "cacheScope": "private",
    }
    return serialize_server_result("tools/list", version, payload)


@pytest.mark.parametrize("version", _protocol_versions())
def test_custom_annotation_survives_version_sieve(version):
    from fastmcp.tools.base import Tool

    probe = Tool(
        name="probe",
        parameters={"type": "object"},
        annotations={"defer_loading": True, "readOnlyHint": True},
    )
    dumped = probe.to_mcp_tool().model_dump(
        by_alias=True, mode="json", exclude_none=True
    )
    sieved = _sieve(version, [dumped])
    assert sieved["tools"][0]["annotations"]["defer_loading"] is True
    # The spec hint must not be collateral damage of allowing extras.
    assert sieved["tools"][0]["annotations"]["readOnlyHint"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("version", _protocol_versions())
async def test_registered_tools_keep_their_defer_flags(version):
    """End-to-end: the real server's tools, through the real sieve."""
    from uspto_enriched_citation_mcp.main import mcp

    tools = list(await mcp.list_tools())
    dumped = [
        t.to_mcp_tool(name=t.name).model_dump(
            by_alias=True, mode="json", exclude_none=True
        )
        for t in tools
    ]
    sieved = _sieve(version, dumped)

    flags = {
        t["name"]: t.get("annotations", {}).get("defer_loading")
        for t in sieved["tools"]
    }
    missing = [name for name, flag in flags.items() if flag is None]
    assert not missing, f"defer_loading stripped for: {missing}"

    for name, flag in flags.items():
        expected = name not in EAGER
        assert flag is expected, (
            f"{name}: defer_loading={flag}, expected {expected}"
        )


def test_tool_titles_are_pinned_to_tool_names():
    """FastMCP 4 derives a title from the name when none is set
    ("Citations Get Guidance"); `_pin_tool_titles` keeps the displayed label
    equal to the name, as every doc and guidance string spells it.
    """
    from uspto_enriched_citation_mcp.main import mcp
    from fastmcp.tools.base import Tool

    tools = [
        c for c in mcp.local_provider._components.values() if isinstance(c, Tool)
    ]
    assert tools, "no tools registered"
    for tool in tools:
        assert tool.to_mcp_tool(name=tool.name).title == tool.name
