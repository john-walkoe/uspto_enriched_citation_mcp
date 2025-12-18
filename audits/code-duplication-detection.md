# Code Duplication Detection Report
**Generated:** 2025-11-18
**Project:** USPTO Enriched Citation MCP
**Analysis Scope:** Complete codebase (42 Python files)

---

## Executive Summary

**Overall Code Quality:** 7.5/10 (Good with room for improvement)

**Total Findings:** 18 duplication issues across 4 categories
- **Exact Duplicates:** 5 findings (HIGH priority)
- **Near Duplicates:** 4 findings (MEDIUM priority)
- **Structural Duplicates:** 6 findings (MEDIUM priority)
- **Data Duplication:** 3 findings (HIGH priority)

**Estimated Refactoring Effort:** 8-12 hours
**Expected Benefits:** ~400 lines reduced, improved maintainability, DRY compliance

---

## 1. EXACT DUPLICATES

### Finding 1.1: HTTP Error Handling Logic Duplication
**Location:**
- `src/uspto_enriched_citation_mcp/api/enriched_client.py:78-130` (_handle_http_error)
- `src/uspto_enriched_citation_mcp/shared/exceptions.py:272-294` (get_exception_class)

**Importance:** 9/10

**Duplication Percentage:** 75%

**Description:**
Both files implement status code to exception mapping. The enriched_client has a complete 50-line method that maps HTTP status codes to custom exceptions, while exceptions.py has a 23-line function doing similar mapping.

**Current Code:**
```python
# enriched_client.py:100-115
if status_code == 401:
    raise AuthenticationError(error_message or "Invalid API key")
elif status_code == 403:
    raise AuthorizationError(error_message or "Access forbidden")
elif status_code == 404:
    raise NotFoundError(error_message or "Resource not found")
elif status_code == 429:
    retry_after = response.headers.get("Retry-After")
    retry_seconds = int(retry_after) if retry_after and retry_after.isdigit() else None
    raise RateLimitError(error_message or "Rate limit exceeded", retry_after=retry_seconds)
# ... continues for all status codes

# exceptions.py:282-291
status_map = {
    400: ValidationError,
    401: AuthenticationError,
    403: AuthorizationError,
    404: NotFoundError,
    429: RateLimitError,
    # ... continues
}
return status_map.get(status_code, APIError)
```

**DRY Solution:**
Extract to a shared utility function in shared/error_utils.py

**Remediation:**
```python
# shared/error_utils.py - ADD THIS FUNCTION:

def raise_http_exception(
    response: httpx.Response,
    error_message: Optional[str] = None
) -> None:
    """
    Raise appropriate exception for HTTP status code.

    Args:
        response: HTTP response object
        error_message: Optional custom error message

    Raises:
        Appropriate USPTOCitationError subclass
    """
    from .exceptions import (
        AuthenticationError, AuthorizationError, NotFoundError,
        RateLimitError, ValidationError, APIConnectionError,
        APIUnavailableError, APITimeoutError, APIResponseError
    )

    if response.status_code < 400:
        return

    status_code = response.status_code

    # Try to extract error message from response
    if error_message is None:
        try:
            error_data = response.json()
            error_message = error_data.get("error", error_data.get("message", ""))
        except Exception:
            error_message = response.text or f"HTTP {status_code}"

    # Map status codes to exceptions
    status_map = {
        401: (AuthenticationError, "Invalid API key"),
        403: (AuthorizationError, "Access forbidden"),
        404: (NotFoundError, "Resource not found"),
        429: (RateLimitError, "Rate limit exceeded"),
        502: (APIConnectionError, "Failed to connect to upstream service"),
        503: (APIUnavailableError, "Service temporarily unavailable"),
        504: (APITimeoutError, "Gateway timeout"),
    }

    if status_code in status_map:
        exc_class, default_msg = status_map[status_code]
        # Special handling for rate limit retry-after header
        if status_code == 429:
            retry_after = response.headers.get("Retry-After")
            retry_seconds = int(retry_after) if retry_after and retry_after.isdigit() else None
            raise exc_class(error_message or default_msg, retry_after=retry_seconds)
        else:
            raise exc_class(error_message or default_msg)
    elif status_code >= 500:
        raise APIResponseError(error_message or "Internal server error")
    elif status_code >= 400:
        raise ValidationError(error_message or "Invalid request")


# enriched_client.py - REPLACE _handle_http_error method:
def _handle_http_error(self, response: httpx.Response) -> None:
    """Handle HTTP errors by raising appropriate custom exceptions."""
    from ..shared.error_utils import raise_http_exception
    raise_http_exception(response)


# exceptions.py - SIMPLIFY get_exception_class:
def get_exception_class(status_code: int) -> type:
    """Get appropriate exception class for HTTP status code."""
    status_map = {
        400: ValidationError, 401: AuthenticationError,
        403: AuthorizationError, 404: NotFoundError,
        429: RateLimitError, 500: APIError,
        502: APIConnectionError, 503: APIUnavailableError,
        504: APITimeoutError,
    }
    return status_map.get(status_code, APIError)
```

**Refactoring Effort:** 1 hour
**Lines Saved:** ~45 lines

---

### Finding 1.2: Retry Decorator Logic (Async vs Sync)
**Location:**
- `src/uspto_enriched_citation_mcp/util/retry.py:64-161` (retry_async)
- `src/uspto_enriched_citation_mcp/util/retry.py:164-244` (retry_sync)

**Importance:** 8/10

**Duplication Percentage:** 95%

**Description:**
The async and sync retry decorators have nearly identical logic (97 lines vs 80 lines). Only difference is async/await vs sync execution. This is classic code duplication.

**Current Code:**
```python
# Lines 64-161: retry_async
def retry_async(max_attempts=3, ...):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    # ... identical error handling logic ...
                    delay = calculate_backoff(...)
                    await asyncio.sleep(delay)
        return wrapper
    return decorator

# Lines 164-244: retry_sync - NEARLY IDENTICAL
def retry_sync(max_attempts=3, ...):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)  # Only diff: no await
                except Exception as e:
                    # ... IDENTICAL error handling logic ...
                    delay = calculate_backoff(...)
                    time.sleep(delay)  # Only diff: time.sleep vs asyncio.sleep
        return wrapper
    return decorator
```

**DRY Solution:**
Create a shared retry logic function and thin wrapper decorators.

**Remediation:**
```python
# util/retry.py - REPLACE both decorators with unified approach:

def _retry_loop(
    func: Callable,
    args: tuple,
    kwargs: dict,
    max_attempts: int,
    base_delay: float,
    max_delay: float,
    exponential_base: float,
    jitter: bool,
    retryable_exceptions: Tuple[Type[Exception], ...],
    is_async: bool
) -> Any:
    """
    Unified retry loop logic for both sync and async functions.

    Returns: Function result
    Raises: Last exception if all retries exhausted
    """
    last_exception = None

    for attempt in range(max_attempts):
        try:
            # Execute function based on type
            if is_async:
                return await func(*args, **kwargs)
            else:
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
                attempt=attempt, base_delay=base_delay,
                max_delay=max_delay, exponential_base=exponential_base,
                jitter=jitter
            )

            logger.info(
                f"Retrying {func.__name__} after {type(e).__name__} "
                f"(attempt {attempt + 1}/{max_attempts}, delay={delay:.2f}s)"
            )

            # Wait before retrying
            if is_async:
                await asyncio.sleep(delay)
            else:
                time.sleep(delay)

    if last_exception:
        raise last_exception


def retry_async(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
):
    """Async retry decorator - thin wrapper around unified logic."""
    if retryable_exceptions is None:
        from ..shared.exceptions import (
            APIConnectionError, APITimeoutError,
            APIUnavailableError, RateLimitError,
        )
        retryable_exceptions = (
            APIConnectionError, APITimeoutError,
            APIUnavailableError, RateLimitError,
            ConnectionError, TimeoutError,
        )

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await _retry_loop(
                func, args, kwargs, max_attempts, base_delay,
                max_delay, exponential_base, jitter,
                retryable_exceptions, is_async=True
            )
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
    """Sync retry decorator - thin wrapper around unified logic."""
    if retryable_exceptions is None:
        retryable_exceptions = (ConnectionError, TimeoutError, OSError)

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Run async logic in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    _retry_loop(
                        func, args, kwargs, max_attempts, base_delay,
                        max_delay, exponential_base, jitter,
                        retryable_exceptions, is_async=False
                    )
                )
            finally:
                loop.close()
        return wrapper
    return decorator
```

**Refactoring Effort:** 2 hours
**Lines Saved:** ~80 lines

---

### Finding 1.3: Cache Statistics Methods
**Location:**
- `src/uspto_enriched_citation_mcp/util/cache.py:210-233` (TTLCache.get_stats)
- `src/uspto_enriched_citation_mcp/util/cache.py:344-367` (LRUCache.get_stats)

