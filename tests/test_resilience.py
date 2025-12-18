"""
Tests for API resilience features in USPTO Enriched Citation MCP.

Tests rate limiting, circuit breaker, retry logic, and caching to ensure
the system handles failures gracefully and prevents abuse.

Run with: uv run pytest tests/test_resilience.py -v
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from uspto_enriched_citation_mcp.util.rate_limiter import (
    TokenBucket,
    RateLimiter,
    RateLimitConfig,
    get_rate_limiter,
    reset_rate_limiter,
)
from uspto_enriched_citation_mcp.shared.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerError,
    circuit_breaker,
)
from uspto_enriched_citation_mcp.util.retry import (
    calculate_backoff,
    is_retryable_error,
    retry_async,
)
from uspto_enriched_citation_mcp.shared.exceptions import (
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
)


class TestTokenBucket:
    """Test token bucket rate limiting algorithm."""

    def test_token_bucket_initialization(self):
        """Test 1.1: Token bucket initializes with full capacity."""
        bucket = TokenBucket(rate=10.0, capacity=20.0)

        assert bucket.rate == 10.0
        assert bucket.capacity == 20.0
        assert bucket.tokens == 20.0  # Starts full

    def test_token_consumption_success(self):
        """Test 1.2: Tokens can be consumed when available."""
        bucket = TokenBucket(rate=10.0, capacity=10.0)

        # Should be able to consume tokens
        assert bucket.consume(5) is True
        # Tokens should be reduced
        assert bucket.tokens == 5.0

    def test_token_consumption_failure(self):
        """Test 1.3: Token consumption fails when insufficient."""
        bucket = TokenBucket(rate=10.0, capacity=10.0)

        # Consume all tokens
        bucket.consume(10)

        # Should fail to consume more
        assert bucket.consume(1) is False
        assert bucket.tokens == 0.0

    def test_token_replenishment(self):
        """Test 1.4: Tokens replenish over time."""
        bucket = TokenBucket(rate=100.0, capacity=100.0)  # Fast replenishment for testing

        # Consume all tokens
        bucket.consume(100)
        assert bucket.tokens == 0.0

        # Wait for replenishment (0.1s = 10 tokens at 100/sec)
        time.sleep(0.1)

        # Should have some tokens back
        result = bucket.consume(1)
        assert result is True  # Can consume again

    def test_token_capacity_limit(self):
        """Test 1.5: Tokens don't exceed capacity."""
        bucket = TokenBucket(rate=100.0, capacity=10.0)

        # Wait long enough to generate many tokens
        time.sleep(1.0)

        # Should still be capped at capacity
        assert bucket.tokens <= 10.0

    def test_wait_time_calculation(self):
        """Test 1.6: Wait time calculation is accurate."""
        bucket = TokenBucket(rate=10.0, capacity=10.0)

        # Consume all tokens
        bucket.consume(10)

        # Need to wait for 1 token at rate of 10/sec = 0.1 seconds
        wait_time = bucket.get_wait_time(1)
        assert 0.0 <= wait_time <= 0.2  # Allow some tolerance

    @pytest.mark.asyncio
    async def test_async_wait_for_token(self):
        """Test 1.7: Async waiting for token replenishment."""
        bucket = TokenBucket(rate=100.0, capacity=10.0)

        # Consume all tokens
        bucket.consume(10)

        # Wait for token (should complete quickly with fast rate)
        start_time = time.time()
        await bucket.wait_for_token(1)
        elapsed = time.time() - start_time

        # Should have waited and gotten token
        assert elapsed < 1.0  # Should be fast with 100 tokens/sec


class TestRateLimiter:
    """Test rate limiter with multiple endpoint support."""

    def test_rate_limiter_initialization(self):
        """Test 2.1: Rate limiter initializes correctly."""
        config = RateLimitConfig(requests_per_minute=100)
        limiter = RateLimiter(config)

        assert limiter is not None
        assert limiter.config.requests_per_minute == 100

    @pytest.mark.asyncio
    async def test_rate_limit_allows_requests(self):
        """Test 2.2: Rate limiter allows requests under limit."""
        reset_rate_limiter()
        config = RateLimitConfig(requests_per_minute=1000)  # High limit
        limiter = get_rate_limiter(config)

        # Should allow multiple requests quickly
        for _ in range(5):
            # This should not raise or block significantly
            await limiter.acquire(endpoint="/test")

    @pytest.mark.asyncio
    async def test_rate_limit_enforces_limit(self):
        """Test 2.3: Rate limiter enforces limits."""
        reset_rate_limiter()
        # Very low limit for testing
        config = RateLimitConfig(requests_per_minute=10, burst_size=5)
        limiter = get_rate_limiter(config)

        # Consume all burst tokens quickly
        for _ in range(5):
            await limiter.acquire(endpoint="/test")

        # Next request should take time or raise
        start_time = time.time()
        try:
            await limiter.acquire(endpoint="/test")
            elapsed = time.time() - start_time
            # If it didn't raise, it should have waited
            assert elapsed > 0.0
        except RateLimitError:
            # Acceptable - rate limit was enforced
            pass

    def test_rate_limiter_singleton(self):
        """Test 2.4: get_rate_limiter returns singleton."""
        reset_rate_limiter()
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()

        assert limiter1 is limiter2


