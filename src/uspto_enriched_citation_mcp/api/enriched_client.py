"""
USPTO Enriched Citation API v3 client.

Concrete client for the /enriched_cited_reference_metadata/v3 endpoint.
Shares transport, caching, and resilience logic with OACitationsClient via
BaseCitationClient. get_fields/search_records (including circuit-breaker and
stale-cache fallback behavior) and __init__ are fully inherited — this class
adds only the enriched-citations-specific query helpers.
"""

import re
from typing import Dict, List, Optional, Union

from .base_citation_client import BaseCitationClient
from ..config.constants import (
    ENRICHED_CITATIONS_FIELDS_PATH,
    ENRICHED_CITATIONS_RECORDS_PATH,
)
from ..config.field_manager import DEFAULT_MINIMAL_FIELDS
from ..shared.enums import ContextLevel
from ..util.logging import get_logger

logger = get_logger(__name__)

# Enriched citation `id` values are 32 hex characters. Enforced here, at the
# layer that builds the `id:<value>` Lucene clause, so a future caller
# reaching the client directly cannot bypass the tool-layer check.
_CITATION_ID_RE = re.compile(r"^[0-9a-f]{32}$", re.IGNORECASE)


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
        charge_quota: bool = True,
    ) -> Dict:
        """
        Search citations (alias for search_records with 'fields' param name).

        Args:
            criteria: Lucene query string
            fields: List of field names to return (optional)
            start: Starting offset for pagination
            rows: Number of results to return
            charge_quota: False when the caller already charged the rate
                limiter for a whole fan-out of sub-calls

        Returns:
            Dict with search results in format:
            {"response": {"start": X, "numFound": Y, "docs": [...]}}
        """
        return await self.search_records(
            criteria=criteria,
            start=start,
            rows=rows,
            selected_fields=fields,
            charge_quota=charge_quota,
        )

    # validate_lucene_query is inherited from BaseCitationClient, which is the
    # same one-line passthrough to util.query_validator.validate_lucene_syntax.

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

        # The identifier guard lives here, at the sink that interpolates it
        # into a Lucene clause, not only in tools/details.py one layer above
        # (S-32). The tool check stays as a fast fail.
        if not _CITATION_ID_RE.fullmatch(citation_id.strip()):
            return {
                "status": "error",
                "error": (
                    "Invalid citation ID format. Expected a 32-character "
                    "hexadecimal identifier from a search result's `id` field."
                ),
                "citation_id": citation_id,
            }

        try:
            # Search for the specific citation by ID
            criteria = f"id:{citation_id}"
            # Full context: pass None so API returns all fields.
            # Minimal context: pass the actual minimal field set. An empty
            # list is NOT a request for no fields — Solr treats an empty `fl`
            # as unset and returns the whole ~4KB record (passage blob and
            # all) while the envelope still says context_level "minimal", so
            # a caller budgeting context on the label under-counted by ~4x.
            selected_fields = (
                None
                if context_level == ContextLevel.FULL
                else list(DEFAULT_MINIMAL_FIELDS)
            )

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

            # The API ignores `fl` here the same way the OA v2 endpoint does
            # (verified live 2026-08-30: the full 22-field record comes back
            # for an 8-field request), so the minimal level only means
            # anything if it is enforced on this side. `id` is kept for
            # parity with the search tiers' filter.
            if selected_fields is not None:
                keep = set(selected_fields) | {"id"}
                citation = {k: v for k, v in citation.items() if k in keep}

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
