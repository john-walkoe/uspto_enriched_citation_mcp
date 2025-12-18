"""
Retry logic with exponential backoff for transient failure handling.

Provides decorators and utilities for retrying failed operations with
intelligent backoff strategies.
"""

import asyncio
import random
import time
from typing import Callable, Optional, Tuple, Type
from functools import wraps
import logging

logger = logging.getLogger(__name__)


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

    # Add jitter (randomize between 0 and calculated delay)
    if jitter:
        delay = random.uniform(0, delay)

    return delay


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

                    # Calculate backoff delay
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


def retry_sync(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
):
    """
    Decorator for sync functions to retry on failure with exponential backoff.

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
        @retry_sync(max_attempts=3, base_delay=1.0)
        def fetch_data():
            return api.get_data()
    """
    if retryable_exceptions is None:
        retryable_exceptions = (ConnectionError, TimeoutError, OSError)

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)

                except Exception as e:
                    last_exception = e

                    # Check if error is retryable
                    if not is_retryable_error(e, retryable_exceptions):
                        logger.warning(
                            f"Non-retryable error in {func.__name__}: {type(e).__name__}: {str(e)}"
                        )
                        raise

                    # Check if we have attempts left
                    if attempt >= max_attempts - 1:
                        logger.error(
                            f"Max retry attempts ({max_attempts}) exceeded for {func.__name__}: "
                            f"{type(e).__name__}: {str(e)}"
                        )
                        raise

                    # Calculate backoff delay
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
                    time.sleep(delay)

            # This should never be reached, but just in case
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        """
        Initialize retry configuration.

        Args:
            max_attempts: Maximum number of attempts
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            exponential_base: Base for exponential growth
            jitter: Whether to add random jitter
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