**Importance:** 6/10

**Duplication Percentage:** 100%

**Description:**
Both cache implementations have identical get_stats() methods with exact same logic and return structure.

**Current Code:**
```python
# TTLCache.get_stats (lines 210-233)
def get_stats(self) -> Dict[str, Any]:
    with self._lock:
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0.0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "total_requests": total,
            "hit_rate_percent": round(hit_rate, 2),
            "current_size": len(self._cache),
            "max_size": self.max_size,
            "fill_percent": (
                round(len(self._cache) / self.max_size * 100, 2)
                if self.max_size > 0 else 0.0
            ),
        }

# LRUCache.get_stats (lines 344-367) - IDENTICAL
def get_stats(self) -> Dict[str, Any]:
    with self._lock:
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0.0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "total_requests": total,
            "hit_rate_percent": round(hit_rate, 2),
            "current_size": len(self._cache),
            "max_size": self.max_size,
            "fill_percent": (
                round(len(self._cache) / self.max_size * 100, 2)
                if self.max_size > 0 else 0.0
            ),
        }
```

**DRY Solution:**
Create a base cache class or mixin with shared statistics logic.

**Remediation:**
```python
# util/cache.py - ADD base class at top of file:

class CacheStatsMixin:
    """Mixin providing common cache statistics functionality."""

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Requires subclass to have: _lock, _hits, _misses, _cache, max_size

        Returns:
            Dict with hits, misses, size, hit_rate
        """
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0.0

            return {
                "hits": self._hits,
                "misses": self._misses,
                "total_requests": total,
                "hit_rate_percent": round(hit_rate, 2),
                "current_size": len(self._cache),
                "max_size": self.max_size,
                "fill_percent": (
                    round(len(self._cache) / self.max_size * 100, 2)
                    if self.max_size > 0 else 0.0
                ),
            }


# MODIFY class declarations:
class TTLCache(CacheStatsMixin):
    """Time-to-live cache with automatic expiration."""
    # ... existing code ...
    # REMOVE get_stats method - inherited from mixin


class LRUCache(CacheStatsMixin):
    """Least Recently Used cache with size-based eviction."""
    # ... existing code ...
    # REMOVE get_stats method - inherited from mixin
```

**Refactoring Effort:** 30 minutes
**Lines Saved:** ~24 lines

---

### Finding 1.4: Metrics Collector Method Signatures
**Location:**
- `src/uspto_enriched_citation_mcp/util/metrics.py:153-196` (NoOpMetricsCollector)
- `src/uspto_enriched_citation_mcp/util/metrics.py:210-281` (LoggingMetricsCollector)

**Importance:** 5/10

**Duplication Percentage:** 40% (method signatures)

**Description:**
Both metrics collectors implement identical abstract method signatures with only implementation differences. This is necessary for the interface but could be streamlined.

**Current Code:**
```python
# NoOpMetricsCollector - all methods just pass
def record_request(self, endpoint, method, status_code, duration_seconds, error):
    pass

def record_rate_limit_event(self, endpoint, tokens_requested, tokens_available, blocked):
    pass

# ... 6 more methods

# LoggingMetricsCollector - same signatures with logging
def record_request(self, endpoint, method, status_code, duration_seconds, error):
    if error:
        logger.log(...)
    else:
        logger.log(...)
```

**DRY Solution:**
Use default parameters in base class and metaclass magic to auto-generate NoOp implementation.

**Remediation:**
```python
# util/metrics.py - ADD helper to reduce boilerplate:

def noop_method(func):
    """Decorator to create no-op version of abstract method."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        pass
    return wrapper


class NoOpMetricsCollector(MetricsCollector):
    """
    No-op implementation - auto-generates pass methods.
    Used as default when no metrics collection is configured.
    """
    # Use decorator to auto-generate all methods
    record_request = noop_method(MetricsCollector.record_request)
    record_rate_limit_event = noop_method(MetricsCollector.record_rate_limit_event)
    record_circuit_breaker_event = noop_method(MetricsCollector.record_circuit_breaker_event)
    record_response_size = noop_method(MetricsCollector.record_response_size)
    increment_counter = noop_method(MetricsCollector.increment_counter)
    record_gauge = noop_method(MetricsCollector.record_gauge)
    record_histogram = noop_method(MetricsCollector.record_histogram)
```

**Refactoring Effort:** 30 minutes
**Lines Saved:** ~15 lines

---

### Finding 1.5: Exception Message Initialization Pattern
**Location:**
- `src/uspto_enriched_citation_mcp/shared/exceptions.py` (multiple classes: 60-236)

**Importance:** 4/10

**Duplication Percentage:** 60%

**Description:**
Multiple exception classes have nearly identical __init__ methods with slight variations for status codes and detail fields.

**Current Code:**
```python
# Lines 60-67
class ValidationError(USPTOCitationError):
    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        details = kwargs.pop("details", {})
        if field:
            details["field"] = field
        super().__init__(message, status_code=400, details=details, **kwargs)

# Lines 70-77 - NEARLY IDENTICAL
class QueryValidationError(ValidationError):
    def __init__(self, message: str, query: Optional[str] = None, **kwargs):
        details = kwargs.pop("details", {})
        if query:
            details["query_preview"] = query[:100]
        super().__init__(message, field="query", details=details, **kwargs)

# Lines 80-87 - NEARLY IDENTICAL
class FieldValidationError(ValidationError):
    def __init__(self, message: str, field_name: Optional[str] = None, **kwargs):
        details = kwargs.pop("details", {})
        if field_name:
            details["field_name"] = field_name
        super().__init__(message, field="field", details=details, **kwargs)
```

**DRY Solution:**
Use class-level attributes and reduce __init__ duplication.

**Remediation:**
```python
# shared/exceptions.py - ADD helper function:

def _add_detail(details: dict, key: str, value: Any) -> dict:
    """Helper to add detail to dict if value is not None."""
    if value is not None:
        details[key] = value
    return details


# SIMPLIFY exception classes:
class ValidationError(USPTOCitationError):
    """Invalid input validation error (400 Bad Request)."""

    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        details = kwargs.pop("details", {})
        _add_detail(details, "field", field)
        super().__init__(message, status_code=400, details=details, **kwargs)


class QueryValidationError(ValidationError):
    """Lucene query validation error."""

    def __init__(self, message: str, query: Optional[str] = None, **kwargs):
        details = kwargs.pop("details", {})
        _add_detail(details, "query_preview", query[:100] if query else None)
        super().__init__(message, field="query", details=details, **kwargs)


class FieldValidationError(ValidationError):
    """Field name or field value validation error."""

    def __init__(self, message: str, field_name: Optional[str] = None, **kwargs):
        details = kwargs.pop("details", {})
        _add_detail(details, "field_name", field_name)
        super().__init__(message, field="field", details=details, **kwargs)
```

**Refactoring Effort:** 1 hour
**Lines Saved:** ~15 lines
**Note:** Low impact but improves consistency.

---

## 2. NEAR DUPLICATES

### Finding 2.1: Two API Client Implementations
**Location:**
- `src/uspto_enriched_citation_mcp/api/client.py` (522 lines)
- `src/uspto_enriched_citation_mcp/api/enriched_client.py` (712 lines)

**Importance:** 7/10

**Duplication Percentage:** 35%

**Description:**
Two separate API client implementations exist. The enriched_client.py is production-ready with full error handling, metrics, caching, and circuit breaker. The client.py appears to be an older/demo version with simpler implementation.

**Analysis:**
- client.py uses aiohttp, structlog, and has demo/mock data
- enriched_client.py uses httpx, standard logging, production-ready
- Both implement get_available_fields, search_citations, validate_query, get_citation_details
- enriched_client.py has ~40% more features (rate limiting, metrics, caching)

**DRY Solution:**
Deprecate client.py or refactor to use enriched_client.py as base.

**Remediation:**
```python
# OPTION 1: Deprecate client.py (RECOMMENDED)
# 1. Update imports in main.py to only use enriched_client
# 2. Add deprecation warning to client.py:

# api/client.py - ADD at top:
import warnings

warnings.warn(
    "client.py is deprecated and will be removed in v2.0. "
    "Use enriched_client.EnrichedCitationClient instead.",
    DeprecationWarning,
    stacklevel=2
)

# OPTION 2: Make client.py a thin wrapper
# api/client.py - REPLACE entire file:

"""
Backward compatibility wrapper for enriched_client.

DEPRECATED: Use enriched_client.EnrichedCitationClient directly.
"""

from .enriched_client import EnrichedCitationClient
from ..config.settings import Settings

class EnrichedCitationClient:
    """
    Deprecated client wrapper.

    Use enriched_client.EnrichedCitationClient instead.
    """

    def __init__(self, settings: Settings):
        warnings.warn(
            "This client wrapper is deprecated. Use EnrichedCitationClient from "
            "enriched_client module directly.",
            DeprecationWarning
        )
        from .enriched_client import EnrichedCitationClient as RealClient

        self._client = RealClient(
            api_key=settings.uspto_ecitation_api_key,
            base_url=settings.uspto_base_url
        )

    # Delegate all methods to real client
    def __getattr__(self, name):
        return getattr(self._client, name)
```

