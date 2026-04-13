"""USPTO Enriched Citation MCP Server"""

import sys
import os
from typing import Dict, List, Optional, Any
from fastmcp import FastMCP
from fastmcp.server.apps import AppConfig, ResourceCSP
import structlog

# Local imports
from .api.enriched_client import EnrichedCitationClient
from .api.oa_citations_client import OACitationsClient
from .config.field_manager import FieldManager, DEFAULT_MINIMAL_FIELDS as MINIMAL_FIELDS, DEFAULT_BALANCED_FIELDS as BALANCED_FIELDS
from .config.settings import get_settings
from .config.feature_flags import get_feature_flags
from .config.constants import (
    MAX_MINIMAL_SEARCH_ROWS,
    MAX_QUERY_LENGTH,
)
from .shared.error_utils import format_error_response
from .services.citation_service import CitationService
from .services.oa_citation_service import OACitationService
from .util.request_context import RequestContext
from .util.security_logger import get_security_logger
from .util.query_validator import validate_lucene_syntax
from .util.query_builder import (
    QueryParameters,
    validate_string_param,
    build_query,
)
from pathlib import Path


# Configure enhanced logging with file rotation and security hardening
from .util.logging import setup_logging
logger = setup_logging(level="INFO")

# Initialize security logger for audit trail
security_logger = get_security_logger()

# Configure structlog to write to stderr (not stdout) to avoid contaminating JSON-RPC stdio transport
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(
        file=sys.stderr
    ),  # CRITICAL: write to stderr, not stdout
    cache_logger_on_first_use=True,
)

# =============================================================================
# SERVER INSTRUCTIONS FOR TOOL SEARCH OPTIMIZATION
# =============================================================================
# These instructions guide Claude on tool usage patterns when tool search is enabled.
# With tool search, most tools are deferred (loaded on-demand) to save context tokens.
# The instructions help Claude discover and use the right tools efficiently.

SERVER_INSTRUCTIONS = """
Citations MCP provides USPTO citation data through 10 tools covering two APIs.

ALWAYS-AVAILABLE TOOLS (non-deferred, immediate access):
1. search_citations_minimal - Primary enriched citation discovery (90-95% context reduction)
2. citations_get_guidance - Workflow guidance and documentation (use section parameter)

ENRICHED CITATIONS (v3) - AI-extracted passage locations, claim mapping, quality scores:
- search_citations_minimal / search_citations_balanced - Progressive disclosure search
- get_citation_details - Full record for specific citation by ID
- get_citation_statistics - Aggregations and trend analysis
- get_available_fields - Enriched Citations field discovery

OFFICE ACTION CITATIONS (v2) - Raw citation lists from Form 892/1449, broader coverage:
- search_oa_citations_minimal / search_oa_citations_balanced - OA citation search
- get_oa_citation_fields - OA Citations field discovery

UTILITY TOOLS:
- validate_query - Lucene syntax validation and optimization
- citations_get_guidance - All workflow and integration guidance

PROGRESSIVE WORKFLOW:
1. Discovery: search_citations_minimal → broad pattern identification
2. Analysis: search_citations_balanced → detailed field analysis
3. Deep Dive: get_citation_details → individual citation context
4. OA Cross-check: search_oa_citations_minimal → verify via raw 892/1449 data

For workflow guidance: citations_get_guidance(section="tools")
For cross-MCP integration: citations_get_guidance(section="workflows_pfw")
"""

# Initialize FastMCP with server instructions for tool search optimization
mcp = FastMCP(
    "uspto-enriched-citation-mcp",
    instructions=SERVER_INSTRUCTIONS,
    icons=[{"src": "https://raw.githubusercontent.com/tailwindlabs/heroicons/master/src/24/outline/document-magnifying-glass.svg", "mimeType": "image/svg+xml"}],
)

# =============================================================================
# MCP APPS — Resource URIs and HTML view registration
# =============================================================================
from .ui.views import CITATION_RESULTS_HTML, OA_CITATIONS_HTML, STATISTICS_HTML  # noqa: E402

_CITATION_RESULTS_URI = "ui://uspto-enriched-citations/citation-results.html"
_OA_CITATIONS_URI = "ui://uspto-enriched-citations/oa-citations.html"
_STATISTICS_URI = "ui://uspto-enriched-citations/statistics.html"

