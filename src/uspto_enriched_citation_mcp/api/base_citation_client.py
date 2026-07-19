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
from ..shared.circuit_breaker import CircuitBreaker, CircuitBreakerError, get_circuit_breaker
from ..shared.uspto_shared_rate_limiter import get_shared_limiter
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
        circuit_breaker: Optional[CircuitBreaker] = None,
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

        # Circuit breaker: injected, or one per API (keyed by
        # _CACHE_KEY_PREFIX) so an outage in one USPTO API can't open the
        # circuit for an unrelated API sharing this base class.
        self._circuit_breaker = circuit_breaker or get_circuit_breaker(
            self._CACHE_KEY_PREFIX or self.__class__.__name__,
            failure_threshold=3,
            recovery_timeout=30.0,
            success_threshold=2,
        )

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

    async def _send(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Perform exactly one HTTP send against the persistent self.client.
        Single choke point for both _get_fields_raw and _search_records_raw,
        each called once per retry attempt by their @retry_async-wrapped
        _impl methods, so this runs once per ATTEMPT.

        Shared cross-process rate limiter (token + concurrency slot) — off
        unless USPTO_SHARED_RATE_LIMIT_DIR is set. This coordinates ACROSS
        processes on top of, not instead of, the existing per-instance
        self.rate_limiter token bucket (which callers still acquire before
        reaching here) — when both are enabled the shared limiter dominates
        since it is the stricter, cross-process ceiling.
        """
        if method.upper() == "POST":
            send = self.client.post(url, **kwargs)
        else:
            send = self.client.get(url, **kwargs)
        limiter = get_shared_limiter()
        if limiter is not None:
            async with limiter:
                return await send
        return await send

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
    #
    # Decorator order matters (E7): retry_async is OUTERMOST so the circuit
    # breaker (invoked inside _get_fields_impl via self._circuit_breaker)
    # sees every raw attempt individually. An open breaker raises
    # CircuitBreakerError on the very first attempt, which is excluded from
    # the retryable set, so it fails fast instead of burning up to
    # max_attempts retries against an already-open circuit.
    # ------------------------------------------------------------------

    async def _get_fields_raw(self) -> Dict:
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
            response = await self._send("GET", url)
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

    @retry_async(max_attempts=3, base_delay=1.0, max_delay=30.0)
    async def _get_fields_impl(self) -> Dict:
        return await self._circuit_breaker.call(self._get_fields_raw)

    def _stale_fields_cache_entry(self, extra_status: Dict) -> Optional[Dict]:
        """Look up a (possibly stale) cached fields entry for fallback."""
        if not (self.enable_cache and self.fields_cache):
            return None
        cache_key = generate_cache_key(
            f"{self._CACHE_KEY_PREFIX}_fields", self.base_url
        )
        meta = self.fields_cache.get_with_metadata(cache_key, allow_stale=True)
        if not meta:
            return None
        result = meta["value"]
        result["_cache_status"] = {
            "is_stale": meta["is_stale"],
            "age_seconds": meta["age_seconds"],
            **extra_status,
        }
        return result

    async def get_fields(self) -> Dict:
        """
        GET fields list with circuit breaker + stale-cache fallback.

        Falls back to stale cache both when the circuit breaker is open and
        on individual transient errors (timeouts, connection failures), so a
        single flaky request degrades gracefully instead of failing outright.
        """
        try:
            return await self._get_fields_impl()
        except CircuitBreakerError:
            logger.warning(
                "Circuit breaker open for get_fields, attempting stale cache fallback"
            )
            stale = self._stale_fields_cache_entry(
                {
                    "source": "stale_cache",
                    "message": "Service temporarily unavailable — using cached data",
                    "circuit_breaker": "open",
                }
            )
            if stale is not None:
                return stale
            raise
        except (APITimeoutError, APIConnectionError) as e:
            logger.warning(
                f"Transient error in get_fields ({type(e).__name__}), "
                "attempting stale cache fallback"
            )
            stale = self._stale_fields_cache_entry(
                {
                    "source": "stale_cache",
                    "message": f"API temporarily unavailable ({type(e).__name__}) — using cached data",
                    "error_type": type(e).__name__,
                }
            )
            if stale is not None:
                return stale
            raise

    # ------------------------------------------------------------------
    # Shared _search_records_impl (subclass controls endpoint via
    # self._RECORDS_PATH and cache-key prefix via self._CACHE_KEY_PREFIX)
    #
    # Same E7 ordering rationale as _get_fields_impl above: retry_async is
    # outermost, the per-instance circuit breaker is invoked per attempt.
    # ------------------------------------------------------------------

    def _get_cached_search_result(self, cache_key: str) -> Optional[Dict]:
        """Return the cached search result for `cache_key`, or None if
        caching is disabled or there's no cache entry."""
        if self.enable_cache and self.search_cache:
            return self.search_cache.get(cache_key)
        return None

    def _set_cached_search_result(self, cache_key: str, result: Dict) -> None:
        """Store `result` under `cache_key` if caching is enabled. No-op otherwise."""
        if self.enable_cache and self.search_cache:
            self.search_cache.set(cache_key, result)

    async def _search_records_raw(
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
        cached = self._get_cached_search_result(cache_key)
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

            response = await self._send("POST", url, data=data)
            self._handle_http_error(response)
            self._validate_content_type(response)
            self._validate_response_size(response)
            result = response.json()

            if "error" in result:
                raise APIResponseError(
                    f"API error: {result.get('error', 'Unknown error')}"
                )

            self._set_cached_search_result(cache_key, result)

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

    @retry_async(max_attempts=3, base_delay=1.0, max_delay=30.0)
    async def _search_records_impl(
        self,
        criteria: str,
        start: int = 0,
        rows: int = 50,
        selected_fields: Optional[List[str]] = None,
    ) -> Dict:
        return await self._circuit_breaker.call(
            self._search_records_raw, criteria, start, rows, selected_fields
        )

    def _stale_search_cache_entry(
        self,
        criteria: str,
        start: int,
        rows: int,
        selected_fields: Optional[List[str]],
        extra_status: Dict,
    ) -> Optional[Dict]:
        """Look up a cached search result for fallback (LRU cache, no TTL)."""
        if not (self.enable_cache and self.search_cache):
            return None
        cache_key = generate_cache_key(
            f"{self._CACHE_KEY_PREFIX}_search",
            criteria, start, rows,
            selected_fields=selected_fields,
        )
        cached = self.search_cache.get(cache_key)
        if not cached:
            return None
        cached["_cache_status"] = extra_status
        return cached

    async def search_records(
        self,
        criteria: str,
        start: int = 0,
        rows: int = 50,
        selected_fields: Optional[List[str]] = None,
    ) -> Dict:
        """
        Search with circuit breaker + cache fallback.

        Falls back to cached results both when the circuit breaker is open
        and on individual transient errors (timeouts, connection failures),
        so a single flaky request degrades gracefully instead of failing
        outright.
        """
        try:
            return await self._search_records_impl(
                criteria, start, rows, selected_fields
            )
        except CircuitBreakerError:
            logger.warning(
                "Circuit breaker open for search, attempting cache fallback"
            )
            cached = self._stale_search_cache_entry(
                criteria, start, rows, selected_fields,
                {
                    "source": "cache",
                    "message": "Service temporarily unavailable — using cached results",
                    "circuit_breaker": "open",
                },
            )
            if cached is not None:
                return cached
            raise
        except (APITimeoutError, APIConnectionError) as e:
            logger.warning(
                f"Transient error in search ({type(e).__name__}), "
                "attempting stale cache fallback"
            )
            cached = self._stale_search_cache_entry(
                criteria, start, rows, selected_fields,
                {
                    "source": "cache",
                    "message": f"API temporarily unavailable ({type(e).__name__}) — using cached results",
                    "error_type": type(e).__name__,
                },
            )
            if cached is not None:
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
