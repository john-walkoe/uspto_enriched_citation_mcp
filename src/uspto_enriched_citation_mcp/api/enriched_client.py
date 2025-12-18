import httpx
import logging
import time
from typing import Dict, List, Optional, Tuple, Union
from ..config.constants import MAX_RESPONSE_SIZE_BYTES, WARNING_RESPONSE_SIZE_BYTES
from ..util.query_validator import validate_lucene_syntax
from ..util.rate_limiter import get_rate_limiter, RateLimitConfig
from ..util.retry import retry_async
from ..util.metrics import get_metrics_collector, MetricsCollector
from ..util.cache import get_fields_cache, get_search_cache, generate_cache_key
from ..shared.circuit_breaker import uspto_api_breaker, CircuitBreakerError
from ..shared.enums import ContextLevel
from ..shared.exceptions import (
    RateLimitError,
    APIConnectionError,
    APITimeoutError,
    APIResponseError,
    ValidationError,
)

logger = logging.getLogger(__name__)


class EnrichedCitationClient:
    """
    Async HTTP client for USPTO Enriched Citation API v3.
    Handles GZIP compression, authentication, Lucene queries, and rate limiting.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://developer.uspto.gov/ds-api",
        rate_limit: int = 100,
        timeout: float = 30.0,
        metrics_collector: Optional[MetricsCollector] = None,
        enable_cache: bool = True,
        fields_cache_ttl: int = 3600,
        search_cache_size: int = 100,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=timeout,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )

        # Initialize rate limiter
        rate_config = RateLimitConfig(requests_per_minute=rate_limit)
        self.rate_limiter = get_rate_limiter(rate_config)

        # Initialize metrics collector (use global if not provided)
        self.metrics_collector = metrics_collector or get_metrics_collector()

        # Initialize caching (optional)
        self.enable_cache = enable_cache
        if enable_cache:
            self.fields_cache = get_fields_cache(
                ttl_seconds=fields_cache_ttl, max_size=10
            )
            self.search_cache = get_search_cache(max_size=search_cache_size)
            logger.info(
                f"Caching enabled (fields TTL: {fields_cache_ttl}s, search size: {search_cache_size})"
            )
        else:
            self.fields_cache = None
            self.search_cache = None
            logger.info("Caching disabled")

    def _handle_http_error(self, response: httpx.Response) -> None:
        """
        Handle HTTP errors by raising appropriate custom exceptions.

        Uses centralized raise_http_exception() from error_utils to avoid duplication.

        Args:
            response: HTTP response to check

        Raises:
            Appropriate custom exception based on status code
        """
        from ..shared.error_utils import raise_http_exception

        raise_http_exception(response)

    def _validate_content_type(
        self, response: httpx.Response, expected_types: Optional[List[str]] = None
    ) -> None:
        """
        Validate response content-type header to prevent content-type confusion attacks.

        Args:
            response: HTTP response to validate
            expected_types: List of acceptable content types (defaults to JSON types)

        Raises:
            APIResponseError: If content-type is missing or invalid
        """
        if expected_types is None:
            # Default expected types for USPTO API (JSON responses, possibly gzipped)
            expected_types = [
                "application/json",
                "application/json; charset=utf-8",
                "application/json;charset=utf-8",
                "application/gzip",
                "application/x-gzip",
            ]

        # Get content-type header (case-insensitive)
        content_type = response.headers.get("content-type", "").lower().strip()

        if not content_type:
            raise APIResponseError(
                "Response missing Content-Type header",
                details={"status_code": response.status_code},
            )

        # Check if content-type matches any expected type
        # Handle parameters like charset by checking prefix match
        is_valid = False
        for expected in expected_types:
            expected_lower = expected.lower()
            # Exact match or prefix match (handles charset parameters)
            if content_type == expected_lower or content_type.startswith(
                expected_lower.split(";")[0]
            ):
                is_valid = True
                break

        if not is_valid:
            raise APIResponseError(
                f"Unexpected Content-Type: {content_type}. Expected one of: {', '.join(expected_types)}",
                details={
                    "received_content_type": content_type,
                    "expected_types": expected_types,
                    "status_code": response.status_code,
                },
            )

    def _validate_response_size(self, response: httpx.Response) -> None:
        """
        Validate response size to prevent memory exhaustion and DoS attacks.

        Args:
            response: HTTP response to validate

        Raises:
            APIResponseError: If response size exceeds maximum limit
        """
        # Get content-length header if available
        content_length_header = response.headers.get("content-length")

        if content_length_header:
            try:
                content_length = int(content_length_header)

                # Check against maximum size (DoS protection)
                if content_length > MAX_RESPONSE_SIZE_BYTES:
                    raise APIResponseError(
                        f"Response too large: {content_length / (1024 * 1024):.2f} MB exceeds maximum of {MAX_RESPONSE_SIZE_BYTES / (1024 * 1024):.0f} MB",
                        details={
                            "content_length_bytes": content_length,
                            "max_allowed_bytes": MAX_RESPONSE_SIZE_BYTES,
                            "status_code": response.status_code,
                        },
                    )

                # Log warning for large responses
                if content_length > WARNING_RESPONSE_SIZE_BYTES:
                    logger.warning(
                        f"Large response received: {content_length / (1024 * 1024):.2f} MB. "
                        f"Consider reducing result set size or using pagination."
                    )

            except ValueError:
                # Invalid content-length header - log but don't fail
                logger.warning(
                    f"Invalid Content-Length header: {content_length_header}"
                )

        # Also check actual response content size (fallback if no header)
        # Note: This happens after download, so less effective for DoS prevention
        # but provides defense in depth
        try:
            actual_size = len(response.content)

            if actual_size > MAX_RESPONSE_SIZE_BYTES:
                raise APIResponseError(
                    f"Response content too large: {actual_size / (1024 * 1024):.2f} MB exceeds maximum of {MAX_RESPONSE_SIZE_BYTES / (1024 * 1024):.0f} MB",
                    details={
                        "actual_size_bytes": actual_size,
                        "max_allowed_bytes": MAX_RESPONSE_SIZE_BYTES,
                        "status_code": response.status_code,
                    },
                )

            if actual_size > WARNING_RESPONSE_SIZE_BYTES:
                logger.warning(
                    f"Large response content: {actual_size / (1024 * 1024):.2f} MB. "
                    f"Consider using pagination or reducing rows parameter."
                )

        except Exception as e:
            # Don't fail validation if we can't check content size
            logger.debug(f"Could not validate response content size: {e}")

    @uspto_api_breaker
    @retry_async(max_attempts=3, base_delay=1.0, max_delay=30.0)
    async def _get_fields_impl(self) -> Dict:
        """Internal implementation of get_fields with circuit breaker and retry protection."""
        # Check cache first
        cache_key = generate_cache_key("fields", self.base_url)
        if self.enable_cache and self.fields_cache:
            cached_result = self.fields_cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for fields: {cache_key}")
                return cached_result

        # Start timing for metrics
        start_time = time.time()
        endpoint = "get_fields"
        method = "GET"
        status_code = None
        error_type = None

        # Apply rate limiting
        if not await self.rate_limiter.acquire(endpoint=endpoint):
            raise RateLimitError("Rate limit exceeded. Please try again later.")

        try:
            url = f"{self.base_url}/enriched_cited_reference_metadata/v3/fields"
            response = await self.client.get(url)
            status_code = response.status_code

            # Handle HTTP errors with custom exceptions
            self._handle_http_error(response)

            # Validate content-type header (security)
            self._validate_content_type(response)

            # Validate response size (DoS protection)
            self._validate_response_size(response)

            # Record response size metrics
            try:
                response_size = len(response.content)
                self.metrics_collector.record_response_size(endpoint, response_size)
            except Exception:
                pass  # Don't fail on metrics errors

            # API returns GZIP, httpx decompresses automatically
            result = response.json()

            # Store in cache
            if self.enable_cache and self.fields_cache:
                self.fields_cache.set(cache_key, result)
                logger.debug(f"Cached fields result: {cache_key}")

            # Record successful request metrics
            duration = time.time() - start_time
            self.metrics_collector.record_request(
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                duration_seconds=duration,
            )

            return result

        except httpx.TimeoutException:
            error_type = "timeout"
            duration = time.time() - start_time
            self.metrics_collector.record_request(
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                duration_seconds=duration,
                error=error_type,
            )
            raise APITimeoutError(
                "Request timed out while fetching fields", timeout_seconds=30.0
            )

        except httpx.ConnectError:
            error_type = "connection_error"
            duration = time.time() - start_time
            self.metrics_collector.record_request(
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                duration_seconds=duration,
                error=error_type,
            )
            raise APIConnectionError("Failed to connect to USPTO API")

        except httpx.HTTPError as e:
            error_type = "http_error"
            duration = time.time() - start_time
            self.metrics_collector.record_request(
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                duration_seconds=duration,
                error=error_type,
            )
            # Catch any other HTTP errors
            raise APIResponseError(f"HTTP error occurred: {str(e)}")

        except Exception as e:
            # Catch any other unexpected errors and record metrics
            error_type = e.__class__.__name__
            duration = time.time() - start_time
            self.metrics_collector.record_request(
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                duration_seconds=duration,
                error=error_type,
            )
            raise

    async def get_fields(self) -> Dict:
        """GET /enriched_cited_reference_metadata/v3/fields - List all searchable fields.

        Protected by circuit breaker and automatically retries on transient failures.
        Cached with TTL for performance. Falls back to stale cache on circuit breaker open.
        """
        try:
            return await self._get_fields_impl()
        except CircuitBreakerError:
            # Circuit breaker is open - try to use stale cache for graceful degradation
            logger.warning("Circuit breaker open for get_fields, attempting fallback to stale cache")
            cache_key = generate_cache_key("fields", self.base_url)

            if self.enable_cache and self.fields_cache:
                cache_metadata = self.fields_cache.get_with_metadata(cache_key, allow_stale=True)
                if cache_metadata:
                    logger.info(
                        f"Returning stale cached fields (age: {cache_metadata['age_seconds']}s, "
                        f"hits: {cache_metadata['hit_count']})"
                    )
                    # Return with degraded status indicator
                    result = cache_metadata["value"]
                    result["_cache_status"] = {
                        "source": "stale_cache",
                        "is_stale": True,
                        "age_seconds": cache_metadata["age_seconds"],
                        "message": "Service temporarily unavailable - using cached data",
                        "circuit_breaker": "open"
                    }
                    return result

            # No cache available - raise the original error
            logger.error("Circuit breaker open and no stale cache available for get_fields")
            raise

    @uspto_api_breaker
    @retry_async(max_attempts=3, base_delay=1.0, max_delay=30.0)
    async def _search_records_impl(
        self,
        criteria: str,
        start: int = 0,
        rows: int = 50,
        selected_fields: Optional[List[str]] = None,
    ) -> Dict:
        """POST /enriched_cited_reference_metadata/v3/records - Search citations with field selection.

        Protected by circuit breaker and automatically retries on transient failures.
        Cached with LRU for performance.
        """
        # Check cache first
        cache_key = generate_cache_key(
            "search", criteria, start, rows, selected_fields=selected_fields
        )
        if self.enable_cache and self.search_cache:
            cached_result = self.search_cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for search: {cache_key[:100]}...")
                return cached_result

        # Start timing for metrics
        start_time = time.time()
        endpoint = "search_records"
        method = "POST"
        status_code = None
        error_type = None

        # Apply rate limiting
        if not await self.rate_limiter.acquire(endpoint=endpoint):
            raise RateLimitError("Rate limit exceeded. Please try again later.")

        # Input validation
        if not criteria.strip():
            raise ValidationError("Criteria cannot be empty", field="criteria")

        if rows > 1000:
            raise ValidationError("Maximum rows is 1000 per request", field="rows")

        try:
            url = f"{self.base_url}/enriched_cited_reference_metadata/v3/records"
            data = {
                "criteria": criteria,
                "start": str(start),
                "rows": str(rows),
            }
            if selected_fields:
                data["fl"] = ",".join(selected_fields)

            response = await self.client.post(url, data=data)
            status_code = response.status_code

            # Handle HTTP errors with custom exceptions
            self._handle_http_error(response)

            # Validate content-type header (security)
            self._validate_content_type(response)

            # Validate response size (DoS protection)
            self._validate_response_size(response)

            # Record response size metrics
            try:
                response_size = len(response.content)
                self.metrics_collector.record_response_size(endpoint, response_size)
            except Exception:
                pass  # Don't fail on metrics errors

            # Response is JSON in {"response": {"start": X, "numFound": Y, "docs": [...]}} format
            result = response.json()

            # Check for API-level errors in response body
            if "error" in result:
                raise APIResponseError(
                    f"API error: {result.get('error', 'Unknown error')}"
                )

            # Store in cache
            if self.enable_cache and self.search_cache:
                self.search_cache.set(cache_key, result)
                logger.debug(f"Cached search result: {cache_key[:100]}...")

            # Record successful request metrics
            duration = time.time() - start_time
            self.metrics_collector.record_request(
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                duration_seconds=duration,
            )

            return result

        except httpx.TimeoutException:
            error_type = "timeout"
            duration = time.time() - start_time
            self.metrics_collector.record_request(
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                duration_seconds=duration,
                error=error_type,
            )
            raise APITimeoutError("Search request timed out", timeout_seconds=30.0)

        except httpx.ConnectError:
            error_type = "connection_error"
            duration = time.time() - start_time
            self.metrics_collector.record_request(
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                duration_seconds=duration,
                error=error_type,
            )
            raise APIConnectionError("Failed to connect to USPTO API")

        except httpx.HTTPError as e:
            error_type = "http_error"
            duration = time.time() - start_time
            self.metrics_collector.record_request(
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                duration_seconds=duration,
                error=error_type,
            )
            # Catch any other HTTP errors not already handled
            raise APIResponseError(f"HTTP error occurred: {str(e)}")

        except Exception as e:
            # Catch any other unexpected errors and record metrics
            error_type = e.__class__.__name__
            duration = time.time() - start_time
            self.metrics_collector.record_request(
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                duration_seconds=duration,
                error=error_type,
            )
            raise

    async def search_records(
        self,
        criteria: str,
        start: int = 0,
        rows: int = 50,
        selected_fields: Optional[List[str]] = None,
    ) -> Dict:
        """POST /enriched_cited_reference_metadata/v3/records - Search citations with field selection.

        Protected by circuit breaker and automatically retries on transient failures.
        Cached with LRU for performance. Falls back to stale cache on circuit breaker open.
        """
        try:
            return await self._search_records_impl(criteria, start, rows, selected_fields)
        except CircuitBreakerError:
            # Circuit breaker is open - try to use stale cache for graceful degradation
            logger.warning(
                f"Circuit breaker open for search_records (criteria: {criteria[:50]}...), "
                "attempting fallback to stale cache"
            )
            cache_key = generate_cache_key(
                "search", criteria, start, rows, selected_fields=selected_fields
            )

            if self.enable_cache and self.search_cache:
                # LRUCache doesn't have expiration, so just try to get the value
                cached_result = self.search_cache.get(cache_key)
                if cached_result:
                    logger.info("Returning cached search results (circuit breaker open)")
                    # Add degraded status indicator
                    cached_result["_cache_status"] = {
                        "source": "cache",
                        "is_stale": False,  # LRU cache doesn't expire
                        "message": "Service temporarily unavailable - using cached results",
                        "circuit_breaker": "open"
                    }
                    return cached_result

            # No cache available - raise the original error
            logger.error(
                f"Circuit breaker open and no cache available for search_records "
                f"(criteria: {criteria[:50]}...)"
            )
            raise

    async def search_citations(
        self,
        criteria: str,
        fields: Optional[List[str]] = None,
        start: int = 0,
        rows: int = 50,
    ) -> Dict:
        """
        Search citations (alias for search_records with different parameter names).

        This method provides compatibility with code that expects 'fields' parameter
        instead of 'selected_fields'.

        Args:
            criteria: Lucene query string
            fields: List of field names to return (optional)
            start: Starting offset for pagination
            rows: Number of results to return

        Returns:
            Dict with search results in format: {"response": {"start": X, "numFound": Y, "docs": [...]}}
        """
        return await self.search_records(
            criteria=criteria, start=start, rows=rows, selected_fields=fields
        )

    def validate_lucene_query(self, query: str) -> Tuple[bool, str]:
        """Validate Lucene query syntax using utility."""
        return validate_lucene_syntax(query)

    async def validate_query(self, query: str) -> Dict:
        """
        Validate a Lucene query and return structured result.

        Args:
            query: The Lucene query string to validate

        Returns:
            Dict with validation results including valid, query, and optional error
        """
        is_valid, message = self.validate_lucene_query(query)

        if is_valid:
            return {
                "status": "success",
                "valid": True,
                "query": query,
                "message": message,
            }
        else:
            return {"status": "error", "valid": False, "query": query, "error": message}

    async def get_citation_details(
        self,
        citation_id: str,
        include_context: Union[bool, ContextLevel] = ContextLevel.FULL,
    ) -> Dict:
        """
        Get complete details for a specific citation by ID.

        Args:
            citation_id: The unique citation identifier
            include_context: Context inclusion level (ContextLevel.FULL or ContextLevel.MINIMAL)
                           For backward compatibility, also accepts bool (True=FULL, False=MINIMAL)

        Returns:
            Dict with citation details or error information
        """
        # Convert bool to ContextLevel for backward compatibility
        if isinstance(include_context, bool):
            context_level = ContextLevel.from_bool(include_context)
        else:
            context_level = include_context

        if not citation_id or not citation_id.strip():
            return {
                "status": "error",
                "error": "Citation ID is required",
                "citation_id": citation_id,
            }

        try:
            # Search for the specific citation by ID
            # Note: The actual field name for citation ID may vary - using common pattern
            criteria = f"id:{citation_id}"

            # Determine field selection based on context level
            selected_fields = None if context_level == ContextLevel.FULL else []

            # Get citation details with appropriate field selection
            result = await self.search_records(
                criteria=criteria, start=0, rows=1, selected_fields=selected_fields
            )

            docs = result.get("response", {}).get("docs", [])

            if not docs:
                return {
                    "status": "error",
                    "error": f"Citation not found: {citation_id}",
                    "citation_id": citation_id,
                }

            citation = docs[0]

            return {
                "status": "success",
                "citation_id": citation_id,
                "citation": citation,
                "context_level": context_level.value,
                "note": f"Citation record with {context_level.value} context level",
            }

        except Exception as e:
            return {"status": "error", "error": str(e), "citation_id": citation_id}

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
