"""Utility tools: field discovery, query validation, and sectioned guidance."""

from typing import Any, Dict

from .. import runtime
from ..config.field_manager import (
    DEFAULT_BALANCED_FIELDS as BALANCED_FIELDS,
    DEFAULT_MINIMAL_FIELDS as MINIMAL_FIELDS,
)
from ..shared.error_utils import format_error_response
from ..util.request_context import RequestContext
from ..util.logging import get_logger
from ..util.security_logger import get_security_logger

logger = get_logger(__name__)
security_logger = get_security_logger()


async def get_available_fields() -> Dict[str, Any]:  # no UI view — utility tool
    """Get all searchable fields from USPTO Enriched Citation API.
    Fields, available fields, columns, schema, what can I query, field names, query syntax for the enriched citations lane.

    Use for: Field discovery, query syntax validation, understanding data structure.
    Returns: Complete field list with descriptions and types.

    For field selection strategies and Solr/Lucene syntax examples, use Citations_get_guidance(section='fields').
    """
    with RequestContext():
        try:
            runtime.initialize_services()
            fields = await runtime.api_client.get_fields()
            return {
                "status": "success",
                "total_fields": len(fields.get("fields", [])),
                "fields": fields.get("fields", []),
                "usage_guidance": {
                    "query_syntax": "Use field:value format (e.g., techCenter:2100, patentApplicationNumber:18180061)",
                    "predefined_sets": {
                    # Derived, not asserted. A hardcoded literal sat next to
                    # len(BALANCED_FIELDS) here and the two disagreed, so this
                    # string shipped a count and its own contradiction to the
                    # model in one breath (D-11).
                        "citations_minimal": f"{len(MINIMAL_FIELDS)} essential fields",
                        "citations_balanced": f"{len(BALANCED_FIELDS)} comprehensive fields",
                    },
                    "best_practices": [
                        "Always use field-specific searches for precision",
                        "Check field types before building queries",
                        "Use Citations_validate_query for complex syntax",
                    ],
                },
            }
        except Exception as e:
            # Log API error for monitoring
            security_logger.api_error(
                endpoint="get_available_fields",
                error_code=500,
                error_type=type(e).__name__
            )
            return format_error_response("Field retrieval failed", 500, exception=e)


async def validate_query(
    query: str, field_set: str = "citations_minimal"
) -> Dict[str, Any]:
    """Validate Lucene query syntax and provide optimization suggestions.
    Check my query, syntax error, is this query valid, Lucene, Solr, escaping, dry run before searching, why did my search fail.

    Solr/Lucene Syntax Examples:
    - Field search: 'groupArtUnitNumber:2854'
    - Date range: 'officeActionDate:[2023-01-01 TO 2023-12-31]'
    - Boolean operators: 'citationCategoryCode:X AND techCenter:2100'
    - OR logic: '(citationCategoryCode:X OR citationCategoryCode:Y)'
    - NOT operator: 'techCenter:2100 NOT groupArtUnitNumber:1600'
    - Wildcard: 'citedDocumentIdentifier:US*'
    - NPL only: 'nplIndicator:true'
    - Open-ended range: 'officeActionDate:[2017-10-01 TO *]'

    For comprehensive query syntax guide, use Citations_get_guidance(section='fields').
    """
    with RequestContext():
        try:
            runtime.initialize_services()
            if not query:
                return format_error_response("Query required", 400)

            result = await runtime.citation_service.validate_and_optimize_query(
                query, field_set
            )
            return result
        except Exception as e:
            security_logger.api_error(
                endpoint="validate_query",
                error_code=500,
                error_type=type(e).__name__,
            )
            return format_error_response("Validation failed", 500, exception=e)


