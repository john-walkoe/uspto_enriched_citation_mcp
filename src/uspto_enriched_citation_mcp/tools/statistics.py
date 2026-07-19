"""Enriched Citations (v3) statistics/aggregation tool."""

from typing import Any, Dict, List

from fastmcp.apps import AppConfig

from .. import runtime
from ..app_uris import STATISTICS_URI
from ..config.constants import MAX_QUERY_LENGTH
from ..shared.error_utils import format_error_response
from ..util.query_validator import validate_lucene_syntax


async def get_citation_statistics(
    criteria: str = "",
    stats_fields: List[str] = ["decisionTypeCode", "citationCategoryCode"],
) -> Dict[str, Any]:
    """Get database statistics and aggregations for strategic planning."""
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
    except Exception as e:
        return format_error_response("Statistics retrieval failed", 500, exception=e)


def register(mcp) -> None:
    """Register get_citation_statistics (name/schema unchanged)."""
    mcp.tool(
        app=AppConfig(resource_uri=STATISTICS_URI),
        annotations={"defer_loading": True, "readOnlyHint": True},
    )(get_citation_statistics)