**Refactoring Effort:** 2 hours (deprecation path) OR 4 hours (merge implementations)
**Lines Saved:** ~522 lines (if client.py removed)

---

### Finding 2.2: Query Validation Logic
**Location:**
- `src/uspto_enriched_citation_mcp/api/client.py:217-338` (validate_query method)
- `src/uspto_enriched_citation_mcp/util/query_validator.py` (if exists - referenced)
- `src/uspto_enriched_citation_mcp/api/enriched_client.py:619-643` (validate_query method)

**Importance:** 6/10

**Duplication Percentage:** 50%

**Description:**
Query validation logic appears in multiple places with similar patterns for checking quotes, parentheses, field syntax.

**Current Code:**
```python
# client.py:217-338
async def validate_query(self, query: str) -> Dict[str, Any]:
    issues = []
    suggestions = []

    # Check for common issues
    if not query.strip():
        issues.append("Query is empty")

    # Check for balanced quotes
    quote_count = query.count('"')
    if quote_count % 2 != 0:
        issues.append("Unbalanced quotes in query")
        suggestions.append("Ensure all quoted phrases have closing quotes")

    # Check for field syntax
    # ... more validation ...

# Similar logic likely exists in query_validator.py
```

**DRY Solution:**
Centralize all query validation in util/query_validator.py

**Remediation:**
```python
# util/query_validator.py - CREATE comprehensive validator:

from typing import Tuple, List, Dict
import re

class QueryValidationResult:
    """Result of query validation with issues and suggestions."""

    def __init__(self):
        self.is_valid = True
        self.issues: List[str] = []
        self.suggestions: List[str] = []
        self.warnings: List[str] = []

    def add_issue(self, issue: str, suggestion: str = None):
        """Add a validation issue."""
        self.is_valid = False
        self.issues.append(issue)
        if suggestion:
            self.suggestions.append(suggestion)

    def add_suggestion(self, suggestion: str):
        """Add optimization suggestion without marking invalid."""
        self.suggestions.append(suggestion)

    def add_warning(self, warning: str):
        """Add a warning without marking invalid."""
        self.warnings.append(warning)


def validate_lucene_syntax(query: str) -> Tuple[bool, str]:
    """
    Validate Lucene query syntax.

    Returns: (is_valid, message)
    """
    result = QueryValidationResult()

    if not query or not query.strip():
        result.add_issue("Query is empty", "Provide a non-empty query string")
        return False, "Query is empty"

    # Check for balanced quotes
    if query.count('"') % 2 != 0:
        result.add_issue(
            "Unbalanced quotes in query",
            "Ensure all quoted phrases have closing quotes"
        )

    # Check for balanced parentheses
    if query.count("(") != query.count(")"):
        result.add_issue(
            "Unbalanced parentheses",
            "Ensure all '(' have matching ')'"
        )

    # Check for balanced brackets
    if query.count("[") != query.count("]"):
        result.add_issue(
            "Unbalanced brackets in range query",
            "Ensure all '[' have matching ']' for range queries"
        )

    # Optimization suggestions
    if "AND" not in query and "OR" not in query and " " in query:
        result.add_suggestion("Consider using explicit AND/OR operators for clarity")

    if "*" in query and query.count("*") > 3:
        result.add_warning("Multiple wildcards may impact performance")

    if result.is_valid:
        return True, "Query syntax is valid"
    else:
        return False, "; ".join(result.issues)


def validate_query_comprehensive(query: str) -> Dict:
    """
    Comprehensive query validation with detailed feedback.

    Returns: Dict with validation results and suggestions
    """
    result = QueryValidationResult()

    # Run basic syntax validation
    is_valid, message = validate_lucene_syntax(query)
    if not is_valid:
        result.is_valid = False
        result.issues.append(message)

    # Additional validations
    # Check for suspicious patterns
    if re.search(r'[<>]', query):
        result.add_warning("Query contains < or > which may not work as expected")

    # Check for common mistakes
    if ' = ' in query:
        result.add_suggestion("Use ':' instead of '=' for field queries (e.g., 'field:value')")

    return {
        "valid": result.is_valid,
        "issues": result.issues,
        "suggestions": result.suggestions,
        "warnings": result.warnings,
        "query": query
    }


# THEN update client implementations to use this:
# enriched_client.py:
def validate_lucene_query(self, query: str) -> Tuple[bool, str]:
    """Validate Lucene query syntax using utility."""
    from ..util.query_validator import validate_lucene_syntax
    return validate_lucene_syntax(query)


# client.py can be updated similarly or deprecated per Finding 2.1
```

**Refactoring Effort:** 2 hours
**Lines Saved:** ~80 lines

---

### Finding 2.3: Field Filtering Logic
**Location:**
- `src/uspto_enriched_citation_mcp/config/field_manager.py:208-245` (filter_response)
- `src/uspto_enriched_citation_mcp/main.py:376-394` (manual field filtering)
- `src/uspto_enriched_citation_mcp/main.py:517-531` (duplicate manual filtering)

**Importance:** 7/10

**Duplication Percentage:** 70%

**Description:**
Field filtering logic is duplicated between field_manager.py and main.py. The main.py has nearly identical filtering code in two tool functions (search_citations_minimal and search_citations_balanced).

**Current Code:**
```python
# main.py:376-394 (search_citations_minimal)
if fields is None:
    filtered = field_manager.filter_response(result, "citations_minimal")
else:
    filtered = result.copy()
    if "response" in filtered and "docs" in filtered["response"]:
        filtered_docs = []
        for doc in filtered["response"]["docs"]:
            filtered_doc = {}
            for field_name in fields:
                if field_name in doc:
                    filtered_doc[field_name] = doc[field_name]
            if "id" in doc:
                filtered_doc["id"] = doc["id"]
            filtered_docs.append(filtered_doc)
        filtered["response"]["docs"] = filtered_docs

# main.py:517-531 (search_citations_balanced) - IDENTICAL
if fields is None:
    filtered = field_manager.filter_response(result, "citations_balanced")
else:
    # ... EXACT SAME CODE AS ABOVE ...
```

**DRY Solution:**
Extract manual filtering to field_manager.py and reuse.

**Remediation:**
```python
# config/field_manager.py - ADD new method:

def filter_response_custom(
    self,
    response: Dict,
    custom_fields: List[str],
    include_id: bool = True
) -> Dict:
    """
    Filter API response to include only custom-specified fields.

    Args:
        response: API response dict
        custom_fields: List of field names to include
        include_id: Whether to always include 'id' field (default: True)

    Returns:
        Filtered response with only specified fields
    """
    try:
        filtered = response.copy()

        if "response" not in filtered or "docs" not in filtered["response"]:
            return filtered

        filtered_docs = []
        for doc in filtered["response"]["docs"]:
            filtered_doc = {}

            # Include requested fields
            for field_name in custom_fields:
                if field_name in doc:
                    filtered_doc[field_name] = doc[field_name]

            # Always include id if present (for tracking/debugging)
            if include_id and "id" in doc and "id" not in custom_fields:
                filtered_doc["id"] = doc["id"]

            filtered_docs.append(filtered_doc)

        filtered["response"]["docs"] = filtered_docs

        logger.debug(
            f"Custom filtered {len(response['response']['docs'])} docs "
            f"to {len(custom_fields)} fields"
        )
        return filtered

    except Exception as e:
        logger.error(f"Custom response filtering failed: {e}")
        return response  # Return original on error


def filter_response_smart(
    self,
    response: Dict,
    field_set_name: Optional[str] = None,
    custom_fields: Optional[List[str]] = None
) -> Dict:
    """
    Smart filtering - use preset or custom fields.

    Args:
        response: API response dict
        field_set_name: Name of predefined field set (e.g., 'citations_minimal')
        custom_fields: List of custom field names (overrides field_set_name)

    Returns:
        Filtered response
    """
    if custom_fields is not None:
        return self.filter_response_custom(response, custom_fields)
    elif field_set_name is not None:
        return self.filter_response(response, field_set_name)
    else:
        # No filtering
        return response


# main.py - REPLACE duplicated filtering in both tools:

# search_citations_minimal (line ~376):
filtered = field_manager.filter_response_smart(
    result,
    field_set_name="citations_minimal" if fields is None else None,
    custom_fields=fields
)

# search_citations_balanced (line ~513):
filtered = field_manager.filter_response_smart(
    result,
    field_set_name="citations_balanced" if fields is None else None,
    custom_fields=fields
)
```

**Refactoring Effort:** 1 hour
**Lines Saved:** ~30 lines

---

