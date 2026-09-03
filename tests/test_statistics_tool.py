"""Statistics tool and service, against the mocked runtime.

Replaces tests/test_statistics.py, which was 24 tests gated on a live USPTO
key whose only assertions were `assert result is not None` (20 times) and
`assert result["status"] in ["success", "error"]` — a tool returning
`{"status": "error"}` for every input passed all of them. All 24 also passed
`stats_fields=[...]`, the parameter the tool accepted and ignored, which is
how a dead argument survives (testing-implementation T-2, readability R-7).

These run by default, assert on real values, and cover the two behaviors the
old file only appeared to cover: the breakdown shape and the fan-out's quota
accounting.
"""

import inspect

import pytest

from uspto_enriched_citation_mcp.services import citation_service as service_module
from uspto_enriched_citation_mcp.tools.statistics import get_citation_statistics


def _counts(*num_found):
    return [{"response": {"numFound": n, "docs": []}} for n in num_found]


@pytest.mark.asyncio
async def test_breakdowns_carry_the_counts_from_the_fan_out(mock_runtime):
    mock_runtime.api_client.search_citations.side_effect = _counts(
        1000, 400, 300, 100, 700, 250
    )

    result = await get_citation_statistics(criteria="techCenter:2100")

    assert result["status"] == "success"
    assert result["total_citations"] == 1000
    assert result["examiner_cited_count"] == 700
    assert result["applicant_cited_count"] == 250
    assert result["breakdowns"]["Citation Category"] == {
        "X — Novel (§102)": 400,
        "Y — Inventive Step (§103)": 300,
        "A — Background Art": 100,
    }
    assert result["breakdowns"]["Cited By"] == {
        "Examiner (Form 892)": 700,
        "Applicant (Form 1449)": 250,
    }
    assert "queries_failed" not in result


@pytest.mark.asyncio
async def test_empty_criteria_queries_every_record(mock_runtime):
    mock_runtime.api_client.search_citations.side_effect = _counts(9, 1, 2, 3, 4, 5)

    result = await get_citation_statistics()

    assert result["query"] == "all records"
    first_call = mock_runtime.api_client.search_citations.call_args_list[0]
    assert first_call.kwargs["criteria"] == "*:*"


@pytest.mark.asyncio
async def test_criteria_scopes_every_breakdown_query(mock_runtime):
    mock_runtime.api_client.search_citations.side_effect = _counts(1, 1, 1, 1, 1, 1)

    await get_citation_statistics(criteria="techCenter:2100")

    scoped = [
        call.kwargs["criteria"]
        for call in mock_runtime.api_client.search_citations.call_args_list[1:]
    ]
    assert all(q.startswith("(techCenter:2100) AND (") for q in scoped)


@pytest.mark.asyncio
async def test_fan_out_does_not_double_charge_the_quota(mock_runtime):
    """The tool charges the limiter once for the whole fan-out, so the
    sub-calls must not charge again (S-13)."""
    mock_runtime.api_client.search_citations.side_effect = _counts(1, 1, 1, 1, 1, 1)

    await get_citation_statistics(criteria="techCenter:2100")

    calls = mock_runtime.api_client.search_citations.call_args_list
    assert len(calls) == 6
    assert all(call.kwargs["charge_quota"] is False for call in calls)


@pytest.mark.asyncio
async def test_partial_failure_is_reported_not_hidden(mock_runtime):
    mock_runtime.api_client.search_citations.side_effect = [
        {"response": {"numFound": 10, "docs": []}},
        RuntimeError("upstream blew up"),
        {"response": {"numFound": 3, "docs": []}},
        {"response": {"numFound": 2, "docs": []}},
        {"response": {"numFound": 6, "docs": []}},
        {"response": {"numFound": 1, "docs": []}},
    ]

    result = await get_citation_statistics(criteria="techCenter:2100")

    assert result["status"] == "success"
    assert result["queries_failed"] == 1
    assert result["breakdowns"]["Citation Category"]["X — Novel (§102)"] == 0


@pytest.mark.asyncio
async def test_oversized_criteria_is_a_400(mock_runtime):
    result = await get_citation_statistics(criteria="techCenter:" + "1" * 6000)
    assert result["status"] == "error"
    assert result["code"] == 400


@pytest.mark.asyncio
async def test_invalid_lucene_is_a_400(mock_runtime):
    result = await get_citation_statistics(criteria="notAField:2100")
    assert result["status"] == "error"
    assert result["code"] == 400


@pytest.mark.asyncio
async def test_rate_limit_rejection_is_reported(mock_runtime, monkeypatch):
    class _Full:
        async def acquire(self, *args, **kwargs):
            return False

    monkeypatch.setattr(service_module, "get_rate_limiter", lambda: _Full())

    result = await get_citation_statistics(criteria="techCenter:2100")

    assert result["status"] == "error"
    assert "Rate limit exceeded" in result["error"]
    mock_runtime.api_client.search_citations.assert_not_called()


def test_stats_fields_is_no_longer_published_in_the_tool_schema():
    """It was advertised, mutable-defaulted and silently ignored."""
    assert "stats_fields" not in inspect.signature(get_citation_statistics).parameters
