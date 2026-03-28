"""
USPTO Enriched Citation API v3 client.

Concrete client for the /enriched_cited_reference_metadata/v3 endpoint.
Shares transport, caching, and resilience logic with OACitationsClient via
BaseCitationClient.
"""

import time
from typing import Dict, List, Optional, Tuple, Union

from .base_citation_client import BaseCitationClient
from ..config.constants import (
    ENRICHED_CITATIONS_FIELDS_PATH,
    ENRICHED_CITATIONS_RECORDS_PATH,
)
from ..util.metrics import get_metrics_collector, MetricsCollector
from ..shared.circuit_breaker import CircuitBreakerError
from ..shared.enums import ContextLevel
from ..shared.exceptions import APIResponseError, APITimeoutError, APIConnectionError


class EnrichedCitationClient(BaseCitationClient):
    """
    Async HTTP client for USPTO Enriched Citation API v3.
    Handles GZIP compression, authentication, Lucene queries, and rate limiting.

    Inherits shared transport, caching, rate-limiting, and resilience logic
    from BaseCitationClient.
    """

    _FIELDS_PATH = ENRICHED_CITATIONS_FIELDS_PATH
    _RECORDS_PATH = ENRICHED_CITATIONS_RECORDS_PATH
    _CACHE_KEY_PREFIX = "enriched"

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
    ):
        # BaseCitationClient initialises: httpx client, rate limiter, metrics,
        # fields cache, search cache.
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            rate_limit=rate_limit,
            timeout=timeout,
            metrics_collector=metrics_collector,
            enable_cache=enable_cache,
            fields_cache_ttl=fields_cache_ttl,
            search_cache_size=search_cache_size,
        )

    # -------------------------------------------------------------------------
    # Public API (signature-compatible with original EnrichedCitationClient)
    # -------------------------------------------------------------------------

    async def get_fields(self) -> Dict:
        """
        GET /enriched_cited_reference_metadata/v3/fields

        Protected by circuit breaker and automatically retries on transient failures.
        Cached with TTL for performance. Falls back to stale cache on circuit
        breaker open and transient API errors (timeouts, connection failures).
        """
        try:
            return await self._get_fields_impl()
        except CircuitBreakerError:
            # Circuit breaker is open — try stale cache for graceful degradation.
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                "Circuit breaker open for get_fields, attempting fallback to stale cache"
            )
            cache_key = self._make_cache_key(f"{self._CACHE_KEY_PREFIX}_fields")
            if self.enable_cache and self.fields_cache:
                meta = self.fields_cache.get_with_metadata(
                    cache_key, allow_stale=True
                )
                if meta:
                    result = meta["value"]
                    result["_cache_status"] = {
                        "source": "stale_cache",
                        "is_stale": True,
                        "age_seconds": meta["age_seconds"],
                        "message": "Service temporarily unavailable — using cached data",
                        "circuit_breaker": "open",
                    }
                    return result
            raise
        except (APITimeoutError, APIConnectionError) as e:
            # Transient error — try stale cache before giving up.
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Transient error in get_fields ({type(e).__name__}), "
                "attempting stale cache fallback"
            )
            cache_key = self._make_cache_key(f"{self._CACHE_KEY_PREFIX}_fields")
            if self.enable_cache and self.fields_cache:
                meta = self.fields_cache.get_with_metadata(
                    cache_key, allow_stale=True
                )
                if meta:
                    result = meta["value"]
                    result["_cache_status"] = {
                        "source": "stale_cache",
                        "is_stale": True,
                        "age_seconds": meta["age_seconds"],
                        "message": f"API temporarily unavailable ({type(e).__name__}) — using cached data",
                        "error_type": type(e).__name__,
                    }
                    return result
            raise

    async def search_records(
        self,
        criteria: str,
        start: int = 0,
        rows: int = 50,
        selected_fields: Optional[List[str]] = None,
    ) -> Dict:
        """
        POST /enriched_cited_reference_metadata/v3/records

        Protected by circuit breaker and automatically retries on transient failures.
        Cached with LRU for performance. Falls back to stale cache on circuit
        breaker open and transient API errors (timeouts, connection failures).
        """
        try:
            return await self._search_records_impl(
                criteria, start, rows, selected_fields
            )
        except CircuitBreakerError:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Circuit breaker open for search (criteria: {criteria[:50]!r}), "
                "attempting stale cache fallback"
            )
            cache_key = self._make_search_cache_key(
                criteria, start, rows, selected_fields
            )
            if self.enable_cache and self.search_cache:
                cached = self.search_cache.get(cache_key)
                if cached:
                    cached["_cache_status"] = {
                        "source": "cache",
                        "is_stale": False,
                        "message": "Service temporarily unavailable — using cached results",
                        "circuit_breaker": "open",
                    }
                    return cached
            raise
        except (APITimeoutError, APIConnectionError) as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Transient error in search ({type(e).__name__}), "
                "attempting stale cache fallback"
            )
            cache_key = self._make_search_cache_key(
                criteria, start, rows, selected_fields
            )
            if self.enable_cache and self.search_cache:
                cached = self.search_cache.get(cache_key)
                if cached:
                    cached["_cache_status"] = {
                        "source": "cache",
                        "is_stale": False,
                        "message": f"API temporarily unavailable ({type(e).__name__}) — using cached results",
                        "error_type": type(e).__name__,
                    }
                    return cached
            raise

    async def search_citations(
        self,
        criteria: str,
        fields: Optional[List[str]] = None,
        start: int = 0,
        rows: int = 50,
    ) -> Dict:
        """
        Search citations (alias for search_records with 'fields' param name).

        Args:
            criteria: Lucene query string
            fields: List of field names to return (optional)
            start: Starting offset for pagination
            rows: Number of results to return

        Returns:
            Dict with search results in format:
            {"response": {"start": X, "numFound": Y, "docs": [...]}}
        """
        return await self.search_records(
            criteria=criteria, start=start, rows=rows, selected_fields=fields
        )

    def validate_lucene_query(self, query: str) -> Tuple[bool, str]:
        """Validate Lucene query syntax using utility."""
        return self._validate_lucene_syntax(query)

    @staticmethod
    def _validate_lucene_syntax(query: str) -> Tuple[bool, str]:
        from ..util.query_validator import validate_lucene_syntax
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
            include_context: Context inclusion level (ContextLevel.FULL or
                           ContextLevel.MINIMAL). For backward compatibility,
                           also accepts bool (True=FULL, False=MINIMAL).

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
            criteria = f"id:{citation_id}"
            # Full context: pass None so API returns all fields.
            # Minimal context: pass [] to get minimal field set.
            selected_fields = None if context_level == ContextLevel.FULL else []

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

    # -------------------------------------------------------------------------
    # Internal helpers (for cache-key construction used in get_fields / search)
    # -------------------------------------------------------------------------

    @staticmethod
    def _make_cache_key(suffix: str) -> str:
        # Delegates to the same cache-key logic used by base._get_fields_impl.
        from ..util.cache import generate_cache_key
        return generate_cache_key(suffix, "https://api.uspto.gov")

    @staticmethod
    def _make_search_cache_key(
        criteria: str,
        start: int,
        rows: int,
        selected_fields: Optional[List[str]] = None,
    ) -> str:
        from ..util.cache import generate_cache_key
        return generate_cache_key(
            "enriched_search",
            criteria, start, rows,
            selected_fields=selected_fields,
        )
