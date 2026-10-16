"""ODP 429 handling and the shared limiter's refusal (rate-limit wave
2026-10-11, plan 2c / 4a / 4c.2), Citations call sites.

The rule: on a 429, note it on the shared key cooldown, then wait
max(5 s, Retry-After) and send ONCE more, only when that wait is <= 10 s;
otherwise answer at once with the rate-limit envelope carrying
details.retry_after = max(5, Retry-After). Never a second retry. The wait
holds no shared slot. The shared limiter's TimeoutError
(SharedLimiterTimeoutError) is answered at once with the envelope, no retry.
A local-bucket rejection keeps today's behaviour (its own interval, under
5 s is fine). APITimeoutError stays retryable; the builtin TimeoutError is
no longer in the default retryable set.

No network: httpx is routed through a MockTransport and the retry sleeps are
recorded instead of waited.
"""

import asyncio

import httpx
import pytest

import uspto_enriched_citation_mcp.shared.uspto_shared_rate_limiter as rate_limiter_module
import uspto_enriched_citation_mcp.util.retry as retry_module
from uspto_enriched_citation_mcp.api import base_citation_client as base_client_module
from uspto_enriched_citation_mcp.api.enriched_client import EnrichedCitationClient
from uspto_enriched_citation_mcp.api.oa_citations_client import OACitationsClient
from uspto_enriched_citation_mcp.shared.circuit_breaker import (
    CircuitBreaker,
    is_counted_failure,
)
from uspto_enriched_citation_mcp.shared.error_utils import (
    format_error_response,
    raise_http_exception,
    retry_after_header_seconds,
)
from uspto_enriched_citation_mcp.shared.exceptions import (
    RATE_LIMIT_SOURCE_LOCAL_BUCKET,
    RATE_LIMIT_SOURCE_SHARED_LIMITER,
    RATE_LIMIT_SOURCE_UPSTREAM,
    APITimeoutError,
    RateLimitError,
)
from uspto_enriched_citation_mcp.shared.uspto_shared_rate_limiter import (
    SharedLimiterTimeoutError,
)
from uspto_enriched_citation_mcp.util.rate_limiter import reset_rate_limiter
from uspto_enriched_citation_mcp.util.retry import (
    planned_429_wait,
    retry_async,
    upstream_retry_after,
)

_REAL_ASYNC_CLIENT = httpx.AsyncClient
_POLL_CUTOFF_SECONDS = 0.25  # above the limiter's poll, below any retry sleep
_KEY = "x" * 32  # not a credential: the transport is mocked


@pytest.fixture(autouse=True)
def _no_limiter_singleton(monkeypatch):
    monkeypatch.setattr(rate_limiter_module, "_singleton", None)
    monkeypatch.setattr(rate_limiter_module, "_singleton_checked", False)
    monkeypatch.delenv("USPTO_SHARED_RATE_LIMIT_DIR", raising=False)
    reset_rate_limiter()
    yield
    reset_rate_limiter()


@pytest.fixture
def sleeps(monkeypatch):
    """Record retry_async's sleeps instead of waiting them out.

    `retry_module.asyncio` is the asyncio module itself, so this patch is
    process-wide: the shared limiter's own polls (0.05 to 0.1 s) stay real
    and unrecorded, and only a retry wait (>= 0.5 s: the smallest jittered
    backoff at base_delay 1.0) is captured."""
    recorded = []
    real_sleep = asyncio.sleep

    async def fake_sleep(seconds):
        if seconds < _POLL_CUTOFF_SECONDS:
            await real_sleep(seconds)
            return
        recorded.append(seconds)

    monkeypatch.setattr(retry_module.asyncio, "sleep", fake_sleep)
    return recorded


@pytest.fixture
def noted(monkeypatch):
    """Record every note_429 the client makes on the shared key."""
    recorded = []
    monkeypatch.setattr(base_client_module, "note_429", recorded.append)
    return recorded


def _route_httpx_through(monkeypatch, handler):
    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return _REAL_ASYNC_CLIENT(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)


def _responses(monkeypatch, *responses):
    """Serve the given responses in order (the last one repeats); returns the
    list of requests seen."""
    seen = []
    queue = list(responses)

    def handler(request):
        seen.append(request)
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return item

    _route_httpx_through(monkeypatch, handler)
    return seen


def _429(retry_after=None):
    headers = {"content-type": "application/json"}
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return httpx.Response(429, json={"error": "slow down"}, headers=headers)