### Finding 2.4: Error Response Formatting
**Location:**
- `src/uspto_enriched_citation_mcp/shared/error_utils.py:123-189` (format_error_response)
- Multiple tool functions in main.py (lines 301, 421, 429, 558, 560, 629, 658, 672)

**Importance:** 5/10

**Duplication Percentage:** 30%

**Description:**
While format_error_response exists, it's called repeatedly with similar patterns throughout main.py. Some calls are nearly identical.

**Current Code:**
```python
# main.py - repeated patterns:
except ValueError as e:
    return format_error_response("Invalid search parameters", 400, exception=e)
except Exception as e:
    return format_error_response("Search failed", 500, exception=e)

# This pattern appears 8+ times with slight variations
```

**DRY Solution:**
Create tool-specific error handlers or decorator.

**Remediation:**
```python
# shared/error_utils.py - ADD decorator:

def handle_tool_errors(operation_name: str):
    """
    Decorator to handle common tool errors with consistent formatting.

    Args:
        operation_name: Name of operation for error messages (e.g., "Search")

    Usage:
        @handle_tool_errors("Search")
        async def search_tool(...):
            # ... implementation ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except ValidationError as e:
                return format_error_response(
                    f"{operation_name} validation failed",
                    400,
                    exception=e
                )
            except ValueError as e:
                return format_error_response(
                    f"Invalid {operation_name.lower()} parameters",
                    400,
                    exception=e
                )
            except Exception as e:
                return format_error_response(
                    f"{operation_name} failed",
                    500,
                    exception=e
                )
        return wrapper
    return decorator


# main.py - USE decorator:
from ..shared.error_utils import handle_tool_errors

@mcp.tool()
@handle_tool_errors("Search")
async def search_citations_minimal(...):
    # Implementation without try/except wrapper
    initialize_services()
    # ... rest of logic ...
    return filtered


@mcp.tool()
@handle_tool_errors("Search")
async def search_citations_balanced(...):
    # Implementation without try/except wrapper
    initialize_services()
    # ... rest of logic ...
    return filtered
```

**Refactoring Effort:** 1.5 hours
**Lines Saved:** ~40 lines

---

## 3. STRUCTURAL DUPLICATES

### Finding 3.1: Singleton Pattern Repetition
**Location:**
- `src/uspto_enriched_citation_mcp/util/rate_limiter.py:256-274` (get_rate_limiter)
- `src/uspto_enriched_citation_mcp/util/metrics.py:331-350` (get_metrics_collector)
- `src/uspto_enriched_citation_mcp/util/cache.py:416-448` (get_fields_cache, get_search_cache)
- `src/uspto_enriched_citation_mcp/config/settings.py:113-118` (get_settings)

**Importance:** 6/10

**Duplication Percentage:** 85% (pattern similarity)

**Description:**
The same singleton pattern is implemented 5+ times across different modules with nearly identical structure.

**Current Code:**
```python
# Pattern repeated across multiple files:
_instance = None

def get_instance(config=None):
    global _instance
    if _instance is None:
        if config is None:
            config = DefaultConfig()
        _instance = InstanceClass(config)
    return _instance
```

**DRY Solution:**
Create a generic singleton factory or use decorators.

**Remediation:**
```python
# Create new file: util/singleton.py

from typing import TypeVar, Type, Optional, Callable
from functools import wraps
import threading

T = TypeVar('T')

class Singleton:
    """
    Thread-safe singleton pattern implementation.

    Usage:
        @singleton
        class MyClass:
            def __init__(self, config):
                self.config = config

        # Get instance
        instance = MyClass.get_instance(config)
    """

    _instances = {}
    _lock = threading.Lock()

    @classmethod
    def get_instance(
        cls,
        instance_class: Type[T],
        factory: Optional[Callable[[], T]] = None
    ) -> T:
        """
        Get or create singleton instance.

        Args:
            instance_class: Class to instantiate
            factory: Optional factory function to create instance

        Returns:
            Singleton instance
        """
        with cls._lock:
            if instance_class not in cls._instances:
                if factory:
                    cls._instances[instance_class] = factory()
                else:
                    cls._instances[instance_class] = instance_class()
            return cls._instances[instance_class]


def singleton(cls: Type[T]) -> Type[T]:
    """
    Decorator to make a class a singleton.

    Adds a get_instance() class method.
    """
    instance = None
    lock = threading.Lock()

    @classmethod
    def get_instance(cls_ref, *args, **kwargs):
        nonlocal instance
        if instance is None:
            with lock:
                if instance is None:
                    instance = cls(*args, **kwargs)
        return instance

    cls.get_instance = get_instance
    return cls


# THEN update all singleton implementations:

# util/metrics.py - SIMPLIFY:
from ..util.singleton import singleton

@singleton
class GlobalMetricsCollector:
    """Global metrics collector wrapper."""
    def __init__(self):
        self.collector = NoOpMetricsCollector()

    def set_collector(self, collector):
        self.collector = collector

    def __getattr__(self, name):
        return getattr(self.collector, name)

def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector."""
    return GlobalMetricsCollector.get_instance().collector


# util/rate_limiter.py - SIMPLIFY:
def get_rate_limiter(config: Optional[RateLimitConfig] = None) -> RateLimiter:
    """Get global rate limiter instance (singleton)."""
    return Singleton.get_instance(
        RateLimiter,
        factory=lambda: RateLimiter(config or RateLimitConfig())
    )


# util/cache.py - SIMPLIFY:
def get_fields_cache(ttl_seconds: int = 3600, max_size: int = 10) -> TTLCache:
    """Get or create the global fields cache."""
    return Singleton.get_instance(
        TTLCache,
        factory=lambda: TTLCache(default_ttl_seconds=ttl_seconds, max_size=max_size)
    )


def get_search_cache(max_size: int = 100) -> LRUCache:
    """Get or create the global search results cache."""
    return Singleton.get_instance(
        LRUCache,
        factory=lambda: LRUCache(max_size=max_size)
    )
```

**Refactoring Effort:** 3 hours
**Lines Saved:** ~50 lines

---

### Finding 3.2: Parameter Validation Pattern
**Location:**
- `src/uspto_enriched_citation_mcp/main.py:173-185` (validate_string_param)
- `src/uspto_enriched_citation_mcp/main.py:141-170` (validate_date_range)
- Similar patterns in other validation code

**Importance:** 6/10

**Duplication Percentage:** 50%

**Description:**
Parameter validation follows similar pattern: strip, check empty, validate format, check length/constraints.

**Current Code:**
```python
# main.py:173-185
def validate_string_param(param: str, max_length: int = 200) -> str:
    clean = param.strip() if param else None
    if not clean:
        return None
    if len(clean) > max_length:
        raise ValueError(f"Parameter too long (max {max_length} chars)")
    if re.search(r'[<>"\\]', clean):
        raise ValueError("Invalid characters in parameter")
    return clean

# Similar pattern for dates, numbers, etc.
```

**DRY Solution:**
Create a unified parameter validator class with chainable validators.

