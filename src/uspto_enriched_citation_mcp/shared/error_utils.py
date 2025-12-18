"""
Error handling utilities with security-conscious message sanitization.

Prevents information disclosure by mapping exceptions to safe, user-friendly messages
while preserving full details for internal logging.
"""

import re
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# Sensitive patterns to remove from error messages
SENSITIVE_PATTERNS = [
    (r"[A-Za-z]:\\[^:\s]+", "[PATH_REDACTED]"),  # Windows paths
    (r"/[^\s:]+/[^\s:]+", "[PATH_REDACTED]"),  # Unix paths
    (r"[a-z0-9]{28,40}", "[KEY_REDACTED]"),  # API keys (28-40 chars)
    (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "[IP_REDACTED]"),  # IP addresses
    (r"https?://[^\s]+", "[URL_REDACTED]"),  # URLs
    (r'password["\']?\s*[:=]\s*["\']?[^\s"\']+', "password=[REDACTED]"),  # Passwords
]

# Exception type to user-friendly message mapping
EXCEPTION_MESSAGES: Dict[str, str] = {
    # Network/Connection errors
    "ConnectionError": "Unable to connect to USPTO API. Please check your network connection.",
    "TimeoutError": "Request timed out. The USPTO API may be experiencing delays.",
    "HTTPError": "USPTO API returned an error. Please try again later.",
    # Custom exceptions
    "ValidationError": "Invalid request parameters. Please check your query syntax.",
    "QueryValidationError": "Invalid query syntax. Please check your Lucene query.",
    "FieldValidationError": "Invalid field name or value.",
    "AuthenticationError": "Authentication failed. Please check your API key.",
    "AuthorizationError": "Access forbidden. You do not have permission for this operation.",
    "NotFoundError": "Requested resource not found.",
    "CitationNotFoundError": "Citation not found in the database.",
    "RateLimitError": "Rate limit exceeded. Please try again later.",
    "APIError": "API error occurred. Please try again.",
    "APIConnectionError": "Failed to connect to USPTO API.",
    "APITimeoutError": "Request timed out. Please try again.",
    "APIUnavailableError": "USPTO API is temporarily unavailable.",
    "APIResponseError": "Invalid response from USPTO API.",
    "CircuitBreakerError": "Service temporarily unavailable. Please try again later.",
    "ConfigurationError": "System configuration error.",
    "SecurityError": "Security violation detected.",
    "InjectionAttemptError": "Invalid input detected.",
    # Standard Python exceptions
    "ValueError": "Invalid input value provided.",
    "KeyError": "Required field is missing from the response.",
    "JSONDecodeError": "Invalid response format from USPTO API.",
    "OSError": "System error occurred. Please contact support if this persists.",
    "RuntimeError": "Operation failed. Please try again.",
}


def sanitize_error_message(message: str) -> str:
    """
    Sanitize error message by removing sensitive information.

    Removes:
    - File paths
    - API keys
    - IP addresses
    - URLs
    - Passwords

    Args:
        message: Raw error message

    Returns:
        Sanitized error message safe for user display
    """
    sanitized = message

    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

    return sanitized


def get_safe_error_message(
    exception: Exception, default_message: str = "An error occurred"
) -> str:
    """
    Convert exception to safe, user-friendly error message.

    Maps known exception types to predefined messages and sanitizes
    any remaining details. Full exception details are logged internally.

    Args:
        exception: The exception to convert
        default_message: Fallback message if exception type is unknown

    Returns:
        Safe error message suitable for user display
    """
    exception_type = type(exception).__name__

    # Log full exception details internally (for debugging)
    logger.error(
        f"Exception occurred: {exception_type}: {str(exception)}", exc_info=True
    )

    # Check for known exception types
    if exception_type in EXCEPTION_MESSAGES:
        return EXCEPTION_MESSAGES[exception_type]

    # For unknown exceptions, sanitize the message
    exception_message = str(exception)
    if exception_message:
        sanitized = sanitize_error_message(exception_message)
        # Only return sanitized message if it's not too technical
        if len(sanitized) < 200 and not any(
            word in sanitized.lower() for word in ["traceback", "stack", "module"]
        ):
            return sanitized

    # Fall back to generic message
    return default_message