def _ok():
    return httpx.Response(
        200,
        json={"response": {"numFound": 0, "docs": []}},
        headers={"content-type": "application/json"},
    )


def _client(client_cls=OACitationsClient):
    """A client with no caches (so every call reaches the transport) and its
    own breaker (so a run cannot open the shared per-prefix one)."""
    return client_cls(
        api_key=_KEY,
        enable_cache=False,
        circuit_breaker=CircuitBreaker(failure_threshold=100, recovery_timeout=9999.0),
    )


# ---------------------------------------------------------------- the rule

class TestPlannedWait:
    @pytest.mark.parametrize(
        "retry_after, expected", [(None, 5.0), (2, 5.0), (5, 5.0), (10, 10.0)]
    )
    def test_waits_once_at_the_floor_or_the_header(self, retry_after, expected):
        assert planned_429_wait(retry_after, False) == expected

    def test_a_header_above_the_absorb_ceiling_means_the_envelope(self):
        assert planned_429_wait(30, False) is None
        assert planned_429_wait(10.5, False) is None

    def test_a_second_429_is_never_retried(self):
        assert planned_429_wait(None, True) is None
        assert planned_429_wait(2, True) is None

    def test_the_envelope_wait_is_never_under_the_floor(self):
        assert upstream_retry_after(None) == 5.0
        assert upstream_retry_after(2) == 5.0
        assert upstream_retry_after(30) == 30.0
        assert upstream_retry_after("bogus") == 5.0

    def test_retry_after_header_parsing(self):
        assert retry_after_header_seconds(_429()) is None
        assert retry_after_header_seconds(_429(2)) == 2.0
        assert retry_after_header_seconds(_429("7.5")) == 7.5
        assert retry_after_header_seconds(_429("Wed, 21 Oct 2026 07:28:00 GMT")) is None
        assert retry_after_header_seconds(None) is None

    def test_an_upstream_429_is_marked_upstream(self):
        with pytest.raises(RateLimitError) as exc_info:
            raise_http_exception(_429(2))
        exc = exc_info.value
        assert exc.is_upstream
        assert exc.source == RATE_LIMIT_SOURCE_UPSTREAM
        assert exc.details["retry_after"] == 2.0
        assert exc.details["rate_limit_source"] == RATE_LIMIT_SOURCE_UPSTREAM

    def test_a_bare_rate_limit_error_is_still_a_local_rejection(self):
        exc = RateLimitError("Rate limit exceeded.", retry_after=1)
        assert exc.source == RATE_LIMIT_SOURCE_LOCAL_BUCKET
        assert not exc.is_upstream
        assert exc.status_code == 429

    def test_no_rate_limit_source_counts_toward_the_breaker(self):
        for source in (
            RATE_LIMIT_SOURCE_LOCAL_BUCKET,
            RATE_LIMIT_SOURCE_UPSTREAM,
            RATE_LIMIT_SOURCE_SHARED_LIMITER,
        ):
            assert is_counted_failure(RateLimitError(source=source)) is False

    def test_the_tool_envelope_carries_the_wait_and_the_source(self):
        exc = RateLimitError(
            "Rate limit exceeded", retry_after=30.0, source=RATE_LIMIT_SOURCE_UPSTREAM
        )
        envelope = format_error_response("Search failed", 500, exception=exc)
        assert envelope["status"] == "error"
        assert envelope["code"] == 429
        assert envelope["details"]["retry_after"] == 30.0
        assert envelope["details"]["rate_limit_source"] == RATE_LIMIT_SOURCE_UPSTREAM


# ---------------------------------------------------------------- retry_async

