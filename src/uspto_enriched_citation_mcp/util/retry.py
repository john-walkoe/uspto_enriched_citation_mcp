"""
Retry logic with exponential backoff for transient failure handling.

Provides decorators and utilities for retrying failed operations with
intelligent backoff strategies.
"""

import asyncio
import random
from typing import Callable, Optional, Tuple, Type
from functools import wraps

from .logging import get_logger

logger = get_logger(__name__)


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

        retryable_exceptions = (
            APIConnectionError,
            APITimeoutError,
            APIUnavailableError,
            RateLimitError,
            ConnectionError,
            TimeoutError,
        )

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

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

                    # Check if we have attempts left
                    if attempt >= max_attempts - 1:
                        # Last attempt, raise the error
                        logger.error(
                            f"Max retry attempts ({max_attempts}) exceeded for {func.__name__}: "
                            f"{type(e).__name__}: {str(e)}"
                        )
                        raise

                    # Honor the upstream's own Retry-After when it gave one;
                    # our backoff is only a guess about when it will be ready.
                    upstream_delay = retry_after_seconds(e)
                    if upstream_delay is not None:
                        delay = min(upstream_delay, max_delay)
                    else:
                        delay = calculate_backoff(
                            attempt=attempt,
                            base_delay=base_delay,
                            max_delay=max_delay,
                            exponential_base=exponential_base,
                            jitter=jitter,
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