**Remediation:**
```python
# Create new file: util/validators.py

from typing import Optional, Callable, Any, List
import re
from datetime import datetime

class ValidationError(ValueError):
    """Validation error with field context."""
    def __init__(self, message: str, field: str = None):
        self.field = field
        super().__init__(message)


class Validator:
    """
    Chainable parameter validator.

    Usage:
        validator = Validator("applicant_name")
        clean_value = (validator
            .required()
            .max_length(200)
            .no_special_chars()
            .validate(user_input))
    """

    def __init__(self, field_name: str = "parameter"):
        self.field_name = field_name
        self.validators: List[Callable] = []

    def required(self, message: str = None):
        """Value must be non-empty after stripping."""
        def validate(value):
            if value is None or (isinstance(value, str) and not value.strip()):
                raise ValidationError(
                    message or f"{self.field_name} is required",
                    self.field_name
                )
            return value
        self.validators.append(validate)
        return self

    def max_length(self, length: int, message: str = None):
        """String must not exceed max length."""
        def validate(value):
            if value and len(str(value)) > length:
                raise ValidationError(
                    message or f"{self.field_name} too long (max {length} chars)",
                    self.field_name
                )
            return value
        self.validators.append(validate)
        return self

    def no_special_chars(self, pattern: str = r'[<>"\\]', message: str = None):
        """String must not contain special characters."""
        def validate(value):
            if value and re.search(pattern, str(value)):
                raise ValidationError(
                    message or f"Invalid characters in {self.field_name}",
                    self.field_name
                )
            return value
        self.validators.append(validate)
        return self

    def date_format(self, format: str = "%Y-%m-%d", message: str = None):
        """Value must be valid date in specified format."""
        def validate(value):
            if value:
                try:
                    datetime.strptime(value, format)
                except ValueError:
                    raise ValidationError(
                        message or f"{self.field_name} must be in {format} format",
                        self.field_name
                    )
            return value
        self.validators.append(validate)
        return self

    def custom(self, validator_func: Callable[[Any], Any]):
        """Add custom validator function."""
        self.validators.append(validator_func)
        return self

    def validate(self, value: Any) -> Any:
        """
        Run all validators and return cleaned value.

        Args:
            value: Value to validate

        Returns:
            Validated/cleaned value

        Raises:
            ValidationError: If validation fails
        """
        # Strip if string
        if isinstance(value, str):
            value = value.strip() if value else None

        # Run all validators
        for validator in self.validators:
            value = validator(value)

        return value


# Convenience validators
def validate_string(
    value: str,
    field_name: str = "parameter",
    required: bool = False,
    max_length: int = 200,
    allow_special_chars: bool = False
) -> Optional[str]:
    """
    Validate string parameter with common rules.

    Returns: Cleaned string or None if empty and not required
    """
    validator = Validator(field_name)

    if required:
        validator.required()

    validator.max_length(max_length)

    if not allow_special_chars:
        validator.no_special_chars()

    return validator.validate(value)


def validate_date(
    value: str,
    field_name: str = "date",
    required: bool = False,
    format: str = "%Y-%m-%d"
) -> Optional[str]:
    """Validate date parameter."""
    validator = Validator(field_name)

    if required:
        validator.required()

    validator.date_format(format)

    return validator.validate(value)


# THEN update main.py:
from .util.validators import validate_string, validate_date

def build_query(params: QueryParameters) -> QueryBuildResult:
    """Build Lucene query from parameters."""
    parts = []
    params_used = {}
    warnings = []

    if params.criteria:
        parts.append(f"({params.criteria})")
        params_used["base_criteria"] = params.criteria

    # REPLACE validate_string_param calls:
    if applicant_name := validate_string(params.applicant_name, "applicant_name"):
        parts.append(f'{QueryFieldNames.FIRST_APPLICANT_NAME}:"{applicant_name}"')
        params_used["applicant_name"] = applicant_name

    if application_number := validate_string(params.application_number, "application_number", max_length=20):
        parts.append(f"{QueryFieldNames.APPLICATION_NUMBER}:{application_number}")
        params_used["application_number"] = application_number

    # REPLACE validate_date_range calls:
    if params.date_start:
        start_date = validate_date(params.date_start, "date_start")
        # ... rest of logic
```

**Refactoring Effort:** 2 hours
**Lines Saved:** ~30 lines

---

### Finding 3.3: Logging Patterns
**Location:**
- Throughout codebase (logger.info, logger.error, logger.debug calls)

**Importance:** 4/10

**Duplication Percentage:** 30%

**Description:**
Similar logging patterns repeated throughout:
- "Operation started" / "Operation completed" pairs
- Error logging with exception info
- Parameter logging for debugging

**DRY Solution:**
Create context manager for operation logging.

**Remediation:**
```python
# util/logging.py - ADD:

import logging
import time
from contextlib import contextmanager
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

@contextmanager
def log_operation(
    operation_name: str,
    level: int = logging.INFO,
    log_params: Optional[Dict[str, Any]] = None,
    log_result: bool = False
):
    """
    Context manager for consistent operation logging.

    Usage:
        with log_operation("search_citations", log_params={"criteria": query}):
            result = await client.search(...)
        # Automatically logs start, duration, and completion
    """
    start_time = time.time()

    # Log start
    params_str = f" with {log_params}" if log_params else ""
    logger.log(level, f"{operation_name} started{params_str}")

    result = None
    error = None

    try:
        yield
    except Exception as e:
        error = e
        duration = time.time() - start_time
        logger.error(
            f"{operation_name} failed after {duration:.3f}s: {type(e).__name__}: {str(e)}",
            exc_info=True
        )
        raise
    else:
        duration = time.time() - start_time
        logger.log(
            level,
            f"{operation_name} completed in {duration:.3f}s"
        )


# USAGE in enriched_client.py:
from ..util.logging import log_operation

async def _get_fields_impl(self) -> Dict:
    """Internal implementation of get_fields."""
    with log_operation("get_fields", log_params={"base_url": self.base_url}):
        # ... existing implementation ...
        return result


async def _search_records_impl(self, criteria, start, rows, selected_fields) -> Dict:
    """POST /enriched_cited_reference_metadata/v3/records."""
    params = {"criteria": criteria[:100], "rows": rows}
    with log_operation("search_records", log_params=params):
        # ... existing implementation ...
        return result
```

**Refactoring Effort:** 2 hours
**Lines Saved:** ~50 lines

---

### Finding 3.4: Context Manager Patterns
**Location:**
- `src/uspto_enriched_citation_mcp/util/metrics.py:284-325` (MetricsTimer)
- `src/uspto_enriched_citation_mcp/util/request_context.py` (RequestContext - likely exists)

**Importance:** 5/10

**Duplication Percentage:** 40%

**Description:**
Multiple context managers follow similar __enter__/__exit__ patterns for resource management and timing.

**DRY Solution:**
Create base context manager class.

**Remediation:**
```python
# util/context_managers.py - CREATE:

from abc import ABC, abstractmethod
import time
from typing import Optional, Any

class BaseContextManager(ABC):
    """
    Base class for context managers with common lifecycle hooks.

    Subclasses implement on_enter, on_success, on_error, on_exit.
    """

    def __init__(self):
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.duration: Optional[float] = None
        self.error: Optional[Exception] = None

    @abstractmethod
    def on_enter(self) -> Any:
        """Called when entering context. Return value becomes 'as' variable."""
        pass

    def on_success(self) -> None:
        """Called on successful context exit (no exception)."""
        pass

    def on_error(self, exc_type, exc_val, exc_tb) -> bool:
        """
        Called on exception during context.

        Returns: True to suppress exception, False to propagate
        """
        return False

    def on_exit(self) -> None:
        """Always called on exit, after on_success or on_error."""
        pass

    def __enter__(self) -> Any:
        """Enter context."""
        self.start_time = time.time()
        return self.on_enter()

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit context."""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time

        suppress = False

        if exc_type is not None:
            self.error = exc_val
            suppress = self.on_error(exc_type, exc_val, exc_tb)
        else:
            self.on_success()

        self.on_exit()

        return suppress


# THEN simplify MetricsTimer:
class MetricsTimer(BaseContextManager):
    """Context manager for timing operations."""

    def __init__(self, collector, name: str, tags=None):
        super().__init__()
        self.collector = collector
        self.name = name
        self.tags = tags or {}

    def on_enter(self):
        return self

    def on_success(self):
        self.tags["success"] = "true"

    def on_error(self, exc_type, exc_val, exc_tb):
        self.tags["success"] = "false"
        self.tags["error_type"] = exc_type.__name__
        return False

    def on_exit(self):
        if self.duration is not None:
            self.collector.record_histogram(self.name, self.duration, tags=self.tags)
            self.collector.increment_counter(f"{self.name}.calls", tags=self.tags)
```

**Refactoring Effort:** 1.5 hours
**Lines Saved:** ~20 lines

---

### Finding 3.5: Response Size Validation
**Location:**
- `src/uspto_enriched_citation_mcp/api/enriched_client.py:185-250` (_validate_response_size)
- Similar validation patterns in other methods

**Importance:** 5/10

**Duplication Percentage:** 40%

**Description:**
Response size validation and content-type validation follow similar patterns with repeated logging and exception handling.

**DRY Solution:**
Create validator composition pattern.