async def citations_get_guidance(section: str = "overview") -> str:
    """Get selective USPTO Citation guidance sections for context-efficient workflows

    🎯 QUICK REFERENCE - What section for your question?

    🔍 "Find citations by examiner/application/tech" → fields
    🔀 "Which lane: OA citations or enriched citations?" → oa_citations
    📄 "Understand citation categories (X/Y/A + NPL via nplIndicator)" → citation_codes
    🔖 "Citation date coverage per lane" → data_coverage
    🤝 "PFW workflow for office action documents" → workflows_pfw
    🚩 "PTAB citation correlation" → workflows_ptab (updated for 2026 PTAB API)
    📊 "FPD petition citation patterns" → workflows_fpd
    🏢 "Complete lifecycle analysis" → workflows_complete
    ⚙️ "Tool guidance and parameters" → tools
    ❌ "Search errors or query issues" → errors
    💰 "Reduce API costs and optimize" → cost

    Available sections:
    - overview: Available sections and tool summary
    - workflows_pfw: Citation + PFW integration workflows
    - workflows_ptab: Citation + PTAB integration workflows (updated 2026-01-17)
    - workflows_fpd: Citation + FPD integration workflows
    - workflows_complete: Four-MCP complete lifecycle analysis

    PTAB Integration (updated 2026-01-17):
    - Trials: PTAB_search_trials_minimal/balanced/complete
    - Documents: PTAB_get_documents, PTAB_get_document_download, PTAB_get_document_content
    - See: Citations_get_guidance(section='workflows_ptab') for integration patterns
    - citation_codes: X/Y/A category decoder; NPL identified by nplIndicator:true field
    - oa_citations: OA (v2) vs enriched (v3) routing rule, measured coverage, field matrix
    - data_coverage: per-lane date coverage and date handling
    - fields: Field selection strategies and Solr/Lucene syntax
    - tools: Tool-specific guidance and parameters
    - errors: Common error patterns and troubleshooting
    - cost: Cost optimization strategies

    Args:
        section: Which guidance section to retrieve (default: overview)

    Returns:
        str: Focused guidance section (1-12KB vs 62KB full content)
    """
    with RequestContext():
        return _guidance_section(section)


def _guidance_section(section: str) -> str:
    try:
        from ..config import tool_reflections

        # Section BUILDERS, not built sections. Calling all twelve assembled
        # the full ~62KB on every invocation and threw away eleven twelfths
        # of it — including on the invalid-section path — while the docstring
        # advertised "1-12KB vs 62KB" (D-3).
        sections = {
            "overview": tool_reflections._get_overview_section,
            "workflows_pfw": tool_reflections._get_workflows_pfw_section,
            "workflows_ptab": tool_reflections._get_workflows_ptab_section,
            "workflows_fpd": tool_reflections._get_workflows_fpd_section,
            "workflows_complete": tool_reflections._get_workflows_complete_section,
            "citation_codes": tool_reflections._get_citation_codes_section,
            "oa_citations": tool_reflections._get_oa_citations_section,
            "data_coverage": tool_reflections._get_data_coverage_section,
            "fields": tool_reflections._get_fields_section,
            "tools": tool_reflections._get_tools_section,
            "errors": tool_reflections._get_errors_section,
            "cost": tool_reflections._get_cost_section,
        }

        if section not in sections:
            available = ", ".join(sections.keys())
            return f"Invalid section '{section}'. Available: {available}"

        body = sections[section]()
        result = f"# USPTO Citation MCP Guidance - {section.title()} Section\n\n{body}"

        logger.info(f"Retrieved Citation guidance section '{section}' ({len(result)} characters)")
        return result

    except Exception:
        # This tool is annotated `-> str` and FastMCP builds its output schema
        # from that annotation, so the error path must return a string too;
        # it used to return format_error_response's dict (E-2 / R-6). The
        # raw exception text is gone with it: this was the only tool in the
        # repo that put str(e) in front of the caller.
        logger.error(
            "Error accessing Citation guidance section '%s'", section, exc_info=True
        )
        return (
            f"# USPTO Citation MCP Guidance - Error\n\n"
            f"Could not load section '{section}'. "
            f"Try Citations_get_guidance(section='overview')."
        )


def register_fields(mcp) -> None:
    mcp.tool(
        name="Citations_get_available_fields",
        annotations={"defer_loading": True, "readOnlyHint": True},
    )(get_available_fields)


def register_validate(mcp) -> None:
    mcp.tool(
        name="Citations_validate_query",
        annotations={"defer_loading": True, "readOnlyHint": True},
    )(validate_query)


def register_guidance(mcp) -> None:
    mcp.tool(
        name="Citations_get_guidance",
        annotations={"defer_loading": False, "readOnlyHint": True},
    )(citations_get_guidance)


def register(mcp) -> None:
    """Register all three utility tools (grouped; use the granular
    register_fields/register_validate/register_guidance functions instead when
    interleaving with other modules' tools to preserve tools/list order)."""
    register_fields(mcp)
    register_validate(mcp)
    register_guidance(mcp)
