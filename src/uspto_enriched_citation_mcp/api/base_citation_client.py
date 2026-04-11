"""
Base HTTP client for USPTO citation APIs.

Provides shared transport, auth, caching, rate-limiting, circuit-breaker,
and error-handling logic. Concrete clients inherit and override only their
API-specific endpoints and field sets.
"""

import httpx
import time
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..util.cache import LRUCache, TTLCache
    from ..util.rate_limiter import RateLimiter

from ..config.constants import (
    MAX_RESPONSE_SIZE_BYTES,
    WARNING_RESPONSE_SIZE_BYTES,
)
from ..util.rate_limiter import get_rate_limiter, RateLimitConfig
from ..util.retry import retry_async
from ..util.metrics import get_metrics_collector, MetricsCollector
from ..util.cache import get_fields_cache, get_search_cache, generate_cache_key
from ..shared.circuit_breaker import uspto_api_breaker, CircuitBreakerError
from ..shared.exceptions import (
    RateLimitError,
    APIConnectionError,
    APITimeoutError,
    APIResponseError,
    ValidationError,
)
from ..util.logging import get_logger

logger = get_logger(__name__)


class BaseCitationClient:
    """
    Shared async HTTP client logic for USPTO ODP citation APIs.

    Subclasses must override:
        _FIELDS_PATH     — API path for the /fields endpoint
        _RECORDS_PATH    — API path for the /records endpoint
        _CACHE_KEY_PREFIX — prefix used in generate_cache_key() calls

    Subclasses may override __init__ to add API-specific parameters,
    but should call super().__init__() to initialise transport, metrics,
    caching, and rate-limiting.
    """

    _FIELDS_PATH: str = ""
    _RECORDS_PATH: str = ""
    _CACHE_KEY_PREFIX: str = ""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.uspto.gov",
        rate_limit: int = 100,
        timeout: float = 30.0,
        metrics_collector: Optional[MetricsCollector] = None,
        enable_cache: bool = True,
        fields_cache_ttl: int = 3600,
        search_cache_size: int = 100,
        # --- DIP: injectable dependencies (default to global singletons) ---
        rate_limiter: Optional["RateLimiter"] = None,
        fields_cache: Optional["TTLCache"] = None,
        search_cache: Optional["LRUCache"] = None,
    ):
        if not base_url.startswith("https://"):
            raise ValueError(f"USPTO base_url must use HTTPS. Got: {base_url}")

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

        self.client = httpx.AsyncClient(
            headers={
                "X-API-KEY": api_key,
                "Accept": "application/json",
            },
            timeout=timeout,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            verify=True,
        )

        # Rate limiter: injected, or fall back to global singleton
        if rate_limiter is not None:
            self.rate_limiter = rate_limiter
        else:
            rl_config = RateLimitConfig(requests_per_minute=rate_limit)
            self.rate_limiter = get_rate_limiter(rl_config)

        self.metrics_collector = metrics_collector or get_metrics_collector()

        self.enable_cache = enable_cache
        if enable_cache:
            # Caches: injected, or fall back to global singletons
            self.fields_cache = (
                fields_cache
                if fields_cache is not None
                else get_fields_cache(ttl_seconds=fields_cache_ttl, max_size=10)
            )
            self.search_cache = (
                search_cache
                if search_cache is not None
                else get_search_cache(max_size=search_cache_size)
            )
        else:
            self.fields_cache = None
            self.search_cache = None

    # ------------------------------------------------------------------
    # HTTP helpers (shared verbatim)
    # ------------------------------------------------------------------

    def _handle_http_error(self, response: httpx.Response) -> None:
        from ..shared.error_utils import raise_http_exception
        raise_http_exception(response)

    def _validate_content_type(
        self, response: httpx.Response, expected_types: Optional[List[str]] = None
    ) -> None:
        if expected_types is None:
            expected_types = [
                "application/json",
                "application/json; charset=utf-8",
                "application/json;charset=utf-8",
                "application/gzip",
                "application/x-gzip",
            ]
        content_type = response.headers.get("content-type", "").lower().strip()
        if not content_type:
            raise APIResponseError(
                "Response missing Content-Type header",
                details={"status_code": response.status_code},
            )
        is_valid = any(
            content_type == e.lower()
            or content_type.startswith(e.lower().split(";")[0])
            for e in expected_types
        )
        if not is_valid:
            raise APIResponseError(
                f"Unexpected Content-Type: {content_type}",
                details={
                    "received_content_type": content_type,
                    "status_code": response.status_code,
                },
            )

    def _validate_response_size(self, response: httpx.Response) -> None:
        content_length_header = response.headers.get("content-length")
        if content_length_header:
            try:
                content_length = int(content_length_header)
                if content_length > MAX_RESPONSE_SIZE_BYTES:
                    raise APIResponseError(
                        f"Response too large: {content_length / (1024*1024):.2f} MB",
                        details={"content_length_bytes": content_length},
                    )
                if content_length > WARNING_RESPONSE_SIZE_BYTES:
                    logger.warning(
                        f"Large response: {content_length / (1024*1024):.2f} MB"
                    )
            except ValueError:
                pass

        actual_size = len(response.content)
        if actual_size > MAX_RESPONSE_SIZE_BYTES:
            raise APIResponseError(
                f"Response too large: {actual_size / (1024*1024):.2f} MB",
                details={"actual_size_bytes": actual_size},
            )
        if actual_size > WARNING_RESPONSE_SIZE_BYTES:
            logger.warning(f"Large response content: {actual_size / (1024*1024):.2f} MB")

    # ------------------------------------------------------------------
    # Shared _get_fields_impl (subclass controls the cache-key prefix via
    # self._CACHE_KEY_PREFIX and the endpoint URL via self._FIELDS_PATH)
    # ------------------------------------------------------------------

    @uspto_api_breaker
    @retry_async(max_attempts=3, base_delay=1.0, max_delay=30.0)
    async def _get_fields_impl(self) -> Dict:
        cache_key = generate_cache_key(
            f"{self._CACHE_KEY_PREFIX}_fields", self.base_url
        )
        if self.enable_cache and self.fields_cache:
            cached = self.fields_cache.get(cache_key)
            if cached is not None:
                return cached

        start_time = time.time()
        endpoint = f"{self._CACHE_KEY_PREFIX}_get_fields"
        if not await self.rate_limiter.acquire(endpoint=endpoint):
            raise RateLimitError("Rate limit exceeded.")

        try:
            url = f"{self.base_url}{self._FIELDS_PATH}"
            response = await self.client.get(url)
            self._handle_http_error(response)
            self._validate_content_type(response)
            self._validate_response_size(response)
            result = response.json()
            if self.enable_cache and self.fields_cache:
                self.fields_cache.set(cache_key, result)
            self.metrics_collector.record_request(
                endpoint=endpoint,
                method="GET",
                status_code=response.status_code,
                duration_seconds=time.time() - start_time,
            )
            return result
        except httpx.TimeoutException:
            raise APITimeoutError(
                "Request timed out while fetching fields", timeout_seconds=30.0
            )
        except httpx.ConnectError:
            raise APIConnectionError("Failed to connect to USPTO API")
        except httpx.HTTPError as e:
            raise APIResponseError(f"HTTP error: {str(e)}")

    async def get_fields(self) -> Dict:
        """GET fields list with circuit breaker + stale-cache fallback."""
        try:
            return await self._get_fields_impl()
        except CircuitBreakerError:
            logger.warning(
                "Circuit breaker open for get_fields, attempting stale cache fallback"
            )
            cache_key = generate_cache_key(
                f"{self._CACHE_KEY_PREFIX}_fields", self.base_url
            )
            if self.enable_cache and self.fields_cache:
                meta = self.fields_cache.get_with_metadata(
                    cache_key, allow_stale=True
                )
                if meta:
                    result = meta["value"]
                    result["_cache_status"] = {
                        "source": "stale_cache",
                        "circuit_breaker": "open",
                    }
                    return result
            raise

    # ------------------------------------------------------------------
    # Shared _search_records_impl (subclass controls endpoint via
    # self._RECORDS_PATH and cache-key prefix via self._CACHE_KEY_PREFIX)
    # ------------------------------------------------------------------

    @uspto_api_breaker
    @retry_async(max_attempts=3, base_delay=1.0, max_delay=30.0)
    async def _search_records_impl(
        self,
        criteria: str,
        start: int = 0,
        rows: int = 50,
        selected_fields: Optional[List[str]] = None,
    ) -> Dict:
        cache_key = generate_cache_key(
            f"{self._CACHE_KEY_PREFIX}_search",
            criteria, start, rows,
            selected_fields=selected_fields,
        )
        if self.enable_cache and self.search_cache:
            cached = self.search_cache.get(cache_key)
            if cached is not None:
                return cached

        start_time = time.time()
        endpoint = f"{self._CACHE_KEY_PREFIX}_search_records"
        if not await self.rate_limiter.acquire(endpoint=endpoint):
            raise RateLimitError("Rate limit exceeded.")

        if not criteria.strip():
            raise ValidationError("Criteria cannot be empty", field="criteria")
        if rows > 1000:
            raise ValidationError("Maximum rows is 1000 per request", field="rows")

        try:
            url = f"{self.base_url}{self._RECORDS_PATH}"
            data = {
                "criteria": criteria,
                "start": str(start),
                "rows": str(rows),
            }
            if selected_fields:
                data["fl"] = ",".join(selected_fields)

            response = await self.client.post(url, data=data)
            self._handle_http_error(response)
            self._validate_content_type(response)
            self._validate_response_size(response)
            result = response.json()

            if "error" in result:
                raise APIResponseError(
                    f"API error: {result.get('error', 'Unknown error')}"
                )

            if self.enable_cache and self.search_cache:
                self.search_cache.set(cache_key, result)

            self.metrics_collector.record_request(
                endpoint=endpoint,
                method="POST",
                status_code=response.status_code,
                duration_seconds=time.time() - start_time,
            )
            return result

        except httpx.TimeoutException:
            raise APITimeoutError("Search request timed out", timeout_seconds=30.0)
        except httpx.ConnectError:
            raise APIConnectionError("Failed to connect to USPTO API")
        except httpx.HTTPError as e:
            raise APIResponseError(f"HTTP error: {str(e)}")

    async def search_records(
        self,
        criteria: str,
        start: int = 0,
        rows: int = 50,
        selected_fields: Optional[List[str]] = None,
    ) -> Dict:
        """Search with circuit breaker + cache fallback."""
        try:
            return await self._search_records_impl(
                criteria, start, rows, selected_fields
            )
        except CircuitBreakerError:
            logger.warning(
                "Circuit breaker open for search, attempting cache fallback"
            )
            cache_key = generate_cache_key(
                f"{self._CACHE_KEY_PREFIX}_search",
                criteria, start, rows,
                selected_fields=selected_fields,
            )
            if self.enable_cache and self.search_cache:
                cached = self.search_cache.get(cache_key)
                if cached:
                    cached["_cache_status"] = {
                        "source": "cache",
                        "circuit_breaker": "open",
                    }
                    return cached
            raise

    # ------------------------------------------------------------------
    # Utilities (shared verbatim)
    # ------------------------------------------------------------------

    def validate_lucene_query(self, query: str):
        from ..util.query_validator import validate_lucene_syntax
        return validate_lucene_syntax(query)

    async def close(self):
        await self.client.aclose()
