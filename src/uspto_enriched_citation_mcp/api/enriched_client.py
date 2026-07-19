"""
USPTO Enriched Citation API v3 client.

Concrete client for the /enriched_cited_reference_metadata/v3 endpoint.
Shares transport, caching, and resilience logic with OACitationsClient via
BaseCitationClient. get_fields/search_records (including circuit-breaker and
stale-cache fallback behaviour) and __init__ are fully inherited — this class
adds only the enriched-citations-specific query helpers.
"""

from typing import Dict, List, Optional, Tuple, Union

from .base_citation_client import BaseCitationClient
from ..config.constants import (
    ENRICHED_CITATIONS_FIELDS_PATH,
    ENRICHED_CITATIONS_RECORDS_PATH,
)
from ..shared.enums import ContextLevel
from ..util.logging import get_logger

logger = get_logger(__name__)


class EnrichedCitationClient(BaseCitationClient):
    """
    Async HTTP client for USPTO Enriched Citation API v3.
    Handles GZIP compression, authentication, Lucene queries, and rate limiting.

    Inherits shared transport, caching, rate-limiting, and resilience logic
    (including circuit breaker + stale-cache fallback) from BaseCitationClient
    unchanged, honoring the base constructor contract (LSP).
    """

    _FIELDS_PATH = ENRICHED_CITATIONS_FIELDS_PATH
    _RECORDS_PATH = ENRICHED_CITATIONS_RECORDS_PATH
    _CACHE_KEY_PREFIX = "enriched"

    # -------------------------------------------------------------------------
    # Public API (signature-compatible with original EnrichedCitationClient)
    # -------------------------------------------------------------------------

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
            # Route through the same sanitized-error-message machinery every
            # other path uses, instead of leaking str(e) to the caller.
            from ..shared.error_utils import get_safe_error_message

            safe_message = get_safe_error_message(
                e, "Failed to retrieve citation details"
            )
            return {
                "status": "error",
                "error": safe_message,
                "citation_id": citation_id,
            }