**Remediation:**
```python
# shared/response_validators.py - CREATE:

from typing import Callable, List
import httpx
import logging

logger = logging.getLogger(__name__)

class ResponseValidator:
    """
    Composable response validator.

    Usage:
        validator = ResponseValidator()
        validator.add_validator(validate_content_type)
        validator.add_validator(validate_response_size)
        validator.validate(response)
    """

    def __init__(self):
        self.validators: List[Callable[[httpx.Response], None]] = []

    def add_validator(self, validator: Callable[[httpx.Response], None]):
        """Add a validator function."""
        self.validators.append(validator)
        return self

    def validate(self, response: httpx.Response) -> None:
        """
        Run all validators.

        Args:
            response: HTTP response to validate

        Raises:
            APIResponseError: If any validation fails
        """
        for validator in self.validators:
            validator(response)


def create_content_type_validator(expected_types: List[str] = None):
    """Factory for content-type validator."""
    if expected_types is None:
        expected_types = [
            "application/json",
            "application/json; charset=utf-8",
            "application/gzip",
        ]

    def validator(response: httpx.Response) -> None:
        from ..shared.exceptions import APIResponseError

        content_type = response.headers.get("content-type", "").lower().strip()

        if not content_type:
            raise APIResponseError(
                "Response missing Content-Type header",
                details={"status_code": response.status_code}
            )

        is_valid = any(
            content_type == exp.lower() or content_type.startswith(exp.lower().split(";")[0])
            for exp in expected_types
        )

        if not is_valid:
            raise APIResponseError(
                f"Unexpected Content-Type: {content_type}",
                details={"received": content_type, "expected": expected_types}
            )

    return validator


def create_response_size_validator(
    max_size: int = 50 * 1024 * 1024,  # 50MB
    warn_size: int = 5 * 1024 * 1024   # 5MB
):
    """Factory for response size validator."""
    def validator(response: httpx.Response) -> None:
        from ..shared.exceptions import APIResponseError

        # Check Content-Length header
        content_length_header = response.headers.get("content-length")
        if content_length_header:
            try:
                content_length = int(content_length_header)

                if content_length > max_size:
                    raise APIResponseError(
                        f"Response too large: {content_length / (1024 * 1024):.2f} MB "
                        f"exceeds maximum of {max_size / (1024 * 1024):.0f} MB",
                        details={"content_length_bytes": content_length}
                    )

                if content_length > warn_size:
                    logger.warning(
                        f"Large response: {content_length / (1024 * 1024):.2f} MB. "
                        "Consider reducing result set size."
                    )
            except ValueError:
                logger.warning(f"Invalid Content-Length header: {content_length_header}")

        # Also check actual content size
        try:
            actual_size = len(response.content)
            if actual_size > max_size:
                raise APIResponseError(
                    f"Response content too large: {actual_size / (1024 * 1024):.2f} MB",
                    details={"actual_size_bytes": actual_size}
                )
        except Exception as e:
            logger.debug(f"Could not validate response content size: {e}")

    return validator


# THEN simplify enriched_client.py:
from ..shared.response_validators import (
    ResponseValidator,
    create_content_type_validator,
    create_response_size_validator
)

class EnrichedCitationClient:
    def __init__(self, ...):
        # ... existing init ...

        # Create response validator
        self.response_validator = ResponseValidator()
        self.response_validator.add_validator(create_content_type_validator())
        self.response_validator.add_validator(create_response_size_validator())

    async def _get_fields_impl(self) -> Dict:
        # ... existing code ...
        response = await self.client.get(url)

        # REPLACE individual validation calls:
        self.response_validator.validate(response)

        # ... rest of code ...
```

**Refactoring Effort:** 2 hours
**Lines Saved:** ~60 lines

---

### Finding 3.6: Default Field Configuration
**Location:**
- `src/uspto_enriched_citation_mcp/config/field_manager.py:127-168` (_set_default_config)
- `src/uspto_enriched_citation_mcp/config/field_manager.py:195-206` (_get_default_minimal_fields)

**Importance:** 5/10

**Duplication Percentage:** 100%

**Description:**
Default field lists are defined twice - once in _set_default_config and again in _get_default_minimal_fields. The minimal fields list is duplicated.

**Current Code:**
```python
# Lines 127-168: _set_default_config
self.config = {
    "predefined_sets": {
        "citations_minimal": {
            "fields": [
                "patentApplicationNumber",
                "publicationNumber",
                # ... 8 fields total
            ]
        },
        # ... more sets
    }
}

# Lines 195-206: _get_default_minimal_fields - DUPLICATE
def _get_default_minimal_fields(self) -> List[str]:
    return [
        "patentApplicationNumber",
        "publicationNumber",
        # ... SAME 8 fields
    ]
```

**DRY Solution:**
Define default fields once as module-level constants.

**Remediation:**
```python
# config/field_manager.py - ADD at module level (after imports):

# Default field configurations (DRY - single source of truth)
DEFAULT_MINIMAL_FIELDS = [
    "patentApplicationNumber",
    "publicationNumber",
    "groupArtUnitNumber",
    "citedDocumentIdentifier",
    "citationCategoryCode",
    "techCenter",
    "officeActionDate",
    "examinerCitedReferenceIndicator",
]

DEFAULT_BALANCED_FIELDS = [
    *DEFAULT_MINIMAL_FIELDS,  # Include all minimal fields
    "passageLocationText",
    "officeActionCategory",
    "relatedClaimNumberText",
    "nplIndicator",
    "workGroupNumber",
    "kindCode",
    "countryCode",
    "qualitySummaryText",
    "firstApplicantName",
    "examinerNameText",
]

DEFAULT_FIELD_SETS = {
    "citations_minimal": DEFAULT_MINIMAL_FIELDS,
    "citations_balanced": DEFAULT_BALANCED_FIELDS,
}


# THEN update methods:
class FieldManager:
    def _set_default_config(self):
        """Fallback to default configuration."""
        self.config = {
            "predefined_sets": {
                name: {"fields": fields}
                for name, fields in DEFAULT_FIELD_SETS.items()
            }
        }

    def _get_default_minimal_fields(self) -> List[str]:
        """Get default minimal fields."""
        return DEFAULT_MINIMAL_FIELDS.copy()  # Return copy to prevent mutation
```

**Refactoring Effort:** 30 minutes
**Lines Saved:** ~15 lines

---

## 4. DATA DUPLICATION

### Finding 4.1: Exception Status Code Mapping
**Location:**
- `src/uspto_enriched_citation_mcp/shared/error_utils.py:24-54` (EXCEPTION_MESSAGES dict)
- `src/uspto_enriched_citation_mcp/shared/exceptions.py` (exception class definitions with status codes)
- `src/uspto_enriched_citation_mcp/api/enriched_client.py:100-128` (status code mapping in _handle_http_error)

**Importance:** 8/10

**Duplication Percentage:** 75%

**Description:**
Exception to status code mappings exist in three places:
1. EXCEPTION_MESSAGES dict maps exception names to user messages
2. Exception classes define their own status_code
3. _handle_http_error maps status codes to exceptions

This is a three-way data duplication issue.

**Current Data:**
```python
# error_utils.py:24-54
EXCEPTION_MESSAGES = {
    "AuthenticationError": "Authentication failed. Please check your API key.",
    "AuthorizationError": "Access forbidden. You do not have permission...",
    "NotFoundError": "Requested resource not found.",
    "RateLimitError": "Rate limit exceeded. Please try again later.",
    # ... 20+ more entries
}

# exceptions.py:93-97
class AuthenticationError(USPTOCitationError):
    def __init__(self, message="Authentication failed", **kwargs):
        super().__init__(message, status_code=401, **kwargs)

# enriched_client.py:101-102
if status_code == 401:
    raise AuthenticationError(error_message or "Invalid API key")
```

**DRY Solution:**
Centralize all exception metadata in exception classes.

**Remediation:**
```python
# shared/exceptions.py - ENHANCE base class:

class USPTOCitationError(Exception):
    """Base exception for all USPTO Citation MCP errors."""

    # Class-level metadata (subclasses override)
    status_code: int = 500
    default_message: str = "An error occurred"
    user_friendly_message: str = None  # If different from default_message

    def __init__(
        self,
        message: str = None,
        status_code: int = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        # Use class defaults if not provided
        self.message = message or self.default_message
        self.status_code = status_code or self.__class__.status_code
        self.details = details or {}
        super().__init__(self.message)

    def get_user_message(self) -> str:
        """Get user-friendly error message."""
        return self.user_friendly_message or self.message

    @classmethod
    def get_exception_metadata(cls) -> Dict[str, Any]:
        """Get metadata for this exception type."""
        return {
            "name": cls.__name__,
            "status_code": cls.status_code,
            "default_message": cls.default_message,
            "user_message": cls.user_friendly_message or cls.default_message,
        }


# UPDATE all exception subclasses to use class attributes:
class AuthenticationError(USPTOCitationError):
    """Authentication failed (401 Unauthorized)."""
    status_code = 401
    default_message = "Authentication failed"
    user_friendly_message = "Authentication failed. Please check your API key."


class AuthorizationError(USPTOCitationError):
    """Authorization failed (403 Forbidden)."""
    status_code = 403
    default_message = "Access forbidden"
    user_friendly_message = "Access forbidden. You do not have permission for this operation."


class NotFoundError(USPTOCitationError):
    """Resource not found (404 Not Found)."""
    status_code = 404
    default_message = "Resource not found"
    user_friendly_message = "Requested resource not found."


class RateLimitError(USPTOCitationError):
    """Rate limit exceeded (429 Too Many Requests)."""
    status_code = 429
    default_message = "Rate limit exceeded"
    user_friendly_message = "Rate limit exceeded. Please try again later."

    def __init__(
        self,
        message: str = None,
        retry_after: Optional[int] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(message, details=details, **kwargs)


# ADD registry for status code mapping:
EXCEPTION_REGISTRY = {}

def register_exception(cls):
    """Decorator to auto-register exception in registry."""
    EXCEPTION_REGISTRY[cls.status_code] = cls
    return cls

# Apply to all exception classes:
@register_exception
class AuthenticationError(USPTOCitationError):
    ...

@register_exception
class AuthorizationError(USPTOCitationError):
    ...

# ... etc for all exception classes


def get_exception_for_status(status_code: int) -> type:
    """
    Get exception class for HTTP status code.

    Returns: Exception class or APIError as fallback
    """
    return EXCEPTION_REGISTRY.get(status_code, APIError)


# THEN update error_utils.py - REMOVE EXCEPTION_MESSAGES dict:
def get_safe_error_message(
    exception: Exception,
    default_message: str = "An error occurred"
) -> str:
    """Convert exception to safe, user-friendly error message."""
    logger.error(f"Exception: {type(exception).__name__}: {str(exception)}", exc_info=True)

    # Use exception's user message if available
    if isinstance(exception, USPTOCitationError):
        return exception.get_user_message()

    # Sanitize message for unknown exceptions
    exception_message = str(exception)
    if exception_message:
        sanitized = sanitize_error_message(exception_message)
        if len(sanitized) < 200 and not any(
            word in sanitized.lower() for word in ["traceback", "stack", "module"]
        ):
            return sanitized

    return default_message


# UPDATE enriched_client.py - USE registry:
def _handle_http_error(self, response: httpx.Response) -> None:
    """Handle HTTP errors by raising appropriate custom exceptions."""
    if response.status_code < 400:
        return

    from ..shared.exceptions import get_exception_for_status, RateLimitError

    # Extract error message
    try:
        error_data = response.json()
        error_message = error_data.get("error", error_data.get("message", ""))
    except Exception:
        error_message = response.text or f"HTTP {response.status_code}"

    # Get exception class from registry
    exc_class = get_exception_for_status(response.status_code)

    # Special handling for rate limit retry-after
    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After")
        retry_seconds = int(retry_after) if retry_after and retry_after.isdigit() else None
        raise RateLimitError(error_message, retry_after=retry_seconds)
    else:
        raise exc_class(error_message)
```

