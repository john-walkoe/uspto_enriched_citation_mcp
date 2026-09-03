"""Business logic for USPTO Office Action Citations API v2 tools."""

from typing import Dict, List, Optional

from ..api.oa_citations_client import OACitationsClient, OA_CITATIONS_MINIMAL_FIELDS, OA_CITATIONS_ALL_FIELDS
from ..shared.pfw_link import pfw_link_for
from ..util.logging import get_logger

logger = get_logger(__name__)


class OACitationService:
    """Service layer for OA Citations v2 operations."""

    def __init__(self, client: OACitationsClient):
        self.client = client

    async def _search(
        self,
        criteria: str,
        start: int,
        rows: int,
        custom_fields: Optional[List[str]],
        default_fields: List[str],
    ) -> Dict:
        """Shared search body for the minimal/balanced tiers.

        Runs the search with the tier's default field set (or the caller's
        custom set), applies client-side field filtering, and annotates docs
        with PFW cross-MCP links.
        """
        fields = custom_fields if custom_fields is not None else default_fields
        result = await self.client.search_records(criteria, start, rows, fields)
        if "error" in result:
            return result

        docs = result.get("response", {}).get("docs", [])

        # The OA Citations API ignores `fl` and returns every field whatever
        # is asked for, so the tier's field set only means anything if it is
        # applied here. This used to run for a CUSTOM list only, which left
        # the minimal tier's 7-field default unenforced: minimal served all
        # 16 fields — the same docs as balanced, plus a guidance block, so
        # the "high-volume discovery" tier cost MORE context than the detail
        # tier (measured 13,020 vs 12,754 chars on app 16816197). Filter on
        # both paths, then annotate.
        field_set = set(fields)
        result["response"]["docs"] = [
            {k: v for k, v in doc.items() if k in field_set}
            for doc in docs
        ]
        docs = result["response"]["docs"]

        # The per-row `_pfw_link` is the same sentence on every doc, differing
        # only in an app number the doc already carries — 1,476 chars of the
        # minimal tier's 7,350 on app 16816197, for zero information. On a
        # default-tier response the hand-off is stated ONCE, on the envelope
        # (`pfw_link`, added by tools/oa.py). It is still injected per row for
        # a CUSTOM field list, where the caller chose the doc shape and the
        # inline annotation is the established contract.
        if custom_fields is not None:
            for doc in docs:
                app_num = doc.get("patentApplicationNumber", "")
                if app_num:
                    doc["_pfw_link"] = pfw_link_for(app_num)

        return result

    async def search_minimal(
        self,
        criteria: str,
        start: int = 0,
        rows: int = 50,
        custom_fields: Optional[List[str]] = None,
    ) -> Dict:
        """Search OA Citations with minimal field set for high-volume discovery."""
        return await self._search(
            criteria, start, rows, custom_fields, OA_CITATIONS_MINIMAL_FIELDS
        )

    async def search_balanced(
        self,
        criteria: str,
        start: int = 0,
        rows: int = 25,
        custom_fields: Optional[List[str]] = None,
    ) -> Dict:
        """Search OA Citations with all available fields."""
        return await self._search(
            criteria, start, rows, custom_fields, OA_CITATIONS_ALL_FIELDS
        )

    async def get_fields(self) -> Dict:
        """Retrieve the list of searchable OA Citations v2 fields."""
        return await self.client.get_fields()