@pytest.mark.asyncio  # strict pytest-asyncio mode in this repo
class TestRetryAsyncRule:
    async def test_builtin_timeout_error_is_no_longer_retried(self, sleeps):
        calls = []

        @retry_async(max_attempts=3)
        async def body():
            calls.append(1)
            raise TimeoutError("shared USPTO rate limiter: no request slot within 45s")

        with pytest.raises(TimeoutError):
            await body()
        assert len(calls) == 1
        assert sleeps == []

    async def test_asyncio_timeout_error_is_no_longer_retried(self, sleeps):
        calls = []

        @retry_async(max_attempts=3)
        async def body():
            calls.append(1)
            raise asyncio.TimeoutError()

        with pytest.raises(asyncio.TimeoutError):
            await body()
        assert len(calls) == 1

    async def test_api_timeout_error_is_still_retried(self, sleeps):
        calls = []

        @retry_async(max_attempts=3, base_delay=1.0)
        async def body():
            calls.append(1)
            if len(calls) < 2:
                raise APITimeoutError("Search request timed out")
            return "ok"

        assert await body() == "ok"
        assert len(calls) == 2
        assert len(sleeps) == 1

    async def test_shared_limiter_rejection_is_raised_at_once(self, sleeps):
        calls = []

        @retry_async(max_attempts=3)
        async def body():
            calls.append(1)
            raise RateLimitError(
                "busy", retry_after=5.0, source=RATE_LIMIT_SOURCE_SHARED_LIMITER
            )

        with pytest.raises(RateLimitError) as exc_info:
            await body()
        assert len(calls) == 1
        assert sleeps == []
        assert exc_info.value.source == RATE_LIMIT_SOURCE_SHARED_LIMITER

    async def test_a_local_bucket_rejection_keeps_its_own_interval(self, sleeps):
        """The local 100/min bucket says how long until its next token; that
        interval (here 1 s, under the upstream floor) is honoured as before
        and the attempt is retried up to max_attempts."""
        calls = []

        @retry_async(max_attempts=3, base_delay=1.0, max_delay=30.0)
        async def body():
            calls.append(1)
            if len(calls) < 3:
                raise RateLimitError("Rate limit exceeded.", retry_after=1)
            return "ok"

        assert await body() == "ok"
        assert len(calls) == 3
        assert sleeps == [1.0, 1.0]


# ---------------------------------------------------------------- the client

