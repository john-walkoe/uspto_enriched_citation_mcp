"""Enriched Citations (v3) statistics/aggregation tool."""

from typing import Any, Dict

from fastmcp.apps import AppConfig

from .. import runtime
from ..app_uris import STATISTICS_URI
from ..config.constants import MAX_QUERY_LENGTH
from ..shared.error_utils import format_error_response
from ..util.query_validator import validate_lucene_syntax
from ..util.request_context import RequestContext
from ..util.security_logger import get_security_logger

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
    Counts, totals, aggregate, how many, distribution, breakdown by art unit or tech center, trends over time, citation volume."""
    with RequestContext():
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
            result = await runtime.citation_service.get_statistics(criteria)
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
