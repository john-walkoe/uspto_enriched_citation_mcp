"""Enriched Citations (v3) statistics/aggregation tool."""

from typing import Any, Dict

from fastmcp.apps import AppConfig

from .. import runtime
from ..app_uris import STATISTICS_URI
from ..config.constants import MAX_QUERY_LENGTH
from ..shared.error_utils import format_error_response
from ..util.citation_links import STATISTICS_CITATION_NOTE
from ..util.deadline import Deadline, content_deadline_seconds
from ..util.query_validator import validate_lucene_syntax
from ..util.request_context import RequestContext
from ..util.security_logger import get_security_logger
from ._shared import run_with_deadline

security_logger = get_security_logger()


# `stats_fields: List[str] = ["decisionTypeCode", "citationCategoryCode"]` used
# to sit in this signature. It was published in the tool's JSON schema, was
# never referenced in the body, and was a mutable default besides — a model
# asking for stats_fields=["groupArtUnitNumber"] got the fixed category and
# cited-by breakdowns back with no indication its request had been dropped.
# The breakdowns are fixed (services/citation_service._BREAKDOWN_QUERIES), so
# the honest fix is to stop advertising a dial that does not exist.
async def get_citation_statistics(criteria: str = "") -> Dict[str, Any]:
    """Get database statistics and aggregations for strategic planning.
    Counts, totals, aggregate, how many, distribution, breakdown by art unit or tech center, trends over time, citation volume.

    ⚠️ ENRICHED LANE ONLY. This tool aggregates the Enriched Citations (v3) index and
    nothing else. `criteria` is validated against the enriched field whitelist, so an
    OA-only clause (legalSectionCode, actionTypeCategory, paragraphNumber,
    referenceIdentifier, parsedReferenceIdentifier, workGroup) is a 400 here rather than
    a wrong answer, and there is no `lane` parameter: the OA Citations (v2) index has no
    statistics path on this server. That is a documented limit, not a bug to work around
    by rephrasing the clause.

    To aggregate the OA lane, count it yourself with the OA search tools and read
    `response.numFound`, which is the whole-result total and not the page size:
        Citations_search_oa_citations_minimal(criteria='techCenter:2100 AND legalSectionCode:103', rows=1)
    One call per bucket gives the same breakdown shape this tool returns for the enriched
    lane. Any cross-lane comparison must state which lane each number came from; the two
    indexes are independent and neither is a superset of the other.

    Returns for the enriched lane: total_citations, examiner_cited_count,
    applicant_cited_count, and breakdowns by citation category (X/Y/A) and by who cited.

    CITATIONS ARE LINKS: this tool returns counts, so it carries a `citation_note` and
    no per-record `cite_as`. A count is not a citation and has no public record to point
    at. To cite any of the citations behind a number here, re-run the same criteria
    through Citations_search_citations_minimal or Citations_search_oa_citations_minimal,
    whose rows each carry a ready-made `cite_as` link to the cited reference (the
    balanced tiers add an `application_cite_as` link to the application).
    """
    with RequestContext():
        # CR-02 (review 2026-09-28): this is the most expensive tool (base
        # query plus five breakdowns, see services/citation_service.py) and
        # was the one search-surface tool with no whole-call deadline, so a
        # slow upstream ran past the ~100s Cloudflare cutoff with nothing
        # returning an honest 504 first — same wrapper details.py uses.
        #
        # Wave 2 Part A item 5 (2026-10-06): ONE end-to-end budget per call,
        # CITATIONS_CONTENT_DEADLINE_SECONDS (85 s, under the ~100 s cut),
        # created here. The fan-out waits only for what is left of it and
        # keeps the counts that returned in time (a deadline note names the
        # rest); the wrapper is the backstop at the same end time.
        deadline = Deadline(content_deadline_seconds())
        return await run_with_deadline(
            lambda: _get_citation_statistics_body(criteria, deadline),
            "Statistics",
            deadline=deadline,
        )


async def _get_citation_statistics_body(
    criteria: str, deadline: Deadline
) -> Dict[str, Any]:
    try:
        runtime.initialize_services()
        if criteria and len(criteria) > MAX_QUERY_LENGTH:
            return format_error_response(
                f"Query too long (max {MAX_QUERY_LENGTH} characters)", 400
            )
        if criteria:
            is_valid, validation_msg = validate_lucene_syntax(criteria)
            if not is_valid:
                return format_error_response(validation_msg, 400)
        result = await runtime.citation_service.get_statistics(
            criteria, deadline=deadline
        )
        # Counts, not records: this envelope carries the note and no
        # per-row `cite_as`, because a number has no public record to
        # link to (util/citation_links).
        if isinstance(result, dict):
            result["citation_note"] = STATISTICS_CITATION_NOTE
        return result
    except ValueError as e:
        # A caller mistake is a 400 here as it is on the search tools; it
        # used to be the only tool that stamped build_query's ValueError
        # as a 500, the class an agent retries.
        security_logger.query_validation_failure(
            query=criteria, reason=str(e), severity="medium"
        )
        return format_error_response("Invalid search parameters", 400, exception=e)
    except Exception as e:
        security_logger.api_error(
            endpoint="get_citation_statistics",
            error_code=500,
            error_type=type(e).__name__,
        )
        return format_error_response(
            "Statistics retrieval failed", 500, exception=e
        )


def register(mcp) -> None:
    """Register get_citation_statistics as Citations_get_citation_statistics
    (function name/schema unchanged)."""
    mcp.tool(
        name="Citations_get_citation_statistics",
        app=AppConfig(resource_uri=STATISTICS_URI),
        annotations={"defer_loading": True, "readOnlyHint": True},
    )(get_citation_statistics)