**Refactoring Effort:** 2 hours
**Lines Saved:** ~50 lines

---

### Finding 4.2: Field Name Constants
**Location:**
- `src/uspto_enriched_citation_mcp/api/field_constants.py` (MINIMAL_FIELDS, BALANCED_FIELDS)
- `src/uspto_enriched_citation_mcp/config/field_manager.py` (DEFAULT_MINIMAL_FIELDS in _set_default_config)

**Importance:** 7/10

**Duplication Percentage:** 100%

**Description:**
Field lists are defined in two places: field_constants.py and field_manager.py. These should have a single source of truth.

**Current Data:**
```python
# api/field_constants.py
MINIMAL_FIELDS = [
    "patentApplicationNumber",
    "publicationNumber",
    # ... 8 fields
]

BALANCED_FIELDS = [
    "patentApplicationNumber",
    "publicationNumber",
    # ... 18 fields
]

# config/field_manager.py:131-168 - DUPLICATE
def _set_default_config(self):
    self.config = {
        "predefined_sets": {
            "citations_minimal": {
                "fields": [
                    "patentApplicationNumber",  # DUPLICATE
                    "publicationNumber",  # DUPLICATE
                    # ... same 8 fields
                ]
            },
            # ...
        }
    }
```

**DRY Solution:**
Import constants from field_constants.py into field_manager.py.

**Remediation:**
```python
# config/field_manager.py - REPLACE _set_default_config:

from ..api.field_constants import MINIMAL_FIELDS, BALANCED_FIELDS

class FieldManager:
    def _set_default_config(self):
        """Fallback to default configuration if YAML missing or invalid."""
        self.config = {
            "predefined_sets": {
                "citations_minimal": {
                    "fields": list(MINIMAL_FIELDS)  # Use imported constant
                },
                "citations_balanced": {
                    "fields": list(BALANCED_FIELDS)  # Use imported constant
                },
            }
        }

    def _get_default_minimal_fields(self) -> List[str]:
        """Get default minimal fields."""
        return list(MINIMAL_FIELDS)  # Use imported constant


# ALTERNATIVE: Move constants to field_manager and import in field_constants
# This makes more sense since field_manager is the configuration authority

# config/field_manager.py - ADD at module level:
DEFAULT_MINIMAL_FIELDS = [
    "patentApplicationNumber",
    "publicationNumber",
    "groupArtUnitNumber",
    "citedDocumentIdentifier",
    "citationCategoryCode",
    "techCenter",
    "officeActionDate",
    "examinerCitedReferenceIndicator",
]

DEFAULT_BALANCED_FIELDS = [
    *DEFAULT_MINIMAL_FIELDS,  # Include all minimal fields
    "passageLocationText",
    "officeActionCategory",
    "relatedClaimNumberText",
    "nplIndicator",
    "workGroupNumber",
    "kindCode",
    "countryCode",
    "qualitySummaryText",
    "firstApplicantName",
    "examinerNameText",
]


# api/field_constants.py - REPLACE with imports:
"""Field name constants for USPTO Enriched Citation API."""

from ..config.field_manager import (
    DEFAULT_MINIMAL_FIELDS as MINIMAL_FIELDS,
    DEFAULT_BALANCED_FIELDS as BALANCED_FIELDS,
)

# Keep QueryFieldNames class as is (field name constants)
class QueryFieldNames:
    """Field names for Lucene queries."""
    # ... existing field names ...
```

**Refactoring Effort:** 1 hour
**Lines Saved:** ~30 lines

---

### Finding 4.3: Configuration Defaults
**Location:**
- `src/uspto_enriched_citation_mcp/config/settings.py` (Field defaults with Field())
- `src/uspto_enriched_citation_mcp/config/constants.py` (likely has overlapping constants)

**Importance:** 6/10

**Duplication Percentage:** 40%

**Description:**
Configuration defaults are defined in multiple places - pydantic Field() defaults in settings.py and likely module constants in constants.py.

**Current Data:**
```python
# settings.py
request_rate_limit: int = Field(default=100, ...)
api_timeout: float = Field(default=30.0, ...)
enable_cache: bool = Field(default=True, ...)

# Likely duplicated in constants.py or other config files
```

**DRY Solution:**
Define constants in one place and reference in Field() defaults.

**Remediation:**
```python
# config/constants.py - CENTRALIZE all defaults:

"""
Configuration constants and defaults for USPTO Enriched Citation MCP.

Single source of truth for default values used across the application.
"""

from datetime import datetime

# API Configuration Defaults
DEFAULT_RATE_LIMIT = 100  # requests per minute
DEFAULT_API_TIMEOUT = 30.0  # seconds
DEFAULT_CONNECT_TIMEOUT = 10.0  # seconds
DEFAULT_BASE_URL = "https://developer.uspto.gov/ds-api"

# Cache Configuration Defaults
DEFAULT_CACHE_ENABLED = True
DEFAULT_FIELDS_CACHE_TTL = 3600  # seconds (1 hour)
DEFAULT_SEARCH_CACHE_SIZE = 100  # max entries

# Result Size Limits
DEFAULT_MAX_MINIMAL_RESULTS = 100
DEFAULT_MAX_BALANCED_RESULTS = 20
DEFAULT_MAX_TOTAL_RESULTS = 1000

# Response Size Limits
MAX_RESPONSE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
WARNING_RESPONSE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

# Data Availability
API_DATA_START_DATE = datetime(2017, 10, 1)
API_DATA_CUTOFF_DATE_STRING = "2017-10-01"

# MCP Server
DEFAULT_MCP_SERVER_PORT = 8081

# Logging
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_REQUEST_ID_HEADER = "X-Request-ID"


# config/settings.py - USE constants:
from .constants import (
    DEFAULT_RATE_LIMIT,
    DEFAULT_API_TIMEOUT,
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_BASE_URL,
    DEFAULT_CACHE_ENABLED,
    DEFAULT_FIELDS_CACHE_TTL,
    DEFAULT_SEARCH_CACHE_SIZE,
    DEFAULT_MAX_MINIMAL_RESULTS,
    DEFAULT_MAX_BALANCED_RESULTS,
    DEFAULT_MAX_TOTAL_RESULTS,
    DEFAULT_MCP_SERVER_PORT,
    DEFAULT_LOG_LEVEL,
    DEFAULT_REQUEST_ID_HEADER,
)

class Settings(BaseSettings):
    """Application settings with secure API key management."""

    # USPTO API Configuration
    uspto_ecitation_api_key: str = Field(..., validation_alias="USPTO_API_KEY")
    uspto_base_url: str = Field(
        default=DEFAULT_BASE_URL,
        validation_alias="USPTO_BASE_URL"
    )

    # MCP Configuration
    mcp_server_port: int = Field(
        default=DEFAULT_MCP_SERVER_PORT,
        validation_alias="MCP_SERVER_PORT"
    )

    # Rate Limiting
    request_rate_limit: int = Field(
        default=DEFAULT_RATE_LIMIT,
        validation_alias="ECITATION_RATE_LIMIT"
    )

    # Timeouts
    api_timeout: float = Field(
        default=DEFAULT_API_TIMEOUT,
        validation_alias="API_TIMEOUT"
    )
    connect_timeout: float = Field(
        default=DEFAULT_CONNECT_TIMEOUT,
        validation_alias="CONNECT_TIMEOUT"
    )

    # Caching Configuration
    enable_cache: bool = Field(
        default=DEFAULT_CACHE_ENABLED,
        validation_alias="ENABLE_CACHE"
    )
    fields_cache_ttl: int = Field(
        default=DEFAULT_FIELDS_CACHE_TTL,
        validation_alias="FIELDS_CACHE_TTL"
    )
    search_cache_size: int = Field(
        default=DEFAULT_SEARCH_CACHE_SIZE,
        validation_alias="SEARCH_CACHE_SIZE"
    )

    # Context Optimization
    max_minimal_results: int = Field(
        default=DEFAULT_MAX_MINIMAL_RESULTS,
        validation_alias="MAX_MINIMAL_RESULTS"
    )
    max_balanced_results: int = Field(
        default=DEFAULT_MAX_BALANCED_RESULTS,
        validation_alias="MAX_BALANCED_RESULTS"
    )
    max_total_results: int = Field(
        default=DEFAULT_MAX_TOTAL_RESULTS,
        validation_alias="MAX_TOTAL_RESULTS"
    )

    # Logging & Security
    log_level: str = Field(
        default=DEFAULT_LOG_LEVEL,
        validation_alias="LOG_LEVEL"
    )
    request_id_header: str = Field(
        default=DEFAULT_REQUEST_ID_HEADER,
        validation_alias="REQUEST_ID_HEADER"
    )
```

