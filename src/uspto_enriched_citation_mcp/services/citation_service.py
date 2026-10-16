"""
Citation service for USPTO Enriched Citation MCP.
"""

import asyncio
from typing import Dict, Any, List, Optional, Sequence, Tuple, Union
import structlog
from ..api.enriched_client import EnrichedCitationClient
from ..config.field_manager import FieldManager
from ..shared.enums import ContextLevel
from ..shared.error_utils import format_error_response, get_safe_error_message
from ..util.deadline import Deadline

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

# The fan-out stops waiting this long before the call's deadline, so the
# partial answer is shaped and returned inside the budget rather than racing
# the whole-call backstop in tools/_shared.run_with_deadline.
_FANOUT_RESERVE_SECONDS = 1.0


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

    async def _fan_out_counts(
        self, criteria: str, deadline: Optional[Deadline] = None
    ) -> Tuple[Dict[str, Optional[int]], int, List[str]]:
        """Run the base query plus every breakdown query concurrently.

        Returns (counts keyed by _BREAKDOWN_QUERIES name plus "total", number
        of sub-queries that failed, names of the sub-queries the deadline cut
        off). A failed sub-query counts as 0 so one upstream hiccup does not
        blank the whole response; the caller reports how many failed so a
        zero-because-failed is distinguishable from a zero-because-empty. A
        sub-query still running when `deadline` (less the reserve) runs out is
        cancelled and counts as None: it has no value, not a zero one. With
        less than the reserve left, nothing is sent at all.
        """

        def scoped(extra: str) -> str:
            return f"({criteria}) AND ({extra})" if criteria else extra

        names = ["total"] + [name for name, _ in _BREAKDOWN_QUERIES]
        timeout: Optional[float] = None
        if deadline is not None:
            timeout = deadline.remaining() - _FANOUT_RESERVE_SECONDS
            if timeout <= 0:
                return {name: None for name in names}, 0, names

        # rows=0 fetches no docs, just numFound. charge_quota=False because
        # get_statistics already charged the limiter for the whole fan-out.
        queries = [criteria or "*:*"] + [scoped(q) for _, q in _BREAKDOWN_QUERIES]
        tasks = [
            asyncio.ensure_future(
                self.client.search_citations(criteria=q, rows=0, charge_quota=False)
            )
            for q in queries
        ]
        try:
            # One wait for the whole fan-out: retries and backoff inside each
            # sub-query spend the same budget, never a fresh one per attempt.
            await asyncio.wait(tasks, timeout=timeout)
        finally:
            # Cut off by the deadline, or the whole call was cancelled: stop
            # whatever is still running so no request outlives the tool call.
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        return self._tally(names, tasks)

    @staticmethod
    def _tally(
        names: List[str], tasks: Sequence["asyncio.Future[Any]"]
    ) -> Tuple[Dict[str, Optional[int]], int, List[str]]:
        """Counts, failures and deadline-cut names from the finished tasks."""
        counts: Dict[str, Optional[int]] = {}
        failed = 0
        unfinished: List[str] = []
        for name, task in zip(names, tasks):
            if task.cancelled():
                counts[name] = None
                unfinished.append(name)
            elif task.exception() is not None:
                counts[name] = 0
                failed += 1
            else:
                counts[name] = task.result().get("response", {}).get("numFound", 0)
        return counts, failed, unfinished

    def _shape_statistics(
        self, counts: Dict[str, Optional[int]], criteria: str, queries_failed: int
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

    @staticmethod
    def _deadline_result(
        response: Dict[str, Any], unfinished: List[str], deadline: Deadline
    ) -> Dict[str, Any]:
        """Mark a statistics envelope the deadline cut short.

        Some counts returned: keep them (status stays success) and say which
        are missing and why. None returned: the same 504 the whole-call
        deadline gives (tools/_shared.run_with_deadline), worded
        "Deadline exceeded" as the sibling servers' content deadlines are.
        """
        total = len(_BREAKDOWN_QUERIES) + 1
        budget = f"{deadline.seconds:.0f}s"
        if len(unfinished) == total:
            return format_error_response(
                f"Deadline exceeded: no statistics count returned within the "
                f"{budget} budget. Narrow the query or retry; the upstream "
                f"USPTO API did not answer in time.",
                504,
            )
        logger.warning(
            "get_statistics: %d/%d count queries cut off by the deadline",
            len(unfinished),
            total,
        )
        response["deadline_exceeded"] = True
        response["queries_unfinished"] = len(unfinished)
        response["unfinished_queries"] = unfinished
        response["deadline_note"] = (
            f"Deadline exceeded: {len(unfinished)} of {total} count queries "
            f"did not return within the {budget} budget, so their values are "
            f"null (unknown), not zero. Every other count is complete. Re-run "
            f"with narrower criteria to fill them in."
        )
        return response

    async def get_statistics(
        self,
        criteria: str = "",
        stats_fields: Optional[List[str]] = None,
        deadline: Optional[Deadline] = None,
    ) -> Dict[str, Any]:
        """Get database statistics with breakdowns via parallel count queries.

        `stats_fields` is accepted and currently unused: the breakdowns are
        fixed. It exists so the tool signature above can keep documenting the
        parameter; see tools/statistics.py.

        `deadline` is the tool call's one end-to-end budget
        (CITATIONS_CONTENT_DEADLINE_SECONDS, created when the tool starts):
        the fan-out waits only for what is left of it and returns the counts
        that made it, with a deadline note for the rest.
        """
        try:
            # This call fans out one query per breakdown plus the base query.
            # Charge the limiter for the full amplification cost up front and
            # pass charge_quota=False to the sub-calls, so the real cost is
            # what the comment says rather than double it.
            #
            # CR-02 (review 2026-09-28, regression of S-13): this used to
            # charge util.rate_limiter.get_rate_limiter()'s process-wide
            # singleton. b0531e2 gave each lane its own RateLimiter instance
            # (runtime.py build()) and production never wires the singleton
            # into any of them, so the six-call fan-out sailed through
            # charged against a bucket nothing else in the process ever
            # draws from or waits on. Charge the ENRICHED lane's own
            # limiter instead — the same bucket search_citations draws
            # from (self.client.rate_limiter, endpoint
            # "<prefix>_search_records") — so statistics competes for the
            # same budget the search tools do.
            if not await self.client.rate_limiter.acquire(
                endpoint=f"{self.client._CACHE_KEY_PREFIX}_search_records",
                tokens=_STATISTICS_QUOTA_COST,
            ):
                return {
                    "status": "error",
                    "error": (
                        f"Rate limit exceeded for statistics request "
                        f"({_STATISTICS_QUOTA_COST}x query amplification)"
                    ),
                }

            counts, queries_failed, unfinished = await self._fan_out_counts(
                criteria, deadline
            )
            response = self._shape_statistics(counts, criteria, queries_failed)
            if unfinished and deadline is not None:
                return self._deadline_result(response, unfinished, deadline)
            return response
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
