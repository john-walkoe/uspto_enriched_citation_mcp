"""
Rate limiting with token bucket algorithm for API protection.

Prevents API abuse and DoS attacks by limiting request rates.
"""

import time
import asyncio
from typing import Optional, Dict
from dataclasses import dataclass
import threading


@dataclass
class RateLimitConfig:
    """Configuration for rate limiter."""

    requests_per_minute: int = 100  # Default from settings
    burst_size: Optional[int] = None  # Max burst (defaults to requests_per_minute)


class TokenBucket:
    """
    Token bucket rate limiter implementation.

    Allows bursts up to bucket capacity while maintaining average rate over time.
    Thread-safe for concurrent access.
    """

    def __init__(self, rate: float, capacity: Optional[float] = None):
        """
        Initialize token bucket.

        Args:
            rate: Tokens added per second
            capacity: Maximum tokens in bucket (defaults to rate)
        """
        self.rate = rate  # Tokens per second
        self.capacity = capacity if capacity is not None else rate
        self.tokens = self.capacity  # Start with full bucket
        self.last_update = time.monotonic()
        self.lock = threading.Lock()

    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens from bucket.

        Args:
            tokens: Number of tokens to consume (default: 1)

        Returns:
            True if tokens were available and consumed, False otherwise
        """
        with self.lock:
            now = time.monotonic()

            # Add tokens based on elapsed time
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now

            # Try to consume
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            else:
                return False

    def get_wait_time(self, tokens: int = 1) -> float:
        """
        Get time to wait until tokens are available.

        Args:
            tokens: Number of tokens needed

        Returns:
            Seconds to wait (0 if tokens available now)
        """
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            available_tokens = min(self.capacity, self.tokens + elapsed * self.rate)

            if available_tokens >= tokens:
                return 0.0

            # Calculate wait time
            needed_tokens = tokens - available_tokens
            wait_seconds = needed_tokens / self.rate
            return wait_seconds

    async def wait_for_token(self, tokens: int = 1) -> None:
        """
        Wait asynchronously until tokens are available, then consume them.

        Args:
            tokens: Number of tokens to wait for and consume
        """
        while not self.consume(tokens):
            wait_time = self.get_wait_time(tokens)
            if wait_time > 0:
                await asyncio.sleep(min(wait_time, 1.0))  # Sleep in 1s chunks


class RateLimiter:
    """
    Rate limiter with multiple buckets for different endpoints.

    Features:
    - Per-endpoint rate limiting
    - Token bucket algorithm
    - Burst handling
    - Security event logging
    """

    def __init__(self, config: RateLimitConfig):
        """
        Initialize rate limiter.

        Args:
            config: Rate limit configuration
        """
        self.config = config

        # Calculate tokens per second from requests per minute
        self.tokens_per_second = config.requests_per_minute / 60.0

        # Burst size (max tokens in bucket)
        self.burst_size = config.burst_size or config.requests_per_minute

        # Token buckets per endpoint
        self.buckets: Dict[str, TokenBucket] = {}
        self.global_bucket = TokenBucket(
            rate=self.tokens_per_second, capacity=self.burst_size
        )

        # Statistics
        self.total_requests = 0
        self.rejected_requests = 0

    def get_or_create_bucket(self, endpoint: str) -> TokenBucket:
        """
        Get or create token bucket for endpoint.

        Args:
            endpoint: Endpoint name

        Returns:
            Token bucket for the endpoint
        """
        if endpoint not in self.buckets:
            self.buckets[endpoint] = TokenBucket(
                rate=self.tokens_per_second, capacity=self.burst_size
            )
        return self.buckets[endpoint]

    async def acquire(self, endpoint: str = "default", tokens: int = 1) -> bool:
        """
        Try to acquire tokens (non-blocking).

        Args:
            endpoint: Endpoint name
            tokens: Number of tokens to acquire

        Returns:
            True if acquired, False if rate limit exceeded
        """
        self.total_requests += 1

        # Check global rate limit
        if not self.global_bucket.consume(tokens):
            self.rejected_requests += 1
            await self._log_rate_limit_exceeded("global", endpoint)
            return False

        # Check endpoint-specific rate limit
        bucket = self.get_or_create_bucket(endpoint)
        if not bucket.consume(tokens):
            self.rejected_requests += 1
            await self._log_rate_limit_exceeded("endpoint", endpoint)
            return False

        return True

    async def acquire_wait(self, endpoint: str = "default", tokens: int = 1) -> None:
        """
        Acquire tokens, waiting if necessary (blocking).

        Args:
            endpoint: Endpoint name
            tokens: Number of tokens to acquire
        """
        # Wait for global bucket
        await self.global_bucket.wait_for_token(tokens)

        # Wait for endpoint bucket
        bucket = self.get_or_create_bucket(endpoint)
        await bucket.wait_for_token(tokens)

        self.total_requests += 1

    async def _log_rate_limit_exceeded(self, limit_type: str, endpoint: str) -> None:
        """
        Log rate limit exceeded event.

        Args:
            limit_type: Type of limit exceeded ("global" or "endpoint")
            endpoint: Endpoint that exceeded limit
        """
        try:
            from .security_logger import get_security_logger

            logger = get_security_logger()
            logger.rate_limit_exceeded(
                limit=self.config.requests_per_minute,
                window="1m",
                endpoint=endpoint,
                limit_type=limit_type,
            )
        except Exception:
            pass  # Don't fail on logging errors

    def get_statistics(self) -> dict:
        """
        Get rate limiter statistics.

        Returns:
            Dict with statistics:
            {
                "total_requests": int,
                "rejected_requests": int,
                "rejection_rate": float,
                "active_endpoints": int
            }
        """
        rejection_rate = 0.0
        if self.total_requests > 0:
            rejection_rate = (self.rejected_requests / self.total_requests) * 100

        return {
            "total_requests": self.total_requests,
            "rejected_requests": self.rejected_requests,
            "rejection_rate": round(rejection_rate, 2),
            "active_endpoints": len(self.buckets),
            "config": {
                "requests_per_minute": self.config.requests_per_minute,
                "burst_size": self.burst_size,
            },
        }


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter(config: Optional[RateLimitConfig] = None) -> RateLimiter:
    """
    Get global rate limiter instance (singleton).

    Args:
        config: Optional configuration (only used on first call)

    Returns:
        RateLimiter instance
    """
    global _rate_limiter

    if _rate_limiter is None:
        if config is None:
            # Use default configuration
            config = RateLimitConfig()
        _rate_limiter = RateLimiter(config)

    return _rate_limiter


def reset_rate_limiter() -> None:
    """Reset global rate limiter (for testing)."""
    global _rate_limiter
    _rate_limiter = None
