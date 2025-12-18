"""
Circuit breaker pattern implementation for API resilience.

Prevents cascade failures by temporarily disabling calls to failing services.
Based on standard circuit breaker pattern with configurable thresholds.
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Callable, Optional, TypeVar
from functools import wraps

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit is open, calls fail fast
    HALF_OPEN = "half_open"  # Testing if service has recovered


class CircuitBreakerError(Exception):
    """Circuit breaker is open."""

    pass


class CircuitBreaker:
    """
    Circuit breaker implementation for protecting against repeated failures.

    Features:
    - Failure threshold (default: 5 failures)
    - Recovery timeout (default: 60 seconds)
    - Success threshold for half-open state (default: 3 successes)
    - Async/sync compatibility
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 3,
        expected_exception: type = Exception,
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before trying half-open state
            success_threshold: Successes needed to close circuit from half-open
            expected_exception: Exception type that counts as failure
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.expected_exception = expected_exception

        # State tracking
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        return self._failure_count

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try half-open state."""
        if self._last_failure_time is None:
            return False

        return time.time() - self._last_failure_time >= self.recovery_timeout

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to call (can be sync or async)
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit is open
            Exception: Original exception from function call
        """
        async with self._lock:
            # Check if circuit is open
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    logger.info("Circuit breaker transitioning to HALF_OPEN")
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                else:
                    raise CircuitBreakerError("Circuit breaker is OPEN")

            # Check if we're in half-open and have exceeded success threshold
            if (
                self._state == CircuitState.HALF_OPEN
                and self._success_count >= self.success_threshold
            ):
                logger.info("Circuit breaker transitioning to CLOSED")
                self._state = CircuitState.CLOSED
                self._failure_count = 0

            try:
                # Execute function (handle both sync and async)
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                # Success - update state
                if self._state == CircuitState.HALF_OPEN:
                    self._success_count += 1
                    logger.debug(
                        f"Circuit breaker half-open success count: {self._success_count}"
                    )
                elif self._state == CircuitState.CLOSED:
                    self._failure_count = 0  # Reset failure count on success

                return result

            except self.expected_exception as e:
                # Failure - update state
                self._failure_count += 1
                self._last_failure_time = time.time()

                if self._state == CircuitState.HALF_OPEN:
                    logger.warning(
                        f"Circuit breaker reverting to OPEN (failure in half-open): {e}"
                    )
                    self._state = CircuitState.OPEN
                elif (
                    self._state == CircuitState.CLOSED
                    and self._failure_count >= self.failure_threshold
                ):
                    logger.warning(
                        f"Circuit breaker transitioning to OPEN (threshold reached): {e}"
                    )
                    self._state = CircuitState.OPEN

                raise  # Re-raise original exception

            except Exception as e:
                # Unexpected exception - also count as failure
                self._failure_count += 1
                self._last_failure_time = time.time()

                if self._state == CircuitState.HALF_OPEN:
                    logger.warning(
                        f"Circuit breaker reverting to OPEN (unexpected failure): {e}"
                    )
                    self._state = CircuitState.OPEN
                elif (
                    self._state == CircuitState.CLOSED
                    and self._failure_count >= self.failure_threshold
                ):
                    logger.warning(
                        f"Circuit breaker transitioning to OPEN (threshold reached): {e}"
                    )
                    self._state = CircuitState.OPEN

                raise  # Re-raise original exception

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator for use with @circuit_breaker."""

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await self.call(func, *args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, we need to run the async call in an event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            return loop.run_until_complete(self.call(func, *args, **kwargs))

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    success_threshold: int = 3,
    expected_exception: type = Exception,
) -> CircuitBreaker:
    """
    Create circuit breaker decorator with specified parameters.

    Args:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before trying half-open state
        success_threshold: Successes needed to close circuit
        expected_exception: Exception type that counts as failure

    Returns:
        CircuitBreaker instance for use as decorator

    Example:
        @circuit_breaker(failure_threshold=3, recovery_timeout=30)
        async def api_call():
            return await client.get("/endpoint")
    """
    return CircuitBreaker(
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        success_threshold=success_threshold,
        expected_exception=expected_exception,
    )


# Pre-configured circuit breaker for USPTO API calls
uspto_api_breaker = circuit_breaker(
    failure_threshold=3,
    recovery_timeout=30.0,
    success_threshold=2,
    expected_exception=(ConnectionError, TimeoutError, httpx.HTTPError),
)