def _build_csp_domains() -> list[str]:
    """Build CSP domain list for MCP Apps. Always includes CDN; MCP_APP_EXTRA_DOMAINS adds more."""
    domains = ["https://cdn.jsdelivr.net"]
    extra = os.getenv("MCP_APP_EXTRA_DOMAINS", "").strip()
    if extra:
        for d in extra.split(","):
            d = d.strip()
            if d:
                domains.append(d)
    return domains

_CSP = ResourceCSP(resource_domains=_build_csp_domains())


@mcp.resource(_CITATION_RESULTS_URI, app=AppConfig(csp=_CSP))
def citation_results_view() -> str:
    return CITATION_RESULTS_HTML


@mcp.resource(_OA_CITATIONS_URI, app=AppConfig(csp=_CSP))
def oa_citations_view() -> str:
    return OA_CITATIONS_HTML


@mcp.resource(_STATISTICS_URI, app=AppConfig(csp=_CSP))
def statistics_view() -> str:
    return STATISTICS_HTML


# Register all prompt templates with the MCP server
# This must be done AFTER mcp is created to avoid circular imports
from .prompts import register_prompts  # noqa: E402
register_prompts(mcp)

# Global variables for lazy initialization
api_client = None
oa_client = None
field_manager = None
citation_service = None
oa_citation_service = None


def initialize_services():
    """Initialize services with settings."""
    global api_client, oa_client, field_manager, citation_service, oa_citation_service

    if api_client is None:
        settings = get_settings()

        # Initialize feature flags
        feature_flags_path = None
        if settings.feature_flags_path:
            feature_flags_path = Path(settings.feature_flags_path)
        else:
            default_path = Path(__file__).parent.parent.parent / "feature_flags.conf"
            if default_path.exists():
                feature_flags_path = default_path

        get_feature_flags(config_file=feature_flags_path)
        logger.info("Feature flags initialized")

        api_client = EnrichedCitationClient(
            api_key=settings.uspto_ecitation_api_key,
            base_url=settings.uspto_base_url,
            rate_limit=settings.request_rate_limit,
            timeout=settings.api_timeout,
            enable_cache=settings.enable_cache,
            fields_cache_ttl=settings.fields_cache_ttl,
            search_cache_size=settings.search_cache_size,
        )

        oa_client = OACitationsClient(
            api_key=settings.uspto_ecitation_api_key,
            base_url=settings.uspto_base_url,
            rate_limit=settings.request_rate_limit,
            timeout=settings.api_timeout,
            enable_cache=settings.enable_cache,
            fields_cache_ttl=settings.fields_cache_ttl,
            search_cache_size=settings.search_cache_size,
        )

        # Load field manager from project root (consistent with other MCPs)
        config_path = Path(__file__).parent.parent.parent / "field_configs.yaml"
        field_manager = FieldManager(config_path)

        # Initialize service layers
        citation_service = CitationService(api_client, field_manager)
        oa_citation_service = OACitationService(oa_client)


@mcp.tool(annotations={"defer_loading": True, "readOnlyHint": True})
async def get_available_fields() -> Dict[str, Any]:  # no UI view — utility tool
    """Get all searchable fields from USPTO Enriched Citation API.

    Use for: Field discovery, query syntax validation, understanding data structure.
    Returns: Complete field list with descriptions and types.

    For field selection strategies and Solr/Lucene syntax examples, use citations_get_guidance(section='fields').
    """
    try:
        initialize_services()
        fields = await api_client.get_fields()
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


