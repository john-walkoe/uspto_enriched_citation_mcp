"""
Retry logic with exponential backoff for transient failure handling.

Provides decorators and utilities for retrying failed operations with
intelligent backoff strategies.

Rate limits are the exception to the backoff (ODP rate-limit wave,
2026-10-11, plan 2c / 4a): a RateLimitError is handled by WHERE it came from
(shared/exceptions.py RATE_LIMIT_SOURCE_*):

  upstream        USPTO answered 429. Wait max(5 s, Retry-After) and send ONCE
                  more, only when that wait is <= 10 s; otherwise raise at
                  once with details["retry_after"] = max(5, Retry-After).
                  Never a second retry, whatever max_attempts says. 5 s is
                  USPTO's own published floor for a retry after a 429.
  shared_limiter  the cross-process limiter gave no slot inside its ceiling
                  (SharedLimiterTimeoutError, mapped by the client). Raised
                  at once: a retry would only queue behind the same backlog.
  local_bucket    this process's own token bucket. Today's behaviour: sleep
                  the bucket's own interval (or the backoff), up to
                  max_attempts.

The builtin TimeoutError is NOT in the default retryable set: the shared
limiter's refusal is a TimeoutError subclass and must not be retried, and
no transport path raises a bare one (httpx timeouts are mapped to
APITimeoutError, which stays retryable).
"""

import asyncio
import random
from typing import Callable, Optional, Tuple, Type
from functools import wraps

from .logging import get_logger

logger = get_logger(__name__)

# The 429 rule's two numbers. Floor: USPTO says no retry within 5 s
# of a 429. Absorb ceiling: a single wait up to 10 s is held inside the tool
# call (no shared slot is held while sleeping); anything longer is handed back
# to the caller as the rate-limit envelope.
RATE_LIMIT_FLOOR_SECONDS = 5.0
RATE_LIMIT_ABSORB_CEILING_SECONDS = 10.0


def upstream_retry_after(retry_after: Optional[float]) -> float:
    """max(5 s, Retry-After): the wait an upstream 429 calls for."""
    try:
        value = float(retry_after) if retry_after is not None else 0.0
    except (TypeError, ValueError):
        value = 0.0
    return max(RATE_LIMIT_FLOOR_SECONDS, value)


def planned_429_wait(
    retry_after: Optional[float], already_retried: bool
) -> Optional[float]:
    """The one wait to absorb before the single retry of an upstream 429, or
    None when the caller must answer with the envelope instead: a second 429
    in the same call, or a wait above the absorb ceiling."""
    if already_retried:
        return None
    wait = upstream_retry_after(retry_after)
    if wait > RATE_LIMIT_ABSORB_CEILING_SECONDS:
        return None
    return wait


def calculate_backoff(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
) -> float:
    """
    Calculate backoff delay with exponential growth and optional jitter.

    Args:
        attempt: Attempt number (0-indexed)
        base_delay: Base delay in seconds (default: 1.0)
        max_delay: Maximum delay in seconds (default: 60.0)
        exponential_base: Base for exponential growth (default: 2.0)
        jitter: Whether to add random jitter (default: True)

    Returns:
        Delay in seconds
    """
    # Calculate exponential delay
    delay = min(base_delay * (exponential_base**attempt), max_delay)

    # Equal jitter, not full jitter: randomize between half and all of the
    # calculated delay. Full jitter drew from [0, delay], so the first retry
    # after a 429 could land at effectively zero seconds, which is the
    # behavior most likely to turn a soft upstream throttle into a hard one
    # on a key shared by four MCPs (R-4).
    if jitter:
        delay = random.uniform(delay / 2, delay)

    return delay


def retry_after_seconds(exception: Exception) -> Optional[float]:
    """The upstream's own Retry-After, if this exception carries one.

    raise_http_exception parses the header onto RateLimitError.details, and
    retry_async then ignored it and slept its own backoff instead, so a 429
    saying "wait 60 seconds" was retried in under a second, three times.
    """
    details = getattr(exception, "details", None)
    if not isinstance(details, dict):
        return None
    value = details.get("retry_after")
    if value is None:
        return None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    return seconds if seconds > 0 else None


def _is_rate_limit_from(exception: Exception, source: str) -> bool:
    """True when `exception` is a RateLimitError raised by `source`."""
    return getattr(exception, "status_code", None) == 429 and (
        getattr(exception, "source", None) == source
    )


