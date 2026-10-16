"""One end-to-end deadline on the statistics fan-out (Wave 2 Part A item 5).

Citations_get_citation_statistics sends six count queries at once. One
util/deadline.Deadline (CITATIONS_CONTENT_DEADLINE_SECONDS, default 85 s,
under Cloudflare's ~100 s cut) is created when the tool starts; time spent
before the fan-out comes out of it, the fan-out waits only for what is left,
retries inside a sub-query never get a fresh budget, and the counts that
returned are kept with a deadline note for the rest. With nothing back, the
answer is the same 504 the whole-call deadline gives, worded "Deadline
exceeded". The clock is faked: the Deadline reads a FakeClock the test moves,
so the real waits below are a few hundredths of a second. Modeled on
uspto_ptab_mcp's tests/test_ocr_deadline.py.
"""

import asyncio
import time

import pytest

from uspto_enriched_citation_mcp.tools import statistics as statistics_tool
from uspto_enriched_citation_mcp.tools.statistics import get_citation_statistics
from uspto_enriched_citation_mcp.util.deadline import (
    DEFAULT_CONTENT_DEADLINE_SECONDS,
    Deadline,
    content_deadline_seconds,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch):
    """Every Deadline the tool creates reads this clock."""
    fake = FakeClock()
    created = []

    def make(seconds):
        deadline = Deadline(seconds, clock=fake)
        created.append(deadline)
        return deadline

    monkeypatch.setattr(statistics_tool, "Deadline", make)
    fake.created = created
    return fake


def _spend_before_the_fan_out(mock_runtime, clock, seconds):
    """The lane limiter's acquire is the one step before the fan-out: make it
    take `seconds` of the call's budget."""

    async def acquire(*args, **kwargs):
        clock.now += seconds
        return True

    mock_runtime.api_client.rate_limiter.acquire.side_effect = acquire


def _fan_out(slow, cancelled):
    """search_citations stand-in: the queries containing a `slow` clause
    never answer (and record their cancellation); the rest answer at once."""

    async def search_citations(*, criteria, rows, charge_quota):
        if any(clause in criteria for clause in slow):
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                cancelled.append(criteria)
                raise
        return {"response": {"numFound": 10, "docs": []}}

    return search_citations


class TestTheBudget:
    def test_default_is_85_seconds(self, monkeypatch):
        monkeypatch.delenv("CITATIONS_CONTENT_DEADLINE_SECONDS", raising=False)
        assert content_deadline_seconds() == DEFAULT_CONTENT_DEADLINE_SECONDS == 85.0

    @pytest.mark.parametrize("raw, expected", [
        ("40", 40.0), ("12.5", 12.5), ("junk", 85.0), ("0", 85.0), ("-5", 85.0),
    ])
    def test_env_parsing(self, monkeypatch, raw, expected):
        monkeypatch.setenv("CITATIONS_CONTENT_DEADLINE_SECONDS", raw)
        assert content_deadline_seconds() == expected

    def test_remaining_counts_down_and_never_goes_negative(self):
        fake = FakeClock()
        deadline = Deadline(85, clock=fake)

        fake.now += 80
        assert deadline.remaining() == pytest.approx(5.0)
        assert not deadline.expired()
        fake.now += 10
        assert deadline.remaining() == 0.0
        assert deadline.expired()