@mcp.tool(app=AppConfig(resource_uri=_CITATION_RESULTS_URI), annotations={"defer_loading": False, "readOnlyHint": True})
async def search_citations_minimal(
    criteria: str = "",
    rows: int = 50,
    start: int = 0,
    applicant_name: Optional[str] = None,
    application_number: Optional[str] = None,
    patent_number: Optional[str] = None,
    tech_center: Optional[str] = None,
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
    examiner_cited: Optional[bool] = None,
    art_unit: Optional[str] = None,
    fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Minimal citation search for discovery (90-95% context reduction).

    Use for high-volume pattern discovery before detailed analysis.
    Essential 8 fields: application, publication, art unit, citation ID, category, tech center, date, examiner indicator.

    Solr/Lucene Query Examples:
    - Field search: criteria='groupArtUnitNumber:2854'
    - Date range: criteria='officeActionDate:[2017-10-01 TO *]'
    - Boolean: criteria='citationCategoryCode:X AND techCenter:2100'
    - Wildcard: criteria='citedDocumentIdentifier:US*'
    - Combined: criteria='groupArtUnitNumber:2854 AND officeActionDate:[2023-01-01 TO 2023-12-31]'

    Ultra-minimal mode: Pass custom fields list for 99% token reduction (2-3 fields only).
    Example: fields=['citedDocumentIdentifier', 'patentApplicationNumber'] for PFW integration.

    Date handling: Office action dates available from 2017-10-01 forward. For application-based searches,
    use date_start='2015-01-01' to account for 1-2 year lag between filing and first office action.
    Example: date_start='2015-01-01', date_end='2024-12-31' covers all available office actions.

    Note: Returns citation metadata only. For actual office action documents, use get_citation_details
    (for specific citation) then PFW MCP 2-step workflow (see get_citation_details docstring).

    For complex workflows and cross-MCP integration, use citations_get_guidance(section).
    Quick reference: 'fields' section for Solr syntax, 'workflows_pfw' for PFW integration.
    """
    # Set request context for tracking
    with RequestContext() as request_id:
        try:
            initialize_services()
            if criteria and len(criteria) > MAX_QUERY_LENGTH:
                return format_error_response(
                    f"Query too long (max {MAX_QUERY_LENGTH} characters)", 400
                )
            if rows > MAX_MINIMAL_SEARCH_ROWS:
                return format_error_response(
                    f"Max {MAX_MINIMAL_SEARCH_ROWS} rows for minimal search", 400
                )

            # Build query using parameter object
            query_params = QueryParameters(
                criteria=criteria,
                applicant_name=applicant_name,
                application_number=application_number,
                patent_number=patent_number,
                tech_center=tech_center,
                date_start=date_start,
                date_end=date_end,
                examiner_cited=examiner_cited,
                art_unit=art_unit,
            )
            result = build_query(query_params)
            query, params, warnings = result.query, result.params_used, result.warnings

            # Use custom fields if provided, otherwise use preset minimal fields
            use_fields = (
                fields
                if fields is not None
                else field_manager.get_fields("citations_minimal")
            )
            result = await api_client.search_records(query, start, rows, use_fields)

            if "error" in result:
                return result

            # Apply field filtering using centralized smart filter
            filtered = field_manager.filter_response_smart(
                result,
                field_set_name="citations_minimal" if fields is None else None,
                custom_fields=fields,
            )
            filtered["query_info"] = {
                "constructed_query": query,
                "parameters": params,
                "tier": "minimal" if fields is None else "ultra-minimal",
                "custom_fields": fields if fields is not None else None,
                "field_count": len(use_fields),
                "cross_mcp": citation_service._get_cross_mcp_links(filtered),
                "request_id": request_id,  # Include request ID for tracking
            }
            if warnings:
                filtered["warnings"] = warnings
            filtered["guidance"] = {
                "next_steps": [
                    "Filter results and use search_citations_balanced for 10-20 important citations",
                    "Extract IDs for cross-MCP integration (PFW/PTAB)",
                ]
            }

            return filtered
        except ValueError as e:
            # Log validation failure for security monitoring
            security_logger.query_validation_failure(
                query=query if 'query' in locals() else criteria,
                reason=str(e),
                severity="medium"
            )
            return format_error_response("Invalid search parameters", 400, exception=e)
        except Exception as e:
            # Log API error for monitoring
            security_logger.api_error(
                endpoint="search_citations_minimal",
                error_code=500,
                error_type=type(e).__name__
            )
            return format_error_response("Search failed", 500, exception=e)


@mcp.tool(app=AppConfig(resource_uri=_CITATION_RESULTS_URI), annotations={"defer_loading": True, "readOnlyHint": True})
async def search_citations_balanced(
    criteria: str = "",
    rows: int = 20,
    start: int = 0,
    applicant_name: Optional[str] = None,
    application_number: Optional[str] = None,
    patent_number: Optional[str] = None,
    tech_center: Optional[str] = None,
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
    decision_type: Optional[str] = None,
    category_code: Optional[str] = None,
    examiner_cited: Optional[bool] = None,
    art_unit: Optional[str] = None,
    fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Balanced citation search for analysis (80-85% context reduction).

    Use after minimal search for detailed study of selected citations (10-20 results).
    18 fields including passages, claims, office action category.

    Solr/Lucene Query Examples:
    - Field search: criteria='examinerNameText:"Smith, John"'
    - Date range: criteria='officeActionDate:[2023-01-01 TO 2023-12-31]'
    - Boolean: criteria='(citationCategoryCode:X OR citationCategoryCode:Y) AND techCenter:2100'
    - Phrase: criteria='firstApplicantNameText:"Tesla Motors"'
    - Complex: criteria='groupArtUnitNumber:2854 AND citationCategoryCode:X AND officeActionDate:[2020-01-01 TO *]'

    Ultra-minimal mode: Pass custom fields list for 99% token reduction (2-3 fields only).
    Example: fields=['citedDocumentIdentifier', 'citationCategoryCode', 'passageLocationText']

    Date handling: Office action dates available from 2017-10-01 forward. For application-based searches,
    use date_start='2015-01-01' to account for 1-2 year lag between filing and first office action.
    Example: date_start='2015-01-01', date_end='2024-12-31' covers all available office actions.

    Convenience parameters (balanced mode only):
    - decision_type: Office action type — use "CTNF" (non-final rejection) or "CTFR" (final rejection)
    - category_code: Citation relevance code — X (anticipatory §102/103), Y (combined §103), A (background)
    - examiner_cited: Boolean filter for examiner-cited references (true/false)
    - art_unit: Group art unit number (e.g., '2128', '3600')

    Note: Returns citation metadata only. For actual office action documents, use get_citation_details
    (for specific citation) then PFW MCP 2-step workflow (see get_citation_details docstring).

    For complex workflows and cross-MCP integration, use citations_get_guidance(section).
    Quick reference: 'fields' section for Solr syntax, 'workflows_pfw'/'workflows_ptab'/'workflows_fpd' for integration patterns.
    """
    try:
        initialize_services()
        if criteria and len(criteria) > MAX_QUERY_LENGTH:
            return format_error_response(
                f"Query too long (max {MAX_QUERY_LENGTH} characters)", 400
            )
        if rows > 50:
            return format_error_response("Max 50 rows for balanced search", 400)

        # Build query using parameter object
        query_params = QueryParameters(
            criteria=criteria,
            applicant_name=applicant_name,
            application_number=application_number,
            patent_number=patent_number,
            tech_center=tech_center,
            date_start=date_start,
            date_end=date_end,
            decision_type=decision_type,
            category_code=category_code,
            examiner_cited=examiner_cited,
            art_unit=art_unit,
        )
        result = build_query(query_params)
        query, params, warnings = result.query, result.params_used, result.warnings

        # Use custom fields if provided, otherwise use preset balanced fields
        use_fields = (
            fields
            if fields is not None
            else field_manager.get_fields("citations_balanced")
        )
        result = await api_client.search_records(query, start, rows, use_fields)

        if "error" in result:
            return result

        # Apply field filtering using centralized smart filter
        filtered = field_manager.filter_response_smart(
            result,
            field_set_name="citations_balanced" if fields is None else None,
            custom_fields=fields,
        )
        filtered["query_info"] = {
            "constructed_query": query,
            "parameters": params,
            "tier": "balanced" if fields is None else "ultra-minimal",
            "custom_fields": fields if fields is not None else None,
            "field_count": len(use_fields),
        }
        if warnings:
            filtered["warnings"] = warnings
        filtered["guidance"] = {
            "analysis_ready": True,
            "passage_analysis": len(
                [
                    d
                    for d in filtered.get("response", {}).get("docs", [])
                    if d.get("passageLocationText")
                ]
            ),
            "next_steps": [
                "Use get_citation_details for 1-5 important citations",
                "Cross-reference with PFW using patentApplicationNumber",
            ],
        }

        return filtered
    except ValueError as e:
        return format_error_response("Invalid search parameters", 400, exception=e)
    except Exception as e:
        return format_error_response("Search failed", 500, exception=e)


@mcp.tool(annotations={"defer_loading": True, "readOnlyHint": True})
async def get_citation_details(
    citation_id: str, include_context: bool = True
) -> Dict[str, Any]:
    """Get complete details for specific citation by ID.

    Use for deep analysis of strategically important citations.
    Full record with all fields and complete citing context.

    ⚠️ IMPORTANT: Returns citation METADATA only, NOT actual documents.

    2-STEP PFW MCP WORKFLOW:
    Step 1: pfw_get_application_documents(app_number='{app_number}', document_code='CTNF', limit=20)

    Document Code Decoder:
    - CTNF: Non-Final Office Action (where most citations appear — start here)
    - CTFR: Final Office Action Rejection
    - NOA: Notice of Allowance
    - 892: Examiner's Search Strategy & Citations List
    - IDS: Applicant's Information Disclosure Statement

    Step 2a (LLM analysis): pfw_get_document_content(app_number, document_identifier) → Extract text for analysis
    Step 2b (User download): pfw_get_document_download(app_number, document_identifier) → PDF download link

    For complete cross-MCP workflows, use citations_get_guidance(section='workflows_pfw') for detailed integration patterns.
    """
    try:
        initialize_services()
        if not citation_id:
            return format_error_response("Citation ID required", 400)

        result = await citation_service.get_details(citation_id, include_context)

        # Add LLM guidance for document retrieval via PFW MCP
        # patentApplicationNumber is nested inside result["citation"], not at the top level
        citation_doc = result.get("citation", {}) if result else {}
        if result and citation_doc.get("patentApplicationNumber"):
            app_number = citation_doc.get("patentApplicationNumber", "")
            oa_category = citation_doc.get("officeActionCategory", "")
            # Map officeActionCategory to PFW document_code
            doc_code_map = {"CTNF": "CTNF", "CTFR": "CTFR"}
            suggested_doc_code = doc_code_map.get(oa_category, "CTNF")
            result["pfw_document_retrieval_guidance"] = {
                "notice": "⚠️ This is citation METADATA only. To get actual documents, use PFW MCP (2-step process):",
                "suggested_document_code": suggested_doc_code,
                "step_1_get_documents": f"pfw_get_application_documents(app_number='{app_number}', document_code='{suggested_doc_code}', limit=20)",
                "common_citation_documents": {
                    "CTNF": "Non-Final Office Action (where this citation most likely appears — start here)",
                    "CTFR": "Final Office Action Rejection",
                    "NOA": "Notice of Allowance (citation overcame or not used)",
                    "892": "Examiner's Search Strategy & Citations List",
                    "IDS": "Applicant's Information Disclosure Statement",
                },
                "step_2_options": {
                    "for_llm_analysis": f"pfw_get_document_content(app_number='{app_number}', document_identifier='{{from_step_1}}') → Extract text to answer user questions",
                    "for_user_download": f"pfw_get_document_download(app_number='{app_number}', document_identifier='{{from_step_1}}') → PDF download link",
                },
                "example_workflow_analysis": f"""
# When user asks "What did the examiner say?" or wants citation context:
docs = pfw_get_application_documents(app_number='{app_number}', document_code='{suggested_doc_code}', limit=20)
content = pfw_get_document_content(app_number='{app_number}', document_identifier=docs['documents'][0]['documentIdentifier'])
# Analyze content and respond to user question
""",
                "example_workflow_download": f"""
# When user says "Get me the office action" or wants to review themselves:
docs = pfw_get_application_documents(app_number='{app_number}', document_code='{suggested_doc_code}', limit=20)
download = pfw_get_document_download(app_number='{app_number}', document_identifier=docs['documents'][0]['documentIdentifier'])
# Present as: **📁 [Download Office Action]({{download['proxy_download_url']}})**
""",
                "alternative_xml_retrieval": f"""
# Alternative: Patent XML (rare for citation workflows, use document retrieval above instead)
# If you need patent claims/abstract for prior art comparison:
xml_data = pfw_get_patent_or_application_xml(
    application_number='{app_number}',
    include_fields=['claims', 'abstract'],  # Select only needed fields
    include_raw_xml=False  # ⭐ CRITICAL: 91-99% token reduction (saves ~45KB)
)
# Note: Document retrieval (above) is preferred for citation context and examiner reasoning
""",
            }

        return result
    except Exception as e:
        return format_error_response("Details retrieval failed", 500, exception=e)


@mcp.tool(annotations={"defer_loading": True, "readOnlyHint": True})
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
        initialize_services()
        if not query:
            return format_error_response("Query required", 400)

        result = await citation_service.validate_and_optimize_query(query, field_set)
        return result
    except Exception as e:
        return format_error_response("Validation failed", 500, exception=e)


@mcp.tool(app=AppConfig(resource_uri=_STATISTICS_URI), annotations={"defer_loading": True, "readOnlyHint": True})
async def get_citation_statistics(
    criteria: str = "",
    stats_fields: List[str] = ["decisionTypeCode", "citationCategoryCode"],
) -> Dict[str, Any]:
    """Get database statistics and aggregations for strategic planning."""
    try:
        initialize_services()
        result = await citation_service.get_statistics(criteria)
        return result
    except Exception as e:
        return format_error_response("Statistics retrieval failed", 500, exception=e)


@mcp.tool(annotations={"defer_loading": False, "readOnlyHint": True})
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
        from .config import tool_reflections

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


# =============================================================================
# OFFICE ACTION CITATIONS TOOLS (v2 API)
# =============================================================================


@mcp.tool(app=AppConfig(resource_uri=_OA_CITATIONS_URI), annotations={"defer_loading": False, "readOnlyHint": True})
async def search_oa_citations_minimal(
    criteria: str = "",
    rows: int = 50,
    start: int = 0,
    application_number: Optional[str] = None,
    tech_center: Optional[str] = None,
    art_unit: Optional[str] = None,
    examiner_cited: Optional[bool] = None,
    fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Search Office Action Citations (v2) for high-volume discovery (7 key fields).

    OA Citations v2 covers raw citation lists extracted from Form PTO-892 (examiner) and
    Form PTO-1449 (applicant) filed from 2017-10-01 forward. Less AI-processed than Enriched
    Citations but broader coverage and faster for bulk application lookups.

    Key fields returned: patentApplicationNumber, groupArtUnitNumber, techCenter,
    referenceIdentifier, actionTypeCategory, examinerCitedReferenceIndicator, createDateTime.

    Solr/Lucene Query Examples:
    - By application: criteria='patentApplicationNumber:16751234'
    - By tech center: criteria='techCenter:2100'
    - By art unit: criteria='groupArtUnitNumber:2854'
    - Examiner-cited only: criteria='examinerCitedReferenceIndicator:true'
    - Combined: criteria='techCenter:1700 AND examinerCitedReferenceIndicator:true'

    Use search_oa_citations_balanced for full 16-field detail on selected results.
    For AI-enriched data (passage locations, claim mapping), use search_citations_minimal.
    """
    try:
        initialize_services()

        if rows > MAX_MINIMAL_SEARCH_ROWS:
            return format_error_response(f"Max {MAX_MINIMAL_SEARCH_ROWS} rows for minimal search", 400)

        # Build criteria string from convenience params
        parts = []
        if criteria:
            try:
                validate_lucene_syntax(criteria)
            except ValueError as e:
                return format_error_response(f"Invalid criteria: {e}", 400)
            parts.append(f"({criteria})")
        if application_number:
            clean = validate_string_param(application_number, 20)
            if clean:
                parts.append(f"patentApplicationNumber:{clean}")
        if tech_center:
            clean = validate_string_param(tech_center, 10)
            if clean:
                parts.append(f"techCenter:{clean}")
        if art_unit:
            clean = validate_string_param(art_unit, 10)
            if clean:
                parts.append(f"groupArtUnitNumber:{clean}")
        if examiner_cited is not None:
            parts.append(f"examinerCitedReferenceIndicator:{str(examiner_cited).lower()}")

        if not parts:
            return format_error_response("At least one search criterion required", 400)

        query = " AND ".join(parts)
        result = await oa_citation_service.search_minimal(query, start, rows, fields)

        if "error" in result:
            return result

        result["query_info"] = {
            "constructed_query": query,
            "tier": "minimal" if fields is None else "custom",
            "api": "oa_citations_v2",
        }
        result["guidance"] = {
            "next_steps": [
                "Use search_oa_citations_balanced for full details on selected results",
                "Cross-reference with search_citations_minimal for AI-enriched passage data",
                "Use application numbers with PFW MCP for prosecution documents",
            ]
        }
        return result

    except ValueError as e:
        return format_error_response("Invalid search parameters", 400, exception=e)
    except Exception as e:
        return format_error_response("OA Citations search failed", 500, exception=e)


@mcp.tool(app=AppConfig(resource_uri=_OA_CITATIONS_URI), annotations={"defer_loading": True, "readOnlyHint": True})
async def search_oa_citations_balanced(
    criteria: str = "",
    rows: int = 25,
    start: int = 0,
    application_number: Optional[str] = None,
    tech_center: Optional[str] = None,
    art_unit: Optional[str] = None,
    examiner_cited: Optional[bool] = None,
    fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Search Office Action Citations (v2) with all 16 available fields.

    Use after search_oa_citations_minimal for detailed analysis of selected applications.
    All fields: patentApplicationNumber, groupArtUnitNumber, techCenter, referenceIdentifier,
    parsedReferenceIdentifier, actionTypeCategory, legalSectionCode, examinerCitedReferenceIndicator,
    applicantCitedExaminerReferenceIndicator, officeActionCitationReferenceIndicator,
    workGroup, paragraphNumber, createDateTime, createUserIdentifier, obsoleteDocumentIdentifier, id.

    OA Citations v2 data: 2017-10-01 to 30 days prior to current date.
    """
    try:
        initialize_services()

        if rows > 50:
            return format_error_response("Max 50 rows for balanced OA Citations search", 400)

        parts = []
        if criteria:
            try:
                validate_lucene_syntax(criteria)
            except ValueError as e:
                return format_error_response(f"Invalid criteria: {e}", 400)
            parts.append(f"({criteria})")
        if application_number:
            clean = validate_string_param(application_number, 20)
            if clean:
                parts.append(f"patentApplicationNumber:{clean}")
        if tech_center:
            clean = validate_string_param(tech_center, 10)
            if clean:
                parts.append(f"techCenter:{clean}")
        if art_unit:
            clean = validate_string_param(art_unit, 10)
            if clean:
                parts.append(f"groupArtUnitNumber:{clean}")
        if examiner_cited is not None:
            parts.append(f"examinerCitedReferenceIndicator:{str(examiner_cited).lower()}")

        if not parts:
            return format_error_response("At least one search criterion required", 400)

        query = " AND ".join(parts)
        result = await oa_citation_service.search_balanced(query, start, rows, fields)

        if "error" in result:
            return result

        result["query_info"] = {
            "constructed_query": query,
            "tier": "balanced" if fields is None else "custom",
            "api": "oa_citations_v2",
        }
        return result

    except ValueError as e:
        return format_error_response("Invalid search parameters", 400, exception=e)
    except Exception as e:
        return format_error_response("OA Citations search failed", 500, exception=e)


@mcp.tool(annotations={"defer_loading": True, "readOnlyHint": True})
async def get_oa_citation_fields() -> Dict[str, Any]:
    """Get all searchable fields from the USPTO Office Action Citations API v2.

    Returns the complete field list for building Lucene queries against the OA Citations dataset.
    OA Citations v2 is the simpler counterpart to the AI-enriched citations — it provides
    raw citation data from Form 892 and Form 1449 office actions.
    """
    try:
        initialize_services()
        fields = await oa_citation_service.get_fields()
        return {
            "status": "success",
            "api": "oa_citations_v2",
            "fields": fields.get("fields", []),
            "note": "OA Citations v2 — raw 892/1449 citation data, 2017-10-01 forward",
        }
    except Exception as e:
        return format_error_response("OA Citation field retrieval failed", 500, exception=e)


# =============================================================================
# PROMPT TEMPLATES
# =============================================================================
# All comprehensive prompt templates have been moved to src/uspto_enriched_citation_mcp/prompts/
# and are registered via the register_prompts(mcp) call after mcp initialization.
#
# Available prompts:
# - enhanced_examiner_behavior_intelligence_PFW_PTAB_FPD
# - technology_citation_landscape_PFW
# - patent_citation_analysis
# - art_unit_citation_assessment
# - litigation_citation_research_PFW_PTAB
#
# See prompts/__init__.py for full documentation.
# =============================================================================


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    """
    Health check endpoint for reverse proxy / Docker deployments.

    NOTE: This endpoint is intentionally unauthenticated to support
    load balancer health probes and container orchestration (Kubernetes,
    Docker Compose, etc.). It returns only a static "OK" response and
    does not expose any sensitive data. Rate limiting is applied globally
    via the RateLimiter.
    """
    from starlette.responses import PlainTextResponse
    return PlainTextResponse("OK")


def main():
    """Synchronous entry point for console scripts.

    Transport is controlled by environment variables:
      FASTMCP_TRANSPORT=http   → HTTP mode (required for MCP Apps)
      FASTMCP_HOST=0.0.0.0     → bind address (HTTP mode only)
      FASTMCP_PORT=8000         → port (HTTP mode only)
      CORS_EXTRA_ORIGIN=https://  → additional CORS origin for reverse proxy

    Default: stdio (Claude Desktop / Claude Code compatible)
    """
    logger.info("Starting USPTO Enriched Citation MCP server...")
    initialize_services()
    logger.info("Progressive disclosure enabled - use minimal searches first")

    transport = os.getenv("FASTMCP_TRANSPORT", "stdio")

    if transport == "http":
        settings = get_settings()

        # SECURITY: Reject non-HTTPS base URLs — API key is sent as X-API-KEY header
        if settings.uspto_base_url.startswith("http://"):
            logger.error(
                "HTTP USPTO_BASE_URL rejected in FASTMCP_TRANSPORT=http mode: "
                "API key would be transmitted without TLS encryption. "
                "Set USPTO_BASE_URL to https://api.uspto.gov or use FASTMCP_TRANSPORT=stdio."
            )
            raise ValueError(
                "FASTMCP_TRANSPORT=http requires USPTO_BASE_URL to use HTTPS. "
                "Got: " + settings.uspto_base_url
            )

        host = settings.http_host
        port = settings.http_port

        # Build CORS origins list
        origins = ["http://localhost:8080", "http://127.0.0.1:8080"]
        if settings.cors_extra_origin:
            # SECURITY: Validate CORS origin to prevent injection of arbitrary origins
            import re
            if not re.match(r"^https?://[a-zA-Z0-9.\-]+(:[0-9]+)?$", settings.cors_extra_origin):
                raise ValueError(
                    f"CORS_EXTRA_ORIGIN must be a valid HTTP/HTTPS URL, got: {settings.cors_extra_origin}"
                )
            origins.append(settings.cors_extra_origin)
            logger.info(f"CORS: added extra origin {settings.cors_extra_origin}")

        class APIKeyAuthMiddleware:
            """Validates X-API-KEY header on all non-health requests in HTTP mode.

            Checks against INTERNAL_AUTH_SECRET (the shared cross-MCP secret),
            not the external USPTO API key.  Health endpoint is intentionally
            open for load balancer probes.
            """
            def __init__(self, app):
                self.app = app

            async def __call__(self, scope, receive, send):
                if scope["type"] != "http":
                    await self.app(scope, receive, send)
                    return
                from starlette.requests import Request
                request = Request(scope, receive)
                if request.url.path == "/health":
                    await self.app(scope, receive, send)
                    return
                key = request.headers.get("x-api-key")
                from .shared_secure_storage import get_internal_auth_secret as _get_secret
                import secrets as _secrets
                expected = (
                    _get_secret()
                    or os.environ.get("INTERNAL_AUTH_SECRET")
                )
                if not expected:
                    from starlette.responses import JSONResponse
                    response = JSONResponse({"error": "Server misconfigured: INTERNAL_AUTH_SECRET not set"}, status_code=500)
                    await response(scope, receive, send)
                    return
                if not key or not _secrets.compare_digest(key, expected):
                    from starlette.responses import JSONResponse
                    response = JSONResponse({"error": "Unauthorized"}, status_code=401)
                    await response(scope, receive, send)
                    return
                await self.app(scope, receive, send)

        class SecurityHeadersMiddleware:
            """Adds browser security headers to all HTTP responses."""
            def __init__(self, app):
                self.app = app

            async def __call__(self, scope, receive, send):
                if scope["type"] != "http":
                    await self.app(scope, receive, send)
                    return

                _SECURITY_HEADERS = [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
                    (
                        b"content-security-policy",
                        b"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
                    ),
                ]

                async def patched_send(message):
                    if message["type"] == "http.response.start":
                        headers = list(message.get("headers", []))
                        headers.extend(_SECURITY_HEADERS)
                        message = {**message, "headers": headers}
                    await send(message)

                await self.app(scope, receive, patched_send)

        from starlette.middleware.cors import CORSMiddleware
        import uvicorn
        # Middleware stack (outermost first): SecurityHeaders → APIKeyAuth → CORS → mcp app
        # Security headers wrap everything so they appear on 401 responses too.
        app = SecurityHeadersMiddleware(
            APIKeyAuthMiddleware(
                CORSMiddleware(
                    mcp.http_app(),
                    allow_origins=origins,
                    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
                    # X-API-KEY removed from allow_headers — auth is enforced via
                    # APIKeyAuthMiddleware, not CORS; reduces browser key exposure
                    allow_headers=["Content-Type", "Accept", "Mcp-Session-Id"],
                    expose_headers=["Mcp-Session-Id"],
                )
            )
        )
        logger.info(f"Starting HTTP transport on {host}:{port}")
        uvicorn.run(app, host=host, port=port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