@pytest.mark.asyncio  # strict pytest-asyncio mode in this repo
class TestClient429:
    @pytest.mark.parametrize("client_cls", [OACitationsClient, EnrichedCitationClient])
    @pytest.mark.parametrize("retry_after", [None, 2, 5])
    async def test_exactly_one_retry_after_at_least_five_seconds(
        self, monkeypatch, sleeps, noted, client_cls, retry_after
    ):
        seen = _responses(monkeypatch, _429(retry_after), _ok())
        client = _client(client_cls)

        result = await client.search_records(criteria="techCenter:2100", rows=5)
        await client.close()

        assert result["response"]["numFound"] == 0
        assert len(seen) == 2
        assert sleeps == [5.0]
        assert noted == [None if retry_after is None else float(retry_after)]

    async def test_retry_after_10_is_absorbed(self, monkeypatch, sleeps, noted):
        seen = _responses(monkeypatch, _429(10), _ok())
        client = _client()

        await client.search_records(criteria="techCenter:2100", rows=5)
        await client.close()

        assert len(seen) == 2
        assert sleeps == [10.0]
        assert noted == [10.0]

    async def test_retry_after_30_is_the_envelope_with_no_retry(self, monkeypatch, sleeps, noted):
        seen = _responses(monkeypatch, _429(30), _ok())
        client = _client()

        with pytest.raises(RateLimitError) as exc_info:
            await client.search_records(criteria="techCenter:2100", rows=5)
        await client.close()

        assert len(seen) == 1
        assert sleeps == []
        assert noted == [30.0]
        exc = exc_info.value
        assert exc.is_upstream
        assert exc.details["retry_after"] == 30.0
        assert exc.to_dict()["code"] == 429

    async def test_a_persistent_429_is_never_retried_twice(self, monkeypatch, sleeps, noted):
        seen = _responses(monkeypatch, _429(), _429(2), _429(2))
        client = _client()

        with pytest.raises(RateLimitError) as exc_info:
            await client.search_records(criteria="techCenter:2100", rows=5)
        await client.close()

        assert len(seen) == 2
        assert sleeps == [5.0]
        assert len(noted) == 2
        assert exc_info.value.details["retry_after"] == 5.0  # never under the floor

    async def test_get_fields_follows_the_same_rule(self, monkeypatch, sleeps, noted):
        seen = _responses(monkeypatch, _429(), _429(), _429())
        client = _client()

        with pytest.raises(RateLimitError):
            await client.get_fields()
        await client.close()

        assert len(seen) == 2
        assert sleeps == [5.0]

    async def test_a_local_bucket_rejection_keeps_the_old_retry(self, monkeypatch, sleeps, noted):
        """This process's own bucket said no once: the client sleeps the
        bucket's own interval (1 s here, under the upstream floor) and the
        retry succeeds. Nothing is noted on the shared key."""
        seen = _responses(monkeypatch, _ok())
        client = _client()
        answers = iter([False, True])

        async def acquire(endpoint=None, **kwargs):
            return next(answers)

        monkeypatch.setattr(client.rate_limiter, "acquire", acquire)
        monkeypatch.setattr(client, "_local_retry_after", lambda endpoint: 1)

        result = await client.search_records(criteria="techCenter:2100", rows=5)
        await client.close()

        assert result["response"]["numFound"] == 0
        assert len(seen) == 1
        assert sleeps == [1.0]
        assert noted == []

    async def test_api_timeout_is_still_retried(self, monkeypatch, sleeps, noted):
        seen = _responses(monkeypatch, httpx.ReadTimeout("slow"), _ok())
        client = _client()

        result = await client.search_records(criteria="techCenter:2100", rows=5)
        await client.close()

        assert result["response"]["numFound"] == 0
        assert len(seen) == 2
        assert len(sleeps) == 1
        assert noted == []

    async def test_limiter_timeout_is_the_envelope_at_once(
        self, monkeypatch, tmp_path, sleeps, noted
    ):
        """The real limiter is on with a 0.2 s ceiling and its slot held
        elsewhere: the refusal is a RateLimitError marked shared_limiter,
        raised with no retry, no sleep, nothing sent, nothing noted."""
        seen = _responses(monkeypatch, _ok())
        monkeypatch.setenv("USPTO_SHARED_RATE_LIMIT_DIR", str(tmp_path))
        monkeypatch.setenv("USPTO_SHARED_MAX_WAIT_SECONDS", "0.2")
        limiter = rate_limiter_module.get_shared_limiter()
        monkeypatch.setattr(limiter, "_try_acquire_any_slot", lambda: None)
        client = _client()

        with pytest.raises(RateLimitError) as exc_info:
            await client.search_records(criteria="techCenter:2100", rows=5)
        await client.close()

        assert seen == []
        assert sleeps == []
        assert noted == []
        exc = exc_info.value
        assert exc.source == RATE_LIMIT_SOURCE_SHARED_LIMITER
        assert exc.details["retry_after"] == 5.0
        assert "shared limiter" in exc.message
        assert not exc.is_upstream

    async def test_a_limiter_refusal_from_send_is_the_shared_limiter_envelope(
        self, monkeypatch, sleeps, noted
    ):
        """The same without the real limiter: _send mapping the refusal."""
        client = _client()
        calls = []

        async def refuse(*args, **kwargs):
            calls.append(1)
            raise SharedLimiterTimeoutError("no request slot within 45s")

        monkeypatch.setattr(client.client, "post", refuse)
        with pytest.raises(RateLimitError) as exc_info:
            await client.search_records(criteria="techCenter:2100", rows=5)
        await client.close()

        assert len(calls) == 1  # no retry
        assert sleeps == []
        assert noted == []
        assert exc_info.value.source == RATE_LIMIT_SOURCE_SHARED_LIMITER
        assert exc_info.value.to_dict()["code"] == 429

    async def test_the_wait_holds_no_shared_slot(self, monkeypatch, tmp_path):
        monkeypatch.setenv("USPTO_SHARED_RATE_LIMIT_DIR", str(tmp_path))
        monkeypatch.setenv("USPTO_SHARED_RATE_LIMIT_RPS", "1000")
        # The real limiter is on, so the retry would wait out the 5 s
        # cooldown the 429 wrote; floor it at 0 for the test.
        monkeypatch.setattr(rate_limiter_module, "_COOLDOWN_FLOOR_SECONDS", 0.0)
        limiter = rate_limiter_module.get_shared_limiter()
        slot_free_during_wait = []
        real_sleep = asyncio.sleep

        async def fake_sleep(seconds):
            if seconds < _POLL_CUTOFF_SECONDS:  # the limiter's own polls stay real
                await real_sleep(seconds)
                return
            fh = limiter._try_acquire_any_slot()
            slot_free_during_wait.append(fh is not None)
            if fh is not None:
                limiter._release_slot(fh)

        monkeypatch.setattr(retry_module.asyncio, "sleep", fake_sleep)
        _responses(monkeypatch, _429(), _ok())
        client = _client()

        result = await client.search_records(criteria="techCenter:2100", rows=5)
        await client.close()

        assert result["response"]["numFound"] == 0
        assert slot_free_during_wait == [True]
        # And the real limiter saw the 429: the cooldown is on the key.
        assert limiter._read_cooldown_until() > 0