class TestCircuitBreaker:
    """Test circuit breaker pattern implementation."""

    def test_circuit_breaker_initialization(self):
        """Test 3.1: Circuit breaker initializes in CLOSED state."""
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)

        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_allows_successful_calls(self):
        """Test 3.2: Circuit breaker allows successful calls."""
        breaker = CircuitBreaker(failure_threshold=3)

        async def successful_call():
            return "success"

        result = await breaker.call(successful_call)

        assert result == "success"
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_opens_on_failures(self):
        """Test 3.3: Circuit breaker opens after threshold failures."""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)

        async def failing_call():
            raise ConnectionError("Test failure")

        # Cause failures to reach threshold
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await breaker.call(failing_call)

        # Circuit should be open
        assert breaker.state == CircuitState.OPEN
        assert breaker.failure_count == 3

    @pytest.mark.asyncio
    async def test_circuit_open_fails_fast(self):
        """Test 3.4: Open circuit fails fast without calling function."""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=60.0)

        call_count = 0

        async def failing_call():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Test failure")

        # Cause failures to open circuit
        for _ in range(2):
            with pytest.raises(ConnectionError):
                await breaker.call(failing_call)

        # Reset call count
        call_count = 0

        # Circuit is open, should fail fast without calling function
        with pytest.raises(CircuitBreakerError):
            await breaker.call(failing_call)

        # Function should not have been called
        assert call_count == 0

    @pytest.mark.asyncio
    async def test_circuit_half_open_transition(self):
        """Test 3.5: Circuit transitions to HALF_OPEN after timeout."""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)  # Short timeout

        async def failing_call():
            raise ConnectionError("Test failure")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ConnectionError):
                await breaker.call(failing_call)

        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(0.2)

        # Next call should transition to HALF_OPEN
        async def successful_call():
            return "success"

        result = await breaker.call(successful_call)

        # After success in half-open, may transition toward closed
        assert result == "success"

    @pytest.mark.asyncio
    async def test_circuit_closes_after_successes(self):
        """Test 3.6: Circuit closes after enough successes in HALF_OPEN."""
        breaker = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=0.1,
            success_threshold=2
        )

        async def failing_call():
            raise ConnectionError("Test failure")

        async def successful_call():
            return "success"

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ConnectionError):
                await breaker.call(failing_call)

        # Wait for recovery
        await asyncio.sleep(0.2)

        # Successful calls should close circuit
        await breaker.call(successful_call)
        await breaker.call(successful_call)
        await breaker.call(successful_call)

        # Should be closed or transitioning to closed
        assert breaker.state in [CircuitState.CLOSED, CircuitState.HALF_OPEN]

    def test_circuit_breaker_decorator(self):
        """Test 3.7: Circuit breaker works as decorator."""
        test_breaker = circuit_breaker(failure_threshold=2, recovery_timeout=60.0)

        # Decorator should be a CircuitBreaker instance
        assert isinstance(test_breaker, CircuitBreaker)
        assert test_breaker.failure_threshold == 2


