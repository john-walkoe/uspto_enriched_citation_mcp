"""Parity between the minimal and balanced tiers on both lanes.

The four search tools were two copy-and-edit pairs that had drifted: only
`search_citations_minimal` opened a `RequestContext` and emitted security
events, so half the enriched surface produced no `request_id` and a
balanced-tier 500 was invisible to the security log (code-duplication D-1,
logging S-19, error-handling E-7). Each pair now runs one implementation
parameterized by tier; these tests pin the properties that used to differ.

Also covers the pagination floors and the deep-paging ceiling (S-28), which
were absent on every tier: `rows` was capped three times and `start` zero
times.
"""

import pytest

from uspto_enriched_citation_mcp.config.constants import MAX_PAGINATION_START
from uspto_enriched_citation_mcp.tools import oa as oa_tools
from uspto_enriched_citation_mcp.tools import search as search_tools
from uspto_enriched_citation_mcp.tools.oa import (
    search_oa_citations_balanced,
    search_oa_citations_minimal,
)
from uspto_enriched_citation_mcp.tools.search import (
    search_citations_balanced,
    search_citations_minimal,
)

_DOCS = {
    "response": {
        "numFound": 1,
        "start": 0,
        "docs": [
            {
                "id": "0de7ea10c59e03dab218a40dece9dffd",
                "patentApplicationNumber": "16816197",
                "citedDocumentIdentifier": "US-1234567-A",
                "techCenter": "2100",
            }
        ],
    }
}

ENRICHED_TOOLS = [search_citations_minimal, search_citations_balanced]
OA_TOOLS = [search_oa_citations_minimal, search_oa_citations_balanced]


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", ENRICHED_TOOLS)
async def test_enriched_tiers_both_report_a_request_id(mock_runtime, tool):
    mock_runtime.api_client.search_records.return_value = dict(_DOCS)
    result = await tool(criteria="techCenter:2100")
    assert result["query_info"]["request_id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", ENRICHED_TOOLS)
async def test_enriched_tiers_both_log_an_api_error(mock_runtime, monkeypatch, tool):
    calls = []
    monkeypatch.setattr(
        search_tools.security_logger,
        "api_error",
        lambda **kw: calls.append(kw),
    )
    mock_runtime.api_client.search_records.side_effect = RuntimeError("boom")

    result = await tool(criteria="techCenter:2100")

    assert result["status"] == "error"
    assert result["code"] == 500
    assert calls and calls[0]["error_type"] == "RuntimeError"


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", OA_TOOLS)
async def test_oa_tiers_both_log_an_api_error(mock_runtime, monkeypatch, tool):
    calls = []
    monkeypatch.setattr(
        oa_tools.security_logger,
        "api_error",
        lambda **kw: calls.append(kw),
    )
    mock_runtime.oa_client.search_records.side_effect = RuntimeError("boom")

    result = await tool(criteria="techCenter:2100")

    assert result["status"] == "error"
    assert result["code"] == 500
    assert calls and calls[0]["error_type"] == "RuntimeError"


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", ENRICHED_TOOLS)
async def test_enriched_tiers_keep_their_own_guidance(mock_runtime, tool):
    mock_runtime.api_client.search_records.return_value = dict(_DOCS)
    result = await tool(criteria="techCenter:2100")
    assert "next_steps" in result["guidance"]


@pytest.mark.asyncio
async def test_balanced_guidance_still_counts_passages(mock_runtime):
    payload = {
        "response": {
            "numFound": 2,
            "start": 0,
            "docs": [
                {"id": "a" * 32, "passageLocationText": "col 3 line 20"},
                {"id": "b" * 32},
            ],
        }
    }
    mock_runtime.api_client.search_records.return_value = payload
    result = await search_citations_balanced(criteria="techCenter:2100")
    assert result["guidance"]["analysis_ready"] is True
    assert result["guidance"]["passage_analysis"] == 1


@pytest.mark.asyncio
async def test_oa_balanced_still_has_no_guidance_block(mock_runtime):
    mock_runtime.oa_client.search_records.return_value = dict(_DOCS)
    result = await search_oa_citations_balanced(criteria="techCenter:2100")
    assert "guidance" not in result
    assert result["pfw_link"]


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", ENRICHED_TOOLS + OA_TOOLS)
@pytest.mark.parametrize(
    "kwargs",
    [
        {"rows": 0},
        {"rows": -1},
        {"start": -1},
        {"start": MAX_PAGINATION_START + 1},
    ],
)
async def test_pagination_bounds_are_rejected(mock_runtime, tool, kwargs):
    mock_runtime.api_client.search_records.return_value = dict(_DOCS)
    mock_runtime.oa_client.search_records.return_value = dict(_DOCS)
    result = await tool(criteria="techCenter:2100", **kwargs)
    assert result["status"] == "error"
    assert result["code"] == 400


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", ENRICHED_TOOLS + OA_TOOLS)
async def test_pagination_boundary_values_are_accepted(mock_runtime, tool):
    mock_runtime.api_client.search_records.return_value = dict(_DOCS)
    mock_runtime.oa_client.search_records.return_value = dict(_DOCS)
    result = await tool(criteria="techCenter:2100", rows=1, start=MAX_PAGINATION_START)
    assert result.get("status") != "error"


