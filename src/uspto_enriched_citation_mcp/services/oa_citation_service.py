"""Business logic for USPTO Office Action Citations API v2 tools."""

import logging
from typing import Dict, List, Optional

from ..api.oa_citations_client import OACitationsClient, OA_CITATIONS_MINIMAL_FIELDS, OA_CITATIONS_ALL_FIELDS

logger = logging.getLogger(__name__)


class OACitationService:
    """Service layer for OA Citations v2 operations."""

    def __init__(self, client: OACitationsClient):
        self.client = client

    async def search_minimal(
        self,
        criteria: str,
        start: int = 0,
        rows: int = 50,
        custom_fields: Optional[List[str]] = None,
    ) -> Dict:
        """Search OA Citations with minimal field set for high-volume discovery."""
        fields = custom_fields if custom_fields is not None else OA_CITATIONS_MINIMAL_FIELDS
        result = await self.client.search_records(criteria, start, rows, fields)
        if "error" in result:
            return result

        docs = result.get("response", {}).get("docs", [])

        # OA Citations API ignores fl — filter fields client-side when custom set requested
        if custom_fields is not None:
            field_set = set(custom_fields)
            result["response"]["docs"] = [
                {k: v for k, v in doc.items() if k in field_set}
                for doc in docs
            ]
            docs = result["response"]["docs"]

        for doc in docs:
            app_num = doc.get("patentApplicationNumber", "")
            if app_num:
                doc["_pfw_link"] = f"Use PFW MCP: pfw_get_application_documents(app_number='{app_num}')"

        return result

    async def search_balanced(
        self,
        criteria: str,
        start: int = 0,
        rows: int = 25,
        custom_fields: Optional[List[str]] = None,
    ) -> Dict:
        """Search OA Citations with all available fields."""
        fields = custom_fields if custom_fields is not None else OA_CITATIONS_ALL_FIELDS
        result = await self.client.search_records(criteria, start, rows, fields)
        if "error" in result:
            return result

        docs = result.get("response", {}).get("docs", [])

        # OA Citations API ignores fl — filter fields client-side when custom set requested
        if custom_fields is not None:
            field_set = set(custom_fields)
            result["response"]["docs"] = [
                {k: v for k, v in doc.items() if k in field_set}
                for doc in docs
            ]
            docs = result["response"]["docs"]

        for doc in docs:
            app_num = doc.get("patentApplicationNumber", "")
            if app_num:
                doc["_pfw_link"] = f"Use PFW MCP: pfw_get_application_documents(app_number='{app_num}')"

        return result

    async def get_fields(self) -> Dict:
        """Retrieve the list of searchable OA Citations v2 fields."""
        return await self.client.get_fields()
