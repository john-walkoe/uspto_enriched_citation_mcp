"""
Custom exception hierarchy for USPTO Enriched Citation MCP.

Enables programmatic error handling with appropriate HTTP status codes
and user-friendly error messages.
"""

from typing import Optional, Dict, Any


class USPTOCitationError(Exception):
    """
    Base exception for all USPTO Citation MCP errors.

    All custom exceptions inherit from this class for easy catching.
    """

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize exception.

        Args:
            message: Error message
            status_code: HTTP status code (default: 500)
            details: Optional additional error details
        """
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict:
        """
        Convert exception to dictionary for error responses.

        Returns:
            Dict with status, error, code, and message fields
        """
        response = {
            "status": "error",
            "error": self.message,
            "code": self.status_code,
            "message": self.message,
        }

        if self.details:
            response["details"] = self.details

        return response


# === VALIDATION ERRORS (4xx) ===


class ValidationError(USPTOCitationError):
    """Invalid input validation error (400 Bad Request)."""

    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        details = kwargs.pop("details", {})
        if field:
            details["field"] = field
        super().__init__(message, status_code=400, details=details, **kwargs)


class QueryValidationError(ValidationError):
    """Lucene query validation error."""

    def __init__(self, message: str, query: Optional[str] = None, **kwargs):
        details = kwargs.pop("details", {})
        if query:
            details["query_preview"] = query[:100]
        super().__init__(message, field="query", details=details, **kwargs)


class FieldValidationError(ValidationError):
    """Field name or field value validation error."""

    def __init__(self, message: str, field_name: Optional[str] = None, **kwargs):
        details = kwargs.pop("details", {})
        if field_name:
            details["field_name"] = field_name
        super().__init__(message, field="field", details=details, **kwargs)


# === AUTHENTICATION/AUTHORIZATION ERRORS (401/403) ===


class AuthenticationError(USPTOCitationError):
    """Authentication failed (401 Unauthorized)."""

    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, status_code=401, **kwargs)


class AuthorizationError(USPTOCitationError):
    """Authorization failed (403 Forbidden)."""

    def __init__(self, message: str = "Access forbidden", **kwargs):
        super().__init__(message, status_code=403, **kwargs)


# === NOT FOUND ERRORS (404) ===


class NotFoundError(USPTOCitationError):
    """Resource not found (404 Not Found)."""

    def __init__(self, message: str = "Resource not found", **kwargs):
        super().__init__(message, status_code=404, **kwargs)


class CitationNotFoundError(NotFoundError):
    """Specific citation not found."""

    def __init__(self, citation_id: Optional[str] = None, **kwargs):
        if citation_id:
            message = f"Citation not found: {citation_id}"
            kwargs["details"] = kwargs.get("details", {})
            kwargs["details"]["citation_id"] = citation_id
        else:
            message = "Citation not found"
        super().__init__(message, **kwargs)


# === RATE LIMITING (429) ===


class RateLimitError(USPTOCitationError):
    """Rate limit exceeded (429 Too Many Requests)."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(message, status_code=429, details=details, **kwargs)


# === API/NETWORK ERRORS (5xx) ===


class APIError(USPTOCitationError):
    """Generic API error (500 Internal Server Error)."""

    def __init__(self, message: str = "API error occurred", **kwargs):
        super().__init__(message, status_code=500, **kwargs)


class APIConnectionError(APIError):
    """Failed to connect to API (502 Bad Gateway)."""

    def __init__(self, message: str = "Failed to connect to USPTO API", **kwargs):
        super().__init__(message, status_code=502, **kwargs)


class APITimeoutError(APIError):
    """API request timed out (504 Gateway Timeout)."""

    def __init__(
        self,
        message: str = "Request timed out",
        timeout_seconds: Optional[float] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        if timeout_seconds:
            details["timeout_seconds"] = timeout_seconds
        super().__init__(message, status_code=504, details=details, **kwargs)


class APIUnavailableError(APIError):
    """API service unavailable (503 Service Unavailable)."""

    def __init__(self, message: str = "USPTO API is temporarily unavailable", **kwargs):
        super().__init__(message, status_code=503, **kwargs)


class APIResponseError(APIError):
    """Invalid response from API (502 Bad Gateway)."""

    def __init__(self, message: str = "Invalid response from USPTO API", **kwargs):
        super().__init__(message, status_code=502, **kwargs)


# === CIRCUIT BREAKER ERRORS ===


class CircuitBreakerError(USPTOCitationError):
    """Circuit breaker is open (503 Service Unavailable)."""

    def __init__(
        self,
        message: str = "Service temporarily unavailable (circuit breaker open)",
        **kwargs,
    ):
        super().__init__(message, status_code=503, **kwargs)


# === CONFIGURATION ERRORS ===


class ConfigurationError(USPTOCitationError):
    """Configuration error (500 Internal Server Error)."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, status_code=500, **kwargs)


# === SECURITY ERRORS ===


class SecurityError(USPTOCitationError):
    """Security violation detected (403 Forbidden)."""

    def __init__(self, message: str, violation_type: Optional[str] = None, **kwargs):
        details = kwargs.pop("details", {})
        if violation_type:
            details["violation_type"] = violation_type
        super().__init__(message, status_code=403, details=details, **kwargs)


class InjectionAttemptError(SecurityError):
    """Injection attempt detected."""

    def __init__(self, message: str = "Injection attempt detected", **kwargs):
        super().__init__(message, violation_type="injection_attempt", **kwargs)


# === UTILITY FUNCTIONS ===


def exception_to_response(exc: Exception) -> dict:
    """
    Convert any exception to error response dict.

    Args:
        exc: Exception to convert

    Returns:
        Dict with error response format
    """
    if isinstance(exc, USPTOCitationError):
        return exc.to_dict()

    # Handle standard HTTP exceptions if they have status codes
    if hasattr(exc, "status_code"):
        return {
            "status": "error",
            "error": str(exc),
            "code": exc.status_code,
            "message": str(exc),
        }

    # Default to 500 for unknown exceptions
    return {
        "status": "error",
        "error": "Internal server error",
        "code": 500,
        "message": "An unexpected error occurred",
    }


def get_exception_class(status_code: int) -> type:
    """
    Get appropriate exception class for HTTP status code.

    Args:
        status_code: HTTP status code

    Returns:
        Exception class to use
    """
    status_map = {
        400: ValidationError,
        401: AuthenticationError,
        403: AuthorizationError,
        404: NotFoundError,
        429: RateLimitError,
        500: APIError,
        502: APIConnectionError,
        503: APIUnavailableError,
        504: APITimeoutError,
    }

    return status_map.get(status_code, APIError)