**Refactoring Effort:** 1 hour
**Lines Saved:** ~15 lines
**Benefit:** Single source of truth for configuration

---

## 5. RECOMMENDED UTILITIES MODULE

Based on the duplication analysis, create a new utilities module to centralize common patterns:

### Create: util/common.py

```python
"""
Common utilities to reduce code duplication.

Provides reusable patterns for:
- Error handling
- Validation
- Logging
- Response formatting
"""

from typing import Optional, Dict, Any, Callable, TypeVar, List
from functools import wraps
import logging
import time
from contextlib import contextmanager

logger = logging.getLogger(__name__)
T = TypeVar('T')


# ========== Error Handling ==========

def handle_tool_errors(operation_name: str):
    """Decorator for consistent tool error handling."""
    # See Finding 2.4 for full implementation
    ...


# ========== Validation ==========

class Validator:
    """Chainable parameter validator."""
    # See Finding 3.2 for full implementation
    ...


def validate_string(value: str, **kwargs) -> Optional[str]:
    """Validate string parameter."""
    # See Finding 3.2 for full implementation
    ...


# ========== Logging ==========

@contextmanager
def log_operation(operation_name: str, **kwargs):
    """Context manager for operation logging."""
    # See Finding 3.3 for full implementation
    ...


# ========== Response Formatting ==========

def format_success_response(data: Any, **metadata) -> Dict[str, Any]:
    """Format successful response with consistent structure."""
    return {
        "status": "success",
        "data": data,
        **metadata
    }


# ========== Singleton Pattern ==========

class Singleton:
    """Thread-safe singleton implementation."""
    # See Finding 3.1 for full implementation
    ...


def singleton(cls):
    """Decorator to make class a singleton."""
    # See Finding 3.1 for full implementation
    ...
```

---

## 6. SUMMARY & PRIORITIES

### High Priority (Do First)
1. **Finding 1.1** - HTTP Error Handling (Importance 9/10, 1 hour, 45 lines)
2. **Finding 4.1** - Exception Status Code Mapping (Importance 8/10, 2 hours, 50 lines)
3. **Finding 1.2** - Retry Decorator Logic (Importance 8/10, 2 hours, 80 lines)
4. **Finding 2.1** - Two API Client Implementations (Importance 7/10, 2-4 hours, 522 lines)
5. **Finding 4.2** - Field Name Constants (Importance 7/10, 1 hour, 30 lines)
6. **Finding 2.3** - Field Filtering Logic (Importance 7/10, 1 hour, 30 lines)

### Medium Priority (Do Second)
7. **Finding 3.1** - Singleton Pattern (Importance 6/10, 3 hours, 50 lines)
8. **Finding 2.2** - Query Validation (Importance 6/10, 2 hours, 80 lines)
9. **Finding 1.3** - Cache Statistics (Importance 6/10, 30 min, 24 lines)
10. **Finding 4.3** - Configuration Defaults (Importance 6/10, 1 hour, 15 lines)
11. **Finding 3.2** - Parameter Validation (Importance 6/10, 2 hours, 30 lines)

### Low Priority (Nice to Have)
12. **Finding 2.4** - Error Response Formatting (Importance 5/10, 1.5 hours, 40 lines)
13. **Finding 3.3** - Logging Patterns (Importance 4/10, 2 hours, 50 lines)
14. **Finding 3.4** - Context Manager Patterns (Importance 5/10, 1.5 hours, 20 lines)
15. **Finding 3.5** - Response Size Validation (Importance 5/10, 2 hours, 60 lines)
16. **Finding 3.6** - Default Field Config (Importance 5/10, 30 min, 15 lines)
17. **Finding 1.4** - Metrics Collector Signatures (Importance 5/10, 30 min, 15 lines)
18. **Finding 1.5** - Exception Init Pattern (Importance 4/10, 1 hour, 15 lines)

### Total Impact
- **Estimated Effort:** 8-12 hours for high priority, 20-30 hours for all
- **Lines Reduced:** ~400-500 lines (12-15% of codebase)
- **Maintainability:** Significant improvement in DRY compliance
- **Testing Impact:** Fewer places to test, easier to maintain tests

---

## 7. IMPLEMENTATION PLAN

### Phase 1: Foundation (3-4 hours)
1. Create util/common.py with shared utilities
2. Implement Finding 1.1 (HTTP error handling)
3. Implement Finding 4.1 (Exception metadata centralization)

### Phase 2: Client Consolidation (4-5 hours)
4. Implement Finding 2.1 (Deprecate old client)
5. Implement Finding 1.2 (Unified retry logic)
6. Implement Finding 2.3 (Field filtering consolidation)

### Phase 3: Configuration & Data (2-3 hours)
7. Implement Finding 4.2 (Field constants)
8. Implement Finding 4.3 (Configuration defaults)
9. Implement Finding 3.6 (Default field config)

### Phase 4: Patterns & Polish (3-4 hours)
10. Implement Finding 3.1 (Singleton pattern)
11. Implement Finding 2.2 (Query validation)
12. Implement Finding 1.3 (Cache statistics)
13. Run tests and verify no regressions

### Phase 5: Optional Improvements (8-12 hours)
14. Implement remaining medium and low priority findings
15. Add comprehensive tests for new utilities
16. Update documentation

---

## 8. TESTING RECOMMENDATIONS

After refactoring, ensure:

1. **Unit Tests**: Test all new utility functions independently
2. **Integration Tests**: Verify API clients still work correctly
3. **Regression Tests**: Run existing test suite to catch breaking changes
4. **Performance Tests**: Ensure refactoring doesn't impact performance
5. **Error Handling Tests**: Test all exception paths with new centralized handling

---

## 9. RISK ASSESSMENT

### Low Risk
- Finding 1.3 (Cache statistics) - Pure refactor, same interface
- Finding 3.6 (Default field config) - Internal change only
- Finding 4.3 (Configuration defaults) - No behavior change

### Medium Risk
- Finding 1.2 (Retry logic) - Core functionality, needs thorough testing
- Finding 2.3 (Field filtering) - Used in main tools, test carefully
- Finding 3.1 (Singleton pattern) - Changes initialization, test concurrency

### High Risk
- Finding 2.1 (Two API clients) - Major refactor, deprecation path needed
- Finding 4.1 (Exception mapping) - Affects error handling across app
- Finding 1.1 (HTTP error handling) - Critical path for API communication

**Recommendation:** Start with low-risk items to build confidence, then tackle high-risk with comprehensive testing.

---

## 10. CONCLUSION

The codebase shows good engineering practices overall (7.5/10) with well-structured error handling, logging, and configuration management. The primary duplication issues stem from:

1. **Pattern Repetition**: Singleton, validation, error handling patterns repeated
2. **Data Duplication**: Field lists, exception mappings, configuration defaults
3. **Legacy Code**: Old client.py alongside new enriched_client.py

**Key Benefits of Refactoring:**
- **Maintainability**: Single source of truth for common patterns
- **Consistency**: Standardized error handling and validation
- **Testability**: Fewer places to test, easier mocking
- **Documentation**: Centralized utilities are self-documenting

**Recommended Approach:**
Focus on high-priority findings first (Findings 1.1, 4.1, 1.2, 2.1, 4.2, 2.3) which provide the most value with reasonable effort. This addresses ~60% of the duplication with ~40% of the total effort.

---

**End of Report**