def raise_http_exception(response, error_message: Optional[str] = None) -> None:
    """
    Raise appropriate exception for HTTP status code.

    Centralized HTTP error handling to eliminate duplication between
    enriched_client and exceptions modules.

    Args:
        response: HTTP response object (httpx.Response)
        error_message: Optional custom error message

    Raises:
        Appropriate USPTOCitationError subclass based on status code
    """
    from .exceptions import (
        AuthenticationError,
        AuthorizationError,
        NotFoundError,
        RateLimitError,
        ValidationError,
        APIConnectionError,
        APIUnavailableError,
        APITimeoutError,
        APIResponseError,
    )

    # Return early if success status
    if response.status_code < 400:
        return

    status_code = response.status_code

    # Try to extract error message from response if not provided
    if error_message is None:
        try:
            error_data = response.json()
            error_message = error_data.get("error", error_data.get("message", ""))
        except Exception:
            error_message = response.text or f"HTTP {status_code}"

    # Map status codes to exceptions with default messages
    status_map = {
        401: (AuthenticationError, "Invalid API key"),
        403: (AuthorizationError, "Access forbidden"),
        404: (NotFoundError, "Resource not found"),
        429: (RateLimitError, "Rate limit exceeded"),
        502: (APIConnectionError, "Failed to connect to upstream service"),
        503: (APIUnavailableError, "Service temporarily unavailable"),
        504: (APITimeoutError, "Gateway timeout"),
    }

    # Handle specific status codes
    if status_code in status_map:
        exc_class, default_msg = status_map[status_code]

        # Special handling for rate limit retry-after header
        if status_code == 429:
            retry_after = response.headers.get("Retry-After")
            retry_seconds = (
                int(retry_after) if retry_after and retry_after.isdigit() else None
            )
            raise exc_class(error_message or default_msg, retry_after=retry_seconds)
        else:
            raise exc_class(error_message or default_msg)

    # Handle generic error ranges
    elif status_code >= 500:
        raise APIResponseError(error_message or "Internal server error")
    elif status_code >= 400:
        raise ValidationError(error_message or "Invalid request")


def format_error_response(
    message: str,
    code: int = 500,
    exception: Optional[Exception] = None,
    sanitize: bool = True,
) -> dict:
    """
    Format error response for MCP tools with optional sanitization.

    Automatically includes request ID if available for correlation.
    Uses custom exception system if exception is provided.

    Args:
        message: Error message prefix (e.g., "Search failed")
        code: HTTP status code
        exception: Optional exception to extract safe message from
        sanitize: Whether to sanitize the message (default True)

    Returns:
        Formatted error response dict with request_id if available
    """
    # Try to use custom exception system first
    if exception is not None:
        try:
            from .exceptions import USPTOCitationError, exception_to_response

            # If it's already our custom exception, use its to_dict method
            if isinstance(exception, USPTOCitationError):
                response = exception.to_dict()
            else:
                # Convert to response using exception_to_response
                response = exception_to_response(exception)
                # Prepend custom message if provided
                if message and message not in response.get("error", ""):
                    response["error"] = f"{message}: {response['error']}"
                    response["message"] = response["error"]
        except ImportError:
            # Fallback to old behavior if exceptions module not available
            safe_message = get_safe_error_message(exception, message)
            full_message = f"{message}: {safe_message}"
            response = {
                "status": "error",
                "error": full_message,
                "code": code,
                "message": full_message,
            }
    else:
        # Use provided message, sanitize if requested
        full_message = sanitize_error_message(message) if sanitize else message
        response = {
            "status": "error",
            "error": full_message,
            "code": code,
            "message": full_message,
        }

    # Add request ID if available (for correlation)
    try:
        from ..util.request_context import get_request_id

        request_id = get_request_id()
        if request_id:
            response["request_id"] = request_id
    except ImportError:
        pass  # Request context not available

    return response