class TestStatisticsFanOut:
    @pytest.mark.asyncio
    async def test_one_deadline_per_call_from_the_env(self, mock_runtime, clock, monkeypatch):
        monkeypatch.setenv("CITATIONS_CONTENT_DEADLINE_SECONDS", "40")
        mock_runtime.api_client.search_citations.side_effect = _fan_out((), [])

        await get_citation_statistics(criteria="techCenter:2100")
        await get_citation_statistics(criteria="techCenter:2100")

        # Per call, not per attempt and not per sub-query: one each.
        assert [d.seconds for d in clock.created] == [40.0, 40.0]

    @pytest.mark.asyncio
    async def test_in_time_the_contract_is_unchanged(self, mock_runtime, clock):
        mock_runtime.api_client.search_citations.side_effect = _fan_out((), [])

        result = await get_citation_statistics(criteria="techCenter:2100")

        assert result["status"] == "success"
        assert result["total_citations"] == 10
        for key in ("deadline_exceeded", "deadline_note", "queries_unfinished",
                    "unfinished_queries", "queries_failed"):
            assert key not in result

    @pytest.mark.asyncio
    async def test_slow_breakdowns_are_cut_off_and_the_rest_are_kept(self, mock_runtime, clock):
        # 83.95 s of the 85 s budget goes before the fan-out, leaving 1.05 s:
        # the fan-out keeps a 1 s reserve, so it waits 0.05 s of real time.
        _spend_before_the_fan_out(mock_runtime, clock, 83.95)
        cancelled = []
        mock_runtime.api_client.search_citations.side_effect = _fan_out(
            ("citationCategoryCode:X", "citationCategoryCode:Y"), cancelled)

        started = time.monotonic()
        result = await get_citation_statistics(criteria="techCenter:2100")
        elapsed = time.monotonic() - started

        assert elapsed < 2.0
        assert result["status"] == "success"
        assert result["total_citations"] == 10
        assert result["examiner_cited_count"] == 10
        assert result["applicant_cited_count"] == 10
        category = result["breakdowns"]["Citation Category"]
        assert category["X — Novel (§102)"] is None  # unknown, not zero
        assert category["Y — Inventive Step (§103)"] is None
        assert category["A — Background Art"] == 10
        assert result["deadline_exceeded"] is True
        assert result["queries_unfinished"] == 2
        assert result["unfinished_queries"] == ["x_count", "y_count"]
        assert result["deadline_note"].startswith("Deadline exceeded: 2 of 6")
        assert "85s" in result["deadline_note"]
        assert "queries_failed" not in result  # cut off is not failed
        # The cut-off sub-queries were cancelled, not left running.
        assert len(cancelled) == 2
        # The Wave 1 contract still holds: one 6-token charge, sub-calls uncharged.
        mock_runtime.api_client.rate_limiter.acquire.assert_awaited_once()
        assert mock_runtime.api_client.rate_limiter.acquire.await_args.kwargs["tokens"] == 6

    @pytest.mark.asyncio
    async def test_retries_inside_a_sub_query_get_no_fresh_budget(self, mock_runtime, clock):
        """A sub-query that keeps retrying (each attempt moving the clock as
        a real one would) is cut at the call's deadline: attempts draw down
        the one budget instead of each getting their own."""
        attempts = []
        cancelled = []

        async def search_citations(*, criteria, rows, charge_quota):
            if "citationCategoryCode:A" in criteria:
                try:
                    while True:  # retry_async-style loop: attempt, back off, retry
                        attempts.append(clock.now)
                        await asyncio.sleep(0.01)
                except asyncio.CancelledError:
                    cancelled.append(criteria)
                    raise
            return {"response": {"numFound": 5, "docs": []}}

        mock_runtime.api_client.search_citations.side_effect = search_citations
        _spend_before_the_fan_out(mock_runtime, clock, 83.95)  # 0.05 s left to wait

        started = time.monotonic()
        result = await get_citation_statistics(criteria="techCenter:2100")

        # The retry loop was stopped at the call's deadline, mid-retry: a few
        # attempts, then cancelled, and the other five counts were kept.
        assert time.monotonic() - started < 2.0
        assert 1 <= len(attempts) < 50
        assert len(cancelled) == 1
        assert result["unfinished_queries"] == ["a_count"]
        assert result["total_citations"] == 5

    @pytest.mark.asyncio
    async def test_nothing_back_in_time_is_the_deadline_504(self, mock_runtime, clock):
        _spend_before_the_fan_out(mock_runtime, clock, 83.95)
        cancelled = []
        mock_runtime.api_client.search_citations.side_effect = _fan_out(("",), cancelled)

        result = await get_citation_statistics(criteria="techCenter:2100")

        assert result["status"] == "error"
        assert result["code"] == 504
        assert result["error"].startswith("Deadline exceeded")
        assert "deadline" in result["message"].lower()
        assert len(cancelled) == 6

    @pytest.mark.asyncio
    async def test_a_spent_budget_sends_no_query_at_all(self, mock_runtime, clock):
        _spend_before_the_fan_out(mock_runtime, clock, 85.0)

        result = await get_citation_statistics(criteria="techCenter:2100")

        assert result["code"] == 504
        assert result["error"].startswith("Deadline exceeded")
        mock_runtime.api_client.search_citations.assert_not_called()

    @pytest.mark.asyncio
    async def test_the_backstop_ends_the_call_at_the_same_deadline(
        self, mock_runtime, monkeypatch
    ):
        """A hang OUTSIDE the fan-out (here the limiter itself) is caught by
        run_with_deadline at the same end time: one budget, two guards."""
        monkeypatch.setenv("CITATIONS_CONTENT_DEADLINE_SECONDS", "0.1")

        async def hang(*args, **kwargs):
            await asyncio.sleep(30)

        mock_runtime.api_client.rate_limiter.acquire.side_effect = hang

        started = time.monotonic()
        result = await get_citation_statistics(criteria="techCenter:2100")

        assert time.monotonic() - started < 2.0
        assert result["code"] == 504
        assert "deadline" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_the_other_tools_keep_their_own_deadline(self, mock_runtime, monkeypatch):
        """CITATIONS_TOOL_DEADLINE still bounds the single-request tools;
        only statistics moved to the content deadline."""
        from uspto_enriched_citation_mcp.tools.search import search_citations_minimal

        monkeypatch.setenv("CITATIONS_TOOL_DEADLINE", "0.05")
        monkeypatch.setenv("CITATIONS_CONTENT_DEADLINE_SECONDS", "85")

        async def never(*args, **kwargs):
            await asyncio.sleep(30)

        mock_runtime.api_client.search_records = never

        result = await search_citations_minimal(criteria="techCenter:2100")

        assert result["code"] == 504