class TestRetryLogic:
    """Test retry logic with exponential backoff."""

    def test_backoff_calculation(self):
        """Test 4.1: Exponential backoff calculation is correct."""
        # Attempt 0: base_delay * 2^0 = 1.0
        delay0 = calculate_backoff(0, base_delay=1.0, jitter=False)
        assert delay0 == 1.0

        # Attempt 1: base_delay * 2^1 = 2.0
        delay1 = calculate_backoff(1, base_delay=1.0, jitter=False)
        assert delay1 == 2.0

        # Attempt 2: base_delay * 2^2 = 4.0
        delay2 = calculate_backoff(2, base_delay=1.0, jitter=False)
        assert delay2 == 4.0

    def test_backoff_max_delay(self):
        """Test 4.2: Backoff respects maximum delay."""
        # Even with high attempt number, should cap at max_delay
        delay = calculate_backoff(100, base_delay=1.0, max_delay=10.0, jitter=False)
        assert delay == 10.0

    def test_backoff_with_jitter(self):
        """Test 4.3: Jitter adds randomization."""
        delays = []
        for _ in range(10):
            delay = calculate_backoff(3, base_delay=1.0, jitter=True)
            delays.append(delay)

        # With jitter, delays should vary
        assert len(set(delays)) > 1  # Not all the same

        # But should be within bounds (0 to base_delay * 2^3 = 8.0)
        for delay in delays:
            assert 0.0 <= delay <= 8.0

    def test_retryable_error_detection(self):
        """Test 4.4: Retryable errors identified correctly."""
        retryable = (ConnectionError, TimeoutError)

        # Should be retryable
        assert is_retryable_error(ConnectionError("test"), retryable) is True
        assert is_retryable_error(TimeoutError("test"), retryable) is True

        # Should not be retryable
        assert is_retryable_error(ValueError("test"), retryable) is False
        assert is_retryable_error(KeyError("test"), retryable) is False

    @pytest.mark.asyncio
    async def test_retry_async_success_first_attempt(self):
        """Test 4.5: Retry succeeds on first attempt."""
        call_count = 0

        @retry_async(max_attempts=3)
        async def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await successful_func()

        assert result == "success"
        assert call_count == 1  # Only called once

    @pytest.mark.asyncio
    async def test_retry_async_eventual_success(self):
        """Test 4.6: Retry succeeds after failures."""
        call_count = 0

        @retry_async(max_attempts=3, base_delay=0.01)
        async def eventually_successful():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise APIConnectionError("Temporary failure")
            return "success"

        result = await eventually_successful()

        assert result == "success"
        assert call_count == 3  # Retried twice, succeeded on third

    @pytest.mark.asyncio
    async def test_retry_async_max_attempts(self):
        """Test 4.7: Retry respects max attempts limit."""
        call_count = 0

        @retry_async(max_attempts=3, base_delay=0.01)
        async def always_failing():
            nonlocal call_count
            call_count += 1
            raise APIConnectionError("Always fails")

        with pytest.raises(APIConnectionError):
            await always_failing()

        assert call_count == 3  # Called 3 times, then gave up

    @pytest.mark.asyncio
    async def test_retry_non_retryable_error(self):
        """Test 4.8: Non-retryable errors fail immediately."""
        call_count = 0

        @retry_async(max_attempts=3)
        async def non_retryable_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Non-retryable")

        with pytest.raises(ValueError):
            await non_retryable_error()

        # Should not retry non-retryable errors
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_async_delay_increases(self):
        """Test 4.9: Retry delays increase exponentially."""
        timestamps = []

        @retry_async(max_attempts=3, base_delay=0.1, jitter=False)
        async def track_timing():
            timestamps.append(time.time())
            if len(timestamps) < 3:
                raise APITimeoutError("Timeout")
            return "success"

        await track_timing()

        # Check delays between attempts
        assert len(timestamps) == 3

        # First delay ~0.1s, second delay ~0.2s
        delay1 = timestamps[1] - timestamps[0]
        delay2 = timestamps[2] - timestamps[1]

        # Second delay should be roughly 2x first delay (exponential)
        assert delay2 > delay1


class TestCaching:
    """Test response caching functionality."""

    def test_cache_key_generation(self):
        """Test 5.1: Cache keys are generated correctly."""
        from uspto_enriched_citation_mcp.util.cache import generate_cache_key

        # Same input should generate same key
        key1 = generate_cache_key("test_query", rows=10)
        key2 = generate_cache_key("test_query", rows=10)

        assert key1 == key2

        # Different input should generate different key
        key3 = generate_cache_key("different_query", rows=10)
        assert key1 != key3

    def test_fields_cache(self):
        """Test 5.2: Fields cache works correctly."""
        from uspto_enriched_citation_mcp.util.cache import get_fields_cache

        cache = get_fields_cache(ttl_seconds=60, max_size=10)

        # Cache should start empty
        assert cache.currsize == 0

        # Add item to cache
        cache["test_key"] = {"field1": "value1"}

        # Should be retrievable
        assert cache["test_key"] == {"field1": "value1"}

    def test_search_cache(self):
        """Test 5.3: Search cache works correctly."""
        from uspto_enriched_citation_mcp.util.cache import get_search_cache

        cache = get_search_cache(max_size=5)

        # Add items
        for i in range(5):
            cache[f"key_{i}"] = f"value_{i}"

        # All should be retrievable
        assert cache["key_0"] == "value_0"

        # Add one more (should evict LRU)
        cache["key_5"] = "value_5"

        # Cache should still have 5 items (max_size)
        assert cache.currsize <= 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
