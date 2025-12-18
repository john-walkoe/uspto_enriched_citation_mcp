"""
Request context management with UUID tracking for security and debugging.

Provides request ID generation and context propagation throughout the application
for:
- Security event correlation
- Incident response
- Debugging
- Audit trails
"""

import uuid
import contextvars
from typing import Optional
from datetime import datetime

# Context variable for request ID (thread-safe)
_request_id_context: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_id", default=None
)

# Context variable for request start time
_request_start_time: contextvars.ContextVar[Optional[datetime]] = (
    contextvars.ContextVar("request_start_time", default=None)
)


def generate_request_id() -> str:
    """
    Generate a new UUID4 request ID.

    Returns:
        UUID4 string (e.g., "550e8400-e29b-41d4-a716-446655440000")
    """
    return str(uuid.uuid4())


def set_request_id(request_id: Optional[str] = None) -> str:
    """
    Set the request ID for the current context.

    If no request_id is provided, generates a new one.

    Args:
        request_id: Optional request ID to set

    Returns:
        The request ID that was set
    """
    if request_id is None:
        request_id = generate_request_id()

    _request_id_context.set(request_id)
    _request_start_time.set(datetime.utcnow())

    return request_id


def get_request_id() -> Optional[str]:
    """
    Get the request ID for the current context.

    Returns:
        Request ID if set, None otherwise
    """
    return _request_id_context.get()


def get_request_duration_ms() -> Optional[float]:
    """
    Get the duration of the current request in milliseconds.

    Returns:
        Duration in milliseconds if request is active, None otherwise
    """
    start_time = _request_start_time.get()
    if start_time is None:
        return None

    duration = (datetime.utcnow() - start_time).total_seconds() * 1000
    return round(duration, 2)


def clear_request_context() -> None:
    """
    Clear the request context (request ID and start time).

    Should be called after request completion.
    """
    _request_id_context.set(None)
    _request_start_time.set(None)


class RequestContext:
    """
    Context manager for request ID tracking.

    Usage:
        with RequestContext() as request_id:
            # All operations within this block will have the same request_id
            logger.info(f"Processing request {request_id}")
    """

    def __init__(self, request_id: Optional[str] = None):
        """
        Initialize request context.

        Args:
            request_id: Optional request ID to use (generates new if None)
        """
        self.request_id = request_id
        self._previous_request_id: Optional[str] = None
        self._previous_start_time: Optional[datetime] = None

    def __enter__(self) -> str:
        """
        Enter request context, setting request ID.

        Returns:
            The request ID for this context
        """
        # Save previous context
        self._previous_request_id = _request_id_context.get()
        self._previous_start_time = _request_start_time.get()

        # Set new context
        self.request_id = set_request_id(self.request_id)

        return self.request_id

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit request context, restoring previous context.
        """
        # Restore previous context
        _request_id_context.set(self._previous_request_id)
        _request_start_time.set(self._previous_start_time)

        return False  # Don't suppress exceptions


def get_request_metadata() -> dict:
    """
    Get all request metadata (ID, duration, etc.).

    Returns:
        Dict with request metadata:
        {
            "request_id": str,
            "duration_ms": float,
            "timestamp": str (ISO format)
        }
    """
    request_id = get_request_id()
    duration_ms = get_request_duration_ms()
    start_time = _request_start_time.get()

    return {
        "request_id": request_id,
        "duration_ms": duration_ms,
        "timestamp": start_time.isoformat() if start_time else None,
    }
