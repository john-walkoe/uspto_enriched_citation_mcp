"""Fleet review 2026-09-03: the breaker's lock, the two CircuitBreakerError
classes, the mutated cache, error sanitization on the exception branch, and
the missing inbound rate limit."""

import asyncio

import pytest

from uspto_enriched_citation_mcp.middleware import InboundRateLimitMiddleware
from uspto_enriched_citation_mcp.shared import exceptions as exceptions_module
from uspto_enriched_citation_mcp.shared.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitState,
)
from uspto_enriched_citation_mcp.shared.error_utils import format_error_response
from uspto_enriched_citation_mcp.shared.exceptions import APIResponseError
from uspto_enriched_citation_mcp.util.cache import LRUCache, TTLCache


# ---------------------------------------------------------------------------
# One CircuitBreakerError, and it is a 503
# ---------------------------------------------------------------------------

def test_circuit_breaker_error_is_the_one_in_the_exception_hierarchy():
    assert CircuitBreakerError is exceptions_module.CircuitBreakerError
    assert CircuitBreakerError().status_code == 503


@pytest.mark.asyncio
async def test_open_circuit_surfaces_as_503_not_500():
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=60.0)

    async def _boom():
        raise APIResponseError("upstream is down")

    for _ in range(2):
        with pytest.raises(APIResponseError):
            await breaker.call(_boom)

    assert breaker.state == CircuitState.OPEN

    with pytest.raises(CircuitBreakerError) as excinfo:
        await breaker.call(_boom)
    assert excinfo.value.status_code == 503
    # A 500 is the class an agent retries; a 503 is not the same signal.
    assert format_error_response("Search failed", exception=excinfo.value)["code"] == 503


# ---------------------------------------------------------------------------
# The lock guards state, not the awaited call
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_calls_are_not_serialized_by_the_breaker_lock():
    breaker = CircuitBreaker(failure_threshold=5)
    in_flight = 0
    peak = 0
    release = asyncio.Event()

    async def _slow():
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await release.wait()
        in_flight -= 1
        return "ok"

    tasks = [asyncio.create_task(breaker.call(_slow)) for _ in range(5)]
    await asyncio.sleep(0)  # let them all reach the await
    await asyncio.sleep(0)
    release.set()
    results = await asyncio.gather(*tasks)

    assert results == ["ok"] * 5
    # Measured concurrency was exactly 1 while the lock spanned the await.
    assert peak > 1


# ---------------------------------------------------------------------------
# The cache hands out copies
# ---------------------------------------------------------------------------

def test_lru_cache_does_not_hand_out_the_stored_object():
    cache = LRUCache(max_size=10)
    stored = {"response": {"docs": [{"id": "1"}]}}
    cache.set("k", stored)

    first = cache.get("k")
    first["patent_number_resolution"] = {"input": "7971071"}
    first["response"]["docs"][0]["_pfw_link"] = "annotated"

    second = cache.get("k")
    assert "patent_number_resolution" not in second
    assert "_pfw_link" not in second["response"]["docs"][0]

    # And mutating what was handed to set() must not reach the cache either.
    stored["response"]["docs"].append({"id": "2"})
    assert len(cache.get("k")["response"]["docs"]) == 1


def test_ttl_cache_does_not_hand_out_the_stored_object():
    cache = TTLCache(default_ttl_seconds=60, max_size=10)
    cache.set("k", {"fields": ["a"]})

    got = cache.get("k")
    got["_cache_status"] = {"message": "API temporarily unavailable"}

    assert "_cache_status" not in cache.get("k")
    assert "_cache_status" not in cache.get_with_metadata("k")["value"]


# ---------------------------------------------------------------------------
# Sanitization runs on the exception branch too
# ---------------------------------------------------------------------------

def test_exception_branch_is_sanitized():
    """The client builds APIResponseError(f"HTTP error: {str(e)}") from httpx
    exceptions that embed the full upstream URL."""
    leaky = APIResponseError(
        "HTTP error: request to https://api.uspto.gov/internal/v3/search failed"
    )
    response = format_error_response("Search failed", 502, exception=leaky)

    assert "https://api.uspto.gov/internal/v3/search" not in response["error"]
    assert "https://api.uspto.gov/internal/v3/search" not in response["message"]


# ---------------------------------------------------------------------------
# Inbound rate limiting exists
# ---------------------------------------------------------------------------

def _scope(headers=None, client=("10.0.0.1", 51234), path="/mcp"):
    return {
        "type": "http",
        "path": path,
        "headers": headers or [],
        "client": client,
    }


@pytest.mark.asyncio
async def test_inbound_limiter_rejects_a_burst_from_one_identity():
    passed = {"n": 0}

    async def _app(scope, receive, send):
        passed["n"] += 1

    sent = []

    async def _send(message):
        sent.append(message)

    middleware = InboundRateLimitMiddleware(_app, requests_per_minute=3)

    for _ in range(3):
        await middleware(_scope(), None, _send)
    assert passed["n"] == 3

    await middleware(_scope(), None, _send)
    assert passed["n"] == 3
    assert sent[0]["status"] == 429


@pytest.mark.asyncio
async def test_inbound_limiter_buckets_per_identity():
    async def _app(scope, receive, send):
        pass

    async def _send(message):
        pass

    middleware = InboundRateLimitMiddleware(_app, requests_per_minute=2)
    first = _scope([(b"x-api-key", b"caller-one")])
    second = _scope([(b"x-api-key", b"caller-two")])

    for _ in range(2):
        await middleware(first, None, _send)

    # The noisy caller is now out of tokens; the quiet one must not be.
    assert not await middleware._limiter.acquire(
        endpoint=middleware._identity(first)
    )
    assert await middleware._limiter.acquire(endpoint=middleware._identity(second))


@pytest.mark.asyncio
async def test_inbound_limiter_never_keys_on_the_raw_credential():
    async def _app(scope, receive, send):
        pass

    middleware = InboundRateLimitMiddleware(_app)
    identity = middleware._identity(_scope([(b"authorization", b"Bearer s3cr3t")]))

    assert identity.startswith("bearer:")
    assert "s3cr3t" not in identity


@pytest.mark.asyncio
async def test_health_is_exempt_from_the_inbound_limit():
    passed = {"n": 0}

    async def _app(scope, receive, send):
        passed["n"] += 1

    async def _send(message):
        pass

    middleware = InboundRateLimitMiddleware(_app, requests_per_minute=1)
    for _ in range(5):
        await middleware(_scope(path="/health"), None, _send)

    assert passed["n"] == 5
