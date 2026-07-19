"""Utility tools: field discovery, query validation, and sectioned guidance."""

from typing import Any, Dict

from .. import runtime
from ..config.field_manager import (
    DEFAULT_BALANCED_FIELDS as BALANCED_FIELDS,
    DEFAULT_MINIMAL_FIELDS as MINIMAL_FIELDS,
)
from ..shared.error_utils import format_error_response
from ..util.logging import get_logger
from ..util.security_logger import get_security_logger

logger = get_logger(__name__)
security_logger = get_security_logger()


async def get_available_fields() -> Dict[str, Any]:  # no UI view — utility tool
    """Get all searchable fields from USPTO Enriched Citation API.

    Use for: Field discovery, query syntax validation, understanding data structure.
    Returns: Complete field list with descriptions and types.

    For field selection strategies and Solr/Lucene syntax examples, use citations_get_guidance(section='fields').
    """
    try:
        runtime.initialize_services()
        fields = await runtime.api_client.get_fields()
        return {
            "status": "success",
            "total_fields": len(fields.get("fields", [])),
            "fields": fields.get("fields", []),
            "usage_guidance": {
                "query_syntax": "Use field:value format (e.g., techCenter:2100, patentApplicationNumber:16751234)",
                "predefined_sets": {
                    "citations_minimal": f"8 essential fields ({len(MINIMAL_FIELDS)})",
                    "citations_balanced": f"18 comprehensive fields ({len(BALANCED_FIELDS)})",
                },
                "best_practices": [
                    "Always use field-specific searches for precision",
                    "Check field types before building queries",
                    "Use validate_query for complex syntax",
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

    Solr/Lucene Syntax Examples:
    - Field search: 'groupArtUnitNumber:2854'
    - Date range: 'officeActionDate:[2023-01-01 TO 2023-12-31]'
    - Boolean operators: 'citationCategoryCode:X AND techCenter:2100'
    - OR logic: '(citationCategoryCode:X OR citationCategoryCode:Y)'
    - NOT operator: 'techCenter:2100 NOT groupArtUnitNumber:1600'
    - Wildcard: 'citedDocumentIdentifier:US*'
    - Phrase search: 'examinerNameText:"Smith, John"'
    - Open-ended range: 'officeActionDate:[2017-10-01 TO *]'

    For comprehensive query syntax guide, use citations_get_guidance(section='fields').
    """
    try:
        runtime.initialize_services()
        if not query:
            return format_error_response("Query required", 400)

        result = await runtime.citation_service.validate_and_optimize_query(query, field_set)
        return result
    except Exception as e:
        return format_error_response("Validation failed", 500, exception=e)


async def citations_get_guidance(section: str = "overview") -> str:
    """Get selective USPTO Citation guidance sections for context-efficient workflows

    🎯 QUICK REFERENCE - What section for your question?

    🔍 "Find citations by examiner/application/tech" → fields
    📄 "Understand citation categories (X/Y/A + NPL via nplIndicator)" → citation_codes
    🔖 "Citation data coverage (2017+)" → data_coverage
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
    - Trials: search_trials_minimal/balanced/complete
    - Documents: ptab_get_documents, ptab_get_document_download, ptab_get_document_content
    - See: citations_get_guidance(section='workflows_ptab') for integration patterns
    - citation_codes: X/Y/A category decoder; NPL identified by nplIndicator:true field
    - data_coverage: 2017+ eligibility and date handling
    - fields: Field selection strategies and Solr/Lucene syntax
    - tools: Tool-specific guidance and parameters
    - errors: Common error patterns and troubleshooting
    - cost: Cost optimization strategies

    Args:
        section: Which guidance section to retrieve (default: overview)

    Returns:
        str: Focused guidance section (1-12KB vs 62KB full content)
    """
    try:
        from ..config import tool_reflections

        # Static sectioned guidance content for context-efficient access
        sections = {
            "overview": tool_reflections._get_overview_section(),
            "workflows_pfw": tool_reflections._get_workflows_pfw_section(),
            "workflows_ptab": tool_reflections._get_workflows_ptab_section(),
            "workflows_fpd": tool_reflections._get_workflows_fpd_section(),
            "workflows_complete": tool_reflections._get_workflows_complete_section(),
            "citation_codes": tool_reflections._get_citation_codes_section(),
            "data_coverage": tool_reflections._get_data_coverage_section(),
            "fields": tool_reflections._get_fields_section(),
            "tools": tool_reflections._get_tools_section(),
            "errors": tool_reflections._get_errors_section(),
            "cost": tool_reflections._get_cost_section()
        }

        if section not in sections:
            available = ", ".join(sections.keys())
            return f"Invalid section '{section}'. Available: {available}"

        result = f"# USPTO Citation MCP Guidance - {section.title()} Section\n\n{sections[section]}"

        logger.info(f"Retrieved Citation guidance section '{section}' ({len(result)} characters)")
        return result

    except Exception as e:
        logger.error(f"Error accessing Citation guidance section '{section}': {e}")
        return format_error_response(f"Failed to access guidance section '{section}': {str(e)}")


def register_fields(mcp) -> None:
    mcp.tool(annotations={"defer_loading": True, "readOnlyHint": True})(get_available_fields)


def register_validate(mcp) -> None:
    mcp.tool(annotations={"defer_loading": True, "readOnlyHint": True})(validate_query)


def register_guidance(mcp) -> None:
    mcp.tool(annotations={"defer_loading": False, "readOnlyHint": True})(citations_get_guidance)


def register(mcp) -> None:
    """Register all three utility tools (grouped; use the granular
    register_fields/register_validate/register_guidance functions instead when
    interleaving with other modules' tools to preserve tools/list order)."""
    register_fields(mcp)
    register_validate(mcp)
    register_guidance(mcp)