# ----------------------------------------------------------------- deadline


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", ENRICHED_TOOLS + OA_TOOLS)
async def test_a_tool_that_never_returns_hits_the_server_deadline(
    mock_runtime, monkeypatch, tool
):
    """Each hop was bounded and the whole call was not: three retry attempts
    at the 30s HTTP timeout plus backoff is about 93 seconds, and every
    reverse proxy in front of this cuts the connection first (R-5)."""
    import asyncio

    monkeypatch.setenv("CITATIONS_TOOL_DEADLINE", "0.05")

    async def never(*args, **kwargs):
        await asyncio.sleep(30)

    mock_runtime.api_client.search_records = never
    mock_runtime.oa_client.search_records = never

    result = await tool(criteria="techCenter:2100")

    assert result["status"] == "error"
    assert result["code"] == 504
    assert "deadline" in result["message"].lower()


@pytest.mark.asyncio
async def test_the_deadline_falls_back_on_a_bad_value(monkeypatch):
    from uspto_enriched_citation_mcp.tools._shared import (
        DEFAULT_TOOL_DEADLINE_SECONDS,
        tool_deadline_seconds,
    )

    monkeypatch.setenv("CITATIONS_TOOL_DEADLINE", "not-a-number")
    assert tool_deadline_seconds() == DEFAULT_TOOL_DEADLINE_SECONDS
    monkeypatch.setenv("CITATIONS_TOOL_DEADLINE", "-5")
    assert tool_deadline_seconds() == DEFAULT_TOOL_DEADLINE_SECONDS
    monkeypatch.setenv("CITATIONS_TOOL_DEADLINE", "12.5")
    assert tool_deadline_seconds() == 12.5


# ------------------------------------------------- correlation on every tool


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_path,call",
    [
        ("api_client.search_records", lambda t: t(criteria="techCenter:2100")),
        ("api_client.search_records", lambda t: t(criteria="techCenter:2100")),
        ("oa_client.search_records", lambda t: t(criteria="techCenter:2100")),
        ("oa_client.search_records", lambda t: t(criteria="techCenter:2100")),
    ],
    ids=["enriched_minimal", "enriched_balanced", "oa_minimal", "oa_balanced"],
)
async def test_search_error_envelopes_carry_a_request_id(
    mock_runtime, request, tool_path, call
):
    """Correlation covered ONE tool out of eleven: RequestContext is a
    complete, correct contextvar mechanism that had exactly one production
    call site, so ten tools produced error responses with no request_id
    (S-19 / E-7). format_error_response attaches it whenever a context is
    open, so its presence in the envelope is the proof."""
    tools = {
        "enriched_minimal": search_citations_minimal,
        "enriched_balanced": search_citations_balanced,
        "oa_minimal": search_oa_citations_minimal,
        "oa_balanced": search_oa_citations_balanced,
    }
    tool = tools[request.node.callspec.id]

    client, attr = tool_path.split(".")
    setattr(getattr(mock_runtime, client), attr, _raiser)

    result = await call(tool)

    assert result["status"] == "error"
    assert result["code"] == 500
    assert result["request_id"]


async def _raiser(*args, **kwargs):
    raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_details_statistics_and_utility_errors_carry_a_request_id(mock_runtime):
    from uspto_enriched_citation_mcp.tools.details import get_citation_details
    from uspto_enriched_citation_mcp.tools.oa import get_oa_citation_fields
    from uspto_enriched_citation_mcp.tools.statistics import get_citation_statistics
    from uspto_enriched_citation_mcp.tools.utility import (
        get_available_fields,
        validate_query,
    )

    mock_runtime.api_client.get_fields = _raiser
    mock_runtime.oa_client.get_fields = _raiser
    mock_runtime.api_client.search_citations = _raiser
    # Patch the service method the tool calls, so the failure is the one this
    # test installed rather than an artifact of an AsyncMock further down.
    mock_runtime.citation_service.get_details = _raiser

    for call in (
        lambda: get_citation_details("0de7ea10c59e03dab218a40dece9dffd"),
        lambda: get_available_fields(),
        lambda: get_oa_citation_fields(),
    ):
        result = await call()
        assert result["status"] == "error", result
        assert result["request_id"], result

    # validate_query's failure comes from the service layer, which returns a
    # degraded envelope of its own rather than raising.
    mock_runtime.citation_service.validate_and_optimize_query = _raiser
    validated = await validate_query("techCenter:2100")
    assert validated["status"] == "error"
    assert validated["request_id"]

    # get_citation_statistics degrades rather than failing: every sub-query
    # errors, so the counts are zero and queries_failed reports how many.
    stats = await get_citation_statistics(criteria="techCenter:2100")
    assert stats["queries_failed"] == 6


@pytest.mark.asyncio
async def test_the_context_is_closed_again_after_a_tool_returns(mock_runtime):
    from uspto_enriched_citation_mcp.util.request_context import get_request_id

    mock_runtime.api_client.search_records.return_value = dict(_DOCS)
    assert get_request_id() is None
    await search_citations_minimal(criteria="techCenter:2100")
    assert get_request_id() is None


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", ENRICHED_TOOLS)
async def test_a_raw_upstream_error_is_re_enveloped(mock_runtime, tool):
    """`if "error" in result: return result` handed the caller USPTO's shape
    — no status, no code, no request_id (E-5)."""
    mock_runtime.api_client.search_records.return_value = {
        "error": "upstream said no"
    }
    result = await tool(criteria="techCenter:2100")
    assert result["status"] == "error"
    assert result["code"] == 502
    assert "upstream said no" in result["error"]
    assert result["request_id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", OA_TOOLS)
async def test_a_raw_upstream_oa_error_is_re_enveloped(mock_runtime, tool):
    mock_runtime.oa_client.search_records.return_value = {"error": "upstream said no"}
    result = await tool(criteria="techCenter:2100")
    assert result["status"] == "error"
    assert result["code"] == 502
    assert result["request_id"]
