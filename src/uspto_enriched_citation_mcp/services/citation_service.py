"""
Citation service for USPTO Enriched Citation MCP.
"""

import asyncio
from typing import Dict, Any, List, Optional, Tuple, Union
import structlog
from ..api.enriched_client import EnrichedCitationClient
from ..config.field_manager import FieldManager
from ..shared.enums import ContextLevel
from ..shared.error_utils import get_safe_error_message
from ..util.rate_limiter import get_rate_limiter

logger = structlog.get_logger(__name__)

# The breakdown fan-out, as data. `total` is the unscoped base query; the rest
# are scoped to it.
_BREAKDOWN_QUERIES: Tuple[Tuple[str, str], ...] = (
    ("x_count", "citationCategoryCode:X"),
    ("y_count", "citationCategoryCode:Y"),
    ("a_count", "citationCategoryCode:A"),
    ("examiner", "examinerCitedReferenceIndicator:true"),
    ("applicant", "applicantCitedExaminerReferenceIndicator:true"),
)

# One token per query in the fan-out, charged once up front.
_STATISTICS_QUOTA_COST = 1 + len(_BREAKDOWN_QUERIES)


class CitationService:
    """Service for handling citation operations."""

    def __init__(self, client: EnrichedCitationClient, field_manager: FieldManager):
        self.client = client
        self.field_manager = field_manager
        self.logger = logger

    async def get_details(
        self,
        citation_id: str,
        include_context: Union[bool, ContextLevel] = ContextLevel.FULL,
    ) -> Dict[str, Any]:
        """Get detailed citation information.

        The default is ContextLevel.FULL, matching both the tool above
        (tools/details.py passes include_context=True) and the client below
        (EnrichedCitationClient.get_citation_details); this layer used to
        default to the opposite of both (R-8).
        """
        return await self.client.get_citation_details(
            citation_id=citation_id, include_context=include_context
        )

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

            is_valid = validation_result.get("valid", True)
            response: Dict[str, Any] = {
                "status": "success",
                "valid": is_valid,
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

            # The whole point of this tool is explaining WHY a query is wrong.
            # The client already computed the reason; the rebuilt envelope used
            # to keep only the boolean and drop it, reporting "success" on a
            # query the search tools reject outright. Carry the reason through.
            if not is_valid:
                reason = (
                    validation_result.get("error")
                    or validation_result.get("message")
                    or "Query failed validation"
                )
                response["status"] = "error"
                response["error"] = reason
                response["message"] = reason

            return response
        except Exception as e:
            safe_message = get_safe_error_message(e, "Query validation failed")
            return {
                "status": "error",
                "valid": False,
                "query": query,
                "error": safe_message,
            }

    async def _fan_out_counts(self, criteria: str) -> Tuple[Dict[str, int], int]:
        """Run the base query plus every breakdown query concurrently.

        Returns (counts keyed by _BREAKDOWN_QUERIES name plus "total", number
        of sub-queries that failed). A failed sub-query counts as 0 so one
        upstream hiccup does not blank the whole response; the caller reports
        how many failed so a zero-because-failed is distinguishable from a
        zero-because-empty.
        """

        def scoped(extra: str) -> str:
            return f"({criteria}) AND ({extra})" if criteria else extra

        # rows=0 fetches no docs, just numFound. charge_quota=False because
        # get_statistics already charged the limiter for the whole fan-out.
        queries = [criteria or "*:*"] + [scoped(q) for _, q in _BREAKDOWN_QUERIES]
        results = await asyncio.gather(
            *(
                self.client.search_citations(criteria=q, rows=0, charge_quota=False)
                for q in queries
            ),
            return_exceptions=True,
        )

        def count(r: Any) -> int:
            if isinstance(r, Exception):
                return 0
            return r.get("response", {}).get("numFound", 0)

        counts = {"total": count(results[0])}
        for (name, _), result in zip(_BREAKDOWN_QUERIES, results[1:]):
            counts[name] = count(result)
        queries_failed = sum(1 for r in results if isinstance(r, Exception))
        return counts, queries_failed

    def _shape_statistics(
        self, counts: Dict[str, int], criteria: str, queries_failed: int
    ) -> Dict[str, Any]:
        """Build the statistics response envelope from the raw counts."""
        response: Dict[str, Any] = {
            "status": "success",
            "total_citations": counts["total"],
            "query": criteria or "all records",
            "examiner_cited_count": counts["examiner"],
            "applicant_cited_count": counts["applicant"],
            "breakdowns": {
                "Citation Category": {
                    "X — Novel (§102)": counts["x_count"],
                    "Y — Inventive Step (§103)": counts["y_count"],
                    "A — Background Art": counts["a_count"],
                },
                "Cited By": {
                    "Examiner (Form 892)": counts["examiner"],
                    "Applicant (Form 1449)": counts["applicant"],
                },
            },
        }
        if queries_failed:
            self.logger.warning(
                "get_statistics: %d/%d count queries failed, "
                "affected breakdowns report as 0",
                queries_failed,
                len(_BREAKDOWN_QUERIES) + 1,
            )
            response["queries_failed"] = queries_failed
        return response

    async def get_statistics(
        self, criteria: str = "", stats_fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get database statistics with breakdowns via parallel count queries.

        `stats_fields` is accepted and currently unused: the breakdowns are
        fixed. It exists so the tool signature above can keep documenting the
        parameter; see tools/statistics.py.
        """
        try:
            # This call fans out one query per breakdown plus the base query.
            # Charge the limiter for the full amplification cost up front and
            # pass charge_quota=False to the sub-calls, so the real cost is
            # what the comment says rather than double it.
            if not await get_rate_limiter().acquire(
                endpoint="get_citation_statistics", tokens=_STATISTICS_QUOTA_COST
            ):
                return {
                    "status": "error",
                    "error": (
                        f"Rate limit exceeded for statistics request "
                        f"({_STATISTICS_QUOTA_COST}x query amplification)"
                    ),
                }

            counts, queries_failed = await self._fan_out_counts(criteria)
            return self._shape_statistics(counts, criteria, queries_failed)
        except Exception as e:
            safe_message = get_safe_error_message(e, "Statistics retrieval failed")
            return {
                "status": "error",
                "error": safe_message,
            }

    def get_cross_mcp_links(self, search_result: Dict[str, Any]) -> Dict[str, Any]:
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
                if tech_center := doc.get("techCenter"):
                    tech_centers.add(str(tech_center))

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
                "guidance": "Use these identifiers to query PFW (PFW_search_applications_*) or PTAB (PTAB_search_trials_*) MCPs",
                "ptab_tools": {
                    "trials": "PTAB_search_trials_minimal/balanced/complete",
                    "documents": "PTAB_get_documents",
                    "example": "PTAB_search_trials_minimal(patent_number='10701173')"
                }
            }
        except Exception as e:
            safe_message = get_safe_error_message(e, "Cross-MCP link extraction failed")
            return {
                "available_links": {},
                "integration_ready": False,
                "error": safe_message,
            }