def _retry_delay(
    exception: Exception,
    attempt: int,
    base_delay: float,
    max_delay: float,
    exponential_base: float,
    jitter: bool,
) -> float:
    """Honor the exception's own Retry-After when it carries one (a
    local-bucket rejection says when its next token is due); our backoff is
    only a guess about when the upstream will be ready."""
    own_delay = retry_after_seconds(exception)
    if own_delay is not None:
        return min(own_delay, max_delay)
    return calculate_backoff(
        attempt=attempt,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
    )


async def _absorb_rate_limit(
    exception: Exception, already_retried: bool, is_last_attempt: bool, name: str
) -> bool:
    """Apply the shared-limiter and upstream-429 rules to `exception`.

    Returns True after sleeping the one absorbed wait (the caller retries
    once more), False when the exception is not one of those two sources.
    Raises `exception` itself when the envelope is due: a shared-limiter
    refusal, a second 429, a Retry-After above the absorb ceiling, or no
    attempts left; the upstream envelope then carries
    details["retry_after"] = max(5, Retry-After).
    """
    if _is_rate_limit_from(exception, "shared_limiter"):
        logger.warning(f"Shared limiter refusal in {name}, answering at once")
        raise exception
    if not _is_rate_limit_from(exception, "upstream"):
        return False
    header = retry_after_seconds(exception)
    wait = planned_429_wait(header, already_retried)
    if wait is None or is_last_attempt:
        exception.details["retry_after"] = upstream_retry_after(header)
        logger.error(
            f"Upstream 429 in {name}, answering with the envelope "
            f"(retry_after={exception.details['retry_after']:.0f}s)"
        )
        raise exception
    logger.warning(f"Upstream 429 in {name}, one retry in {wait:.0f}s")
    await asyncio.sleep(wait)
    return True


def is_retryable_error(
    exception: Exception, retryable_exceptions: Tuple[Type[Exception], ...]
) -> bool:
    """
    Check if exception is retryable.

    Args:
        exception: Exception to check
        retryable_exceptions: Tuple of retryable exception types

    Returns:
        True if exception is retryable
    """
    return isinstance(exception, retryable_exceptions)


def retry_async(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
):
    """
    Decorator for async functions to retry on failure with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts (default: 3)
        base_delay: Base delay in seconds (default: 1.0)
        max_delay: Maximum delay in seconds (default: 60.0)
        exponential_base: Base for exponential growth (default: 2.0)
        jitter: Whether to add random jitter (default: True)
        retryable_exceptions: Tuple of exceptions to retry on (default: Exception)

    Returns:
        Decorated function with retry logic

    Example:
        @retry_async(max_attempts=3, base_delay=1.0)
        async def fetch_data():
            return await api.get_data()
    """
    if retryable_exceptions is None:
        # Default: retry on common transient errors
        from ..shared.exceptions import (
            APIConnectionError,
            APITimeoutError,
            APIUnavailableError,
            RateLimitError,
        )

        # The builtin TimeoutError is deliberately absent (module docstring).
        retryable_exceptions = (
            APIConnectionError,
            APITimeoutError,
            APIUnavailableError,
            RateLimitError,
            ConnectionError,
        )

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            retried_429 = False

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)

                except Exception as e:
                    last_exception = e

                    # Check if error is retryable
                    if not is_retryable_error(e, retryable_exceptions):
                        # Non-retryable error, raise immediately
                        logger.warning(
                            f"Non-retryable error in {func.__name__}: {type(e).__name__}: {str(e)}"
                        )
                        raise

                    # The rate-limit sources with their own rule (module
                    # docstring): raises when the envelope is due, sleeps and
                    # returns True for the one upstream retry, False when `e`
                    # is not one of them (a local-bucket rejection falls
                    # through to the backoff below, as before).
                    if await _absorb_rate_limit(
                        e, retried_429, attempt >= max_attempts - 1, func.__name__
                    ):
                        retried_429 = True
                        continue

                    # Check if we have attempts left
                    if attempt >= max_attempts - 1:
                        # Last attempt, raise the error
                        logger.error(
                            f"Max retry attempts ({max_attempts}) exceeded for {func.__name__}: "
                            f"{type(e).__name__}: {str(e)}"
                        )
                        raise

                    delay = _retry_delay(
                        e, attempt, base_delay, max_delay, exponential_base, jitter
                    )

                    logger.info(
                        f"Retrying {func.__name__} after {type(e).__name__} "
                        f"(attempt {attempt + 1}/{max_attempts}, delay={delay:.2f}s)"
                    )

                    # Wait before retrying
                    await asyncio.sleep(delay)

            # This should never be reached, but just in case
            if last_exception:
                raise last_exception

        return wrapper

    return decorator
