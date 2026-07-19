"""
Citation service for USPTO Enriched Citation MCP.
"""

from typing import Dict, Any
import structlog
from ..api.enriched_client import EnrichedCitationClient
from ..config.field_manager import FieldManager

logger = structlog.get_logger(__name__)


class CitationService:
    """Service for handling citation operations."""

    def __init__(self, client: EnrichedCitationClient, field_manager: FieldManager):
        self.client = client
        self.field_manager = field_manager
        self.logger = logger

    async def search_minimal(self, criteria: str, rows: int = 100) -> Dict[str, Any]:
        """Search citations with minimal field set."""
        fields = self.field_manager.get_field_set("citations_minimal")
        return await self.client.search_citations(
            criteria=criteria, fields=fields, rows=rows
        )

    async def search_balanced(self, criteria: str, rows: int = 20) -> Dict[str, Any]:
        """Search citations with balanced field set."""
        fields = self.field_manager.get_field_set("citations_balanced")
        return await self.client.search_citations(
            criteria=criteria, fields=fields, rows=rows
        )

    async def get_details(
        self, citation_id: str, include_context: bool = False
    ) -> Dict[str, Any]:
        """Get detailed citation information."""
        return await self.client.get_citation_details(
            citation_id=citation_id, include_context=include_context
        )

    async def get_available_fields(self) -> Dict[str, Any]:
        """Get available fields from API."""
        return await self.client.get_available_fields()

    async def validate_query(self, query: str) -> Dict[str, Any]:
        """Validate a Lucene query."""
        return await self.client.validate_query(query)

    async def validate_and_optimize_query(
        self, query: str, field_set: str = "citations_minimal"
    ) -> Dict[str, Any]:
        """Validate a Lucene query and provide optimization suggestions."""
        try:
            # Basic validation
            validation_result = await self.validate_query(query)

            # Add optimization suggestions
            suggestions = []
            if "*" in query and query.count("*") > 3:
                suggestions.append("Consider reducing wildcards for better performance")

            if "AND" not in query and "OR" not in query and " " in query:
                suggestions.append("Use explicit AND/OR operators for clarity")

            fields = self.field_manager.get_field_set(field_set)

            return {
                "status": "success",
                "valid": validation_result.get("valid", True),
                "query": query,
                "field_set": field_set,
                "available_fields": len(fields),
                "optimization_suggestions": suggestions,
                "query_tips": [
                    "Use field-specific searches (field:value)",
                    "Combine with boolean operators (AND, OR, NOT)",
                    "Use quotes for phrase searches",
                    "Use brackets for date ranges [start TO end]",
                ],
            }
        except Exception as e:
            from ..shared.error_utils import get_safe_error_message

            safe_message = get_safe_error_message(e, "Query validation failed")
            return {
                "status": "error",
                "valid": False,
                "query": query,
                "error": safe_message,
            }

    async def get_statistics(self, criteria: str = "") -> Dict[str, Any]:
        """Get database statistics with breakdowns via parallel count queries."""
        import asyncio
        from ..util.rate_limiter import get_rate_limiter

        try:
            # M2 (business-logic-vulnerabilities.md): this call fans out 6
            # parallel upstream queries per invocation — charge the rate
            # limiter for the full amplification cost up front (rather than
            # letting each of the 6 sub-calls acquire independently) so a
            # burst of statistics calls degrades the bucket proportionally to
            # its real cost, and rejects before any network round-trip.
            if not await get_rate_limiter().acquire(
                endpoint="get_citation_statistics", tokens=6
            ):
                return {
                    "status": "error",
                    "error": "Rate limit exceeded for statistics request (6x query amplification)",
                }

            base = criteria or "*:*"

            def scoped(extra: str) -> str:
                if criteria:
                    return f"({criteria}) AND ({extra})"
                return extra

            # Run all count queries in parallel (rows=0 fetches no docs, just numFound)
            results = await asyncio.gather(
                self.client.search_citations(criteria=base, rows=0),
                self.client.search_citations(criteria=scoped("citationCategoryCode:X"), rows=0),
                self.client.search_citations(criteria=scoped("citationCategoryCode:Y"), rows=0),
                self.client.search_citations(criteria=scoped("citationCategoryCode:A"), rows=0),
                self.client.search_citations(criteria=scoped("examinerCitedReferenceIndicator:true"), rows=0),
                self.client.search_citations(criteria=scoped("applicantCitedExaminerReferenceIndicator:true"), rows=0),
                return_exceptions=True,
            )

            def count(r: Any) -> int:
                if isinstance(r, Exception):
                    return 0
                return r.get("response", {}).get("numFound", 0)

            total      = count(results[0])
            x_count    = count(results[1])
            y_count    = count(results[2])
            a_count    = count(results[3])
            examiner   = count(results[4])
            applicant  = count(results[5])

            # 3.1: a failed sub-query silently degrades to a zero count above
            # (so a single upstream hiccup doesn't blank the whole response),
            # but reporting overall "success" with no signal that some counts
            # are zero-because-failed (not zero-because-empty) is misleading.
            # Surface the failure count additively; the zero counts stay.
            queries_failed = sum(1 for r in results if isinstance(r, Exception))

            response: Dict[str, Any] = {
                "status": "success",
                "total_citations": total,
                "query": criteria or "all records",
                "examiner_cited_count": examiner,
                "applicant_cited_count": applicant,
                "breakdowns": {
                    "Citation Category": {
                        "X — Novel (§102)": x_count,
                        "Y — Inventive Step (§103)": y_count,
                        "A — Background Art": a_count,
                    },
                    "Cited By": {
                        "Examiner (Form 892)": examiner,
                        "Applicant (Form 1449)": applicant,
                    },
                },
            }
            if queries_failed:
                self.logger.warning(
                    "get_statistics: %d/%d count queries failed, "
                    "affected breakdowns report as 0",
                    queries_failed,
                    len(results),
                )
                response["queries_failed"] = queries_failed
            return response
        except Exception as e:
            from ..shared.error_utils import get_safe_error_message

            safe_message = get_safe_error_message(e, "Statistics retrieval failed")
            return {
                "status": "error",
                "error": safe_message,
            }

    def _get_cross_mcp_links(self, search_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract cross-MCP linking fields from search results."""
        try:
            docs = search_result.get("response", {}).get("docs", [])

            if not docs:
                return {"available_links": {}, "integration_ready": False}

            # Extract unique identifiers for cross-MCP integration
            application_numbers = set()
            patent_numbers = set()
            art_units = set()
            tech_centers = set()

            for doc in docs:
                if app_num := doc.get("patentApplicationNumber"):
                    application_numbers.add(str(app_num))
                if pub_num := doc.get("publicationNumber"):
                    patent_numbers.add(str(pub_num))
                if art_unit := doc.get("groupArtUnitNumber"):
                    art_units.add(str(art_unit))
                if tc := doc.get("techCenter"):
                    tech_centers.add(str(tc))

            return {
                "available_links": {
                    "patent_file_wrapper": {
                        "field": "applicationNumberText",
                        "count": len(application_numbers),
                        "sample": (
                            list(application_numbers)[:5] if application_numbers else []
                        ),
                    },
                    "ptab": {
                        "field": "patentNumber",
                        "count": len(patent_numbers),
                        "sample": list(patent_numbers)[:5] if patent_numbers else [],
                    },
                    "art_units": {
                        "field": "groupArtUnitNumber",
                        "count": len(art_units),
                        "sample": list(art_units)[:5] if art_units else [],
                    },
                    "tech_centers": {
                        "field": "techCenter",
                        "count": len(tech_centers),
                        "sample": list(tech_centers)[:5] if tech_centers else [],
                    },
                },
                "integration_ready": len(application_numbers) > 0
                or len(patent_numbers) > 0,
                "guidance": "Use these identifiers to query PFW (pfw_search_applications_*) or PTAB (search_trials_*) MCPs",
                "ptab_tools": {
                    "trials": "search_trials_minimal/balanced/complete",
                    "documents": "ptab_get_documents",
                    "example": "search_trials_minimal(patent_number='10701173')"
                }
            }
        except Exception as e:
            from ..shared.error_utils import get_safe_error_message

            safe_message = get_safe_error_message(e, "Cross-MCP link extraction failed")
            return {
                "available_links": {},
                "integration_ready": False,
                "error": safe_message,
            }
