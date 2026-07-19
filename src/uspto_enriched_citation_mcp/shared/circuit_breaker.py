"""
Circuit breaker pattern implementation for API resilience.

Prevents cascade failures by temporarily disabling calls to failing services.
Based on standard circuit breaker pattern with configurable thresholds.
"""

import asyncio
import time
from enum import Enum
from typing import Callable, Dict, Optional, TypeVar
from functools import wraps

import httpx

from ..util.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit is open, calls fail fast
    HALF_OPEN = "half_open"  # Testing if service has recovered


class CircuitBreakerError(Exception):
    """Circuit breaker is open."""

    pass


def is_counted_failure(exc: BaseException) -> bool:
    """
    Classify whether an exception represents infrastructure-level
    unhealthiness that should count toward the circuit breaker's failure
    threshold.

    Counted (infrastructure signals — the upstream API itself is unhealthy):
        - timeouts / connection errors (raw httpx or builtin)
        - any 5xx-derived domain exception (APIConnectionError,
          APITimeoutError, APIUnavailableError, APIResponseError, ...)

    NOT counted (expected outcomes, not service-health signals):
        - 429 / RateLimitError — an expected backpressure response; heavy
          legitimate use must not open the circuit and block everyone
        - other 4xx domain exceptions (ValidationError, AuthenticationError,
          AuthorizationError, NotFoundError, ...) — repeated bad input from
          one caller must not open the circuit for everyone else

    Unrecognized exception types default to "counted" (conservative — an
    unexpected bug is still evidence something is wrong).
    """
    from .exceptions import RateLimitError, USPTOCitationError

    if isinstance(exc, RateLimitError):
        return False

    if isinstance(exc, USPTOCitationError):
        return exc.status_code >= 500

    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError)):
        return True

    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True

    return True


class CircuitBreaker:
    """
    Circuit breaker implementation for protecting against repeated failures.

    Features:
    - Failure threshold (default: 5 failures)
    - Recovery timeout (default: 60 seconds)
    - Success threshold for half-open state (default: 3 successes)
    - Async/sync compatibility
    - Only infrastructure failures (timeouts, connection errors, 5xx)
      count toward the failure threshold — see `is_counted_failure()`.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 3,
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before trying half-open state
            success_threshold: Successes needed to close circuit from half-open
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

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

    def _record_failure(self, e: BaseException) -> None:
        """Update state for a failure that counts toward the threshold."""
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
            except Exception as e:
                if not is_counted_failure(e):
                    # Expected outcome (4xx / 429 backpressure) — not a
                    # service-health signal, propagate without affecting
                    # breaker state so it can't block unrelated callers.
                    raise
                self._record_failure(e)
                raise  # Re-raise original exception

            # Success - update state
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                logger.debug(
                    f"Circuit breaker half-open success count: {self._success_count}"
                )
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0  # Reset failure count on success

            return result

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
) -> CircuitBreaker:
    """
    Create circuit breaker decorator with specified parameters.

    Args:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before trying half-open state
        success_threshold: Successes needed to close circuit

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
    )


# --- Per-API breaker registry (bulkhead isolation) -------------------------
#
# A single shared breaker across independent USPTO APIs means an outage in
# one API opens the circuit for the other. Each API gets its own named
# instance so failures stay isolated to the API that's actually unhealthy.
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 3,
    recovery_timeout: float = 30.0,
    success_threshold: int = 2,
) -> CircuitBreaker:
    """
    Get or create a named CircuitBreaker instance.

    Repeated calls with the same `name` return the same instance (a small
    per-name registry), so all clients for a given API share one breaker
    while remaining isolated from other APIs' breakers.

    Args:
        name: Unique name for this breaker (e.g. "enriched", "oa")
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before trying half-open state
        success_threshold: Successes needed to close circuit from half-open

    Returns:
        The named CircuitBreaker instance
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            success_threshold=success_threshold,
        )
    return _circuit_breakers[name]


def reset_circuit_breakers() -> None:
    """Clear the named-breaker registry. Test isolation helper."""
    _circuit_breakers.clear()
