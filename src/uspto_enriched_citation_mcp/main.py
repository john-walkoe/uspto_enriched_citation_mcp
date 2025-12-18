"""USPTO Enriched Citation MCP Server"""

import sys
from typing import Dict, List, Optional, Any, NamedTuple
from dataclasses import dataclass
from mcp.server.fastmcp import FastMCP
import structlog

# Local imports
from .api.enriched_client import EnrichedCitationClient
from .api.field_constants import QueryFieldNames
from .config.field_manager import FieldManager, DEFAULT_MINIMAL_FIELDS as MINIMAL_FIELDS, DEFAULT_BALANCED_FIELDS as BALANCED_FIELDS
from .config.settings import get_settings
from .config.feature_flags import get_feature_flags
from .config.constants import (
    API_DATA_START_DATE,
    API_DATA_CUTOFF_DATE_STRING,
    MAX_MINIMAL_SEARCH_ROWS,
)
from .shared.error_utils import format_error_response
from .services.citation_service import CitationService
from .util.request_context import RequestContext
from .util.security_logger import get_security_logger
from pathlib import Path
from datetime import datetime
import re


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

mcp = FastMCP("uspto-enriched-citation-mcp")

# Register all prompt templates with the MCP server
# This must be done AFTER mcp is created to avoid circular imports
from .prompts import register_prompts  # noqa: E402
register_prompts(mcp)

# Global variables for lazy initialization
api_client = None
field_manager = None
citation_service = None


def initialize_services():
    """Initialize services with settings."""
    global api_client, field_manager, citation_service

    if api_client is None:
        settings = get_settings()

        # Initialize feature flags
        feature_flags_path = None
        if settings.feature_flags_path:
            feature_flags_path = Path(settings.feature_flags_path)
        else:
            # Try default location (project root)
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

        # Load field manager from project root (consistent with other MCPs)
        config_path = Path(__file__).parent.parent.parent / "field_configs.yaml"
        field_manager = FieldManager(config_path)

        # Initialize service layer
        citation_service = CitationService(api_client, field_manager)


# =============================================================================
# DATA STRUCTURES FOR QUERY BUILDING
# =============================================================================


@dataclass
class QueryParameters:
    """Parameters for building Lucene query.

    Consolidates query building parameters into a single object for better
    maintainability and extensibility.
    """
    criteria: str = ""
    applicant_name: Optional[str] = None
    application_number: Optional[str] = None
    patent_number: Optional[str] = None
    tech_center: Optional[str] = None
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    decision_type: Optional[str] = None
    category_code: Optional[str] = None
    examiner_cited: Optional[bool] = None
    art_unit: Optional[str] = None


class QueryBuildResult(NamedTuple):
    """Result of query building operation.

    Provides self-documenting return values for build_query function.
    """
    query: str
    params_used: Dict[str, str]
    warnings: List[str]


def validate_date_range(
    date_str: str, field_name: str = "officeActionDate"
) -> tuple[Optional[str], Optional[str]]:
    """Validate date string in YYYY-MM-DD format.

    Returns: (validated_date, warning_message)
    Warning if office action date is before 2017-10-01 (API data availability cutoff).
    """
    if not date_str:
        return None, None

    clean_date = date_str.strip()
    if not clean_date:
        return None, None

    if not re.match(r"^\d{4}-\d{2}-\d{2}$", clean_date):
        raise ValueError("Date must be in YYYY-MM-DD format")

    try:
        date_obj = datetime.strptime(clean_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Invalid date format")

    # Check against API cutoff for office action dates
    warning = None
    if field_name == "officeActionDate":
        if date_obj < API_DATA_START_DATE:
            warning = f"Warning: Office action dates before {API_DATA_CUTOFF_DATE_STRING} not available in API. Using {clean_date} may return no results."

    return clean_date, warning


def validate_string_param(param: str, max_length: int = 200) -> str:
    """Validate and clean string parameter."""
    clean = param.strip() if param else None
    if not clean:
        return None

    if len(clean) > max_length:
        raise ValueError(f"Parameter too long (max {max_length} chars)")

    if re.search(r'[<>"\\]', clean):
        raise ValueError("Invalid characters in parameter")

    return clean


def build_query(params: QueryParameters) -> QueryBuildResult:
    """Build Lucene query from parameters.

    Args:
        params: Query parameters consolidated in a single object

    Returns:
        QueryBuildResult with query string, params used, and warnings
    """
    parts = []
    params_used = {}
    warnings = []

    if params.criteria:
        parts.append(f"({params.criteria})")
        params_used["base_criteria"] = params.criteria

    if applicant_name := validate_string_param(params.applicant_name):
        parts.append(f'{QueryFieldNames.FIRST_APPLICANT_NAME}:"{applicant_name}"')
        params_used["applicant_name"] = applicant_name

    if application_number := validate_string_param(params.application_number, 20):
        parts.append(f"{QueryFieldNames.APPLICATION_NUMBER}:{application_number}")
        params_used["application_number"] = application_number

    if patent_number := validate_string_param(params.patent_number, 15):
        parts.append(f"{QueryFieldNames.PUBLICATION_NUMBER}:{patent_number}")
        params_used["patent_number"] = patent_number

    if tech_center := validate_string_param(params.tech_center, 10):
        parts.append(f"{QueryFieldNames.TECH_CENTER}:{tech_center}")
        params_used["tech_center"] = tech_center

    if params.date_start or params.date_end:
        start_date, start_warning = (
            validate_date_range(params.date_start) if params.date_start else (None, None)
        )
        end_date, end_warning = (
            validate_date_range(params.date_end) if params.date_end else (None, None)
        )

        if start_warning:
            warnings.append(start_warning)
        if end_warning:
            warnings.append(end_warning)

        start = start_date or "*"
        end = end_date or "*"
        if start != "*" or end != "*":
            parts.append(f"{QueryFieldNames.OFFICE_ACTION_DATE}:[{start} TO {end}]")
            params_used["date_range"] = f"{start} TO {end}"

    if decision_type := validate_string_param(params.decision_type, 50):
        parts.append(f"{QueryFieldNames.DECISION_TYPE_CODE}:{decision_type}")
        params_used["decision_type"] = decision_type

    if category_code := validate_string_param(params.category_code, 10):
        parts.append(f"{QueryFieldNames.CITATION_CATEGORY}:{category_code}")
        params_used["category_code"] = category_code

    if params.examiner_cited is not None:
        # Convert boolean to lowercase string for Lucene query
        examiner_cited_str = str(params.examiner_cited).lower()
        parts.append(f"{QueryFieldNames.EXAMINER_CITED}:{examiner_cited_str}")
        params_used["examiner_cited"] = examiner_cited_str

    if art_unit := validate_string_param(params.art_unit, 10):
        parts.append(f"{QueryFieldNames.GROUP_ART_UNIT}:{art_unit}")
        params_used["art_unit"] = art_unit

    if not parts:
        raise ValueError("At least one search criterion required")

    query = " AND ".join(parts)
    return QueryBuildResult(query, params_used, warnings)


@mcp.tool()
async def get_available_fields() -> Dict[str, Any]:
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


@mcp.tool()
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


@mcp.tool()
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
    - category_code: Citation category code (e.g., '102', '103')
    - examiner_cited: Boolean filter for examiner-cited references (true/false)
    - art_unit: Group art unit number (e.g., '2128', '3600')

    Note: Returns citation metadata only. For actual office action documents, use get_citation_details
    (for specific citation) then PFW MCP 2-step workflow (see get_citation_details docstring).

    For complex workflows and cross-MCP integration, use citations_get_guidance(section).
    Quick reference: 'fields' section for Solr syntax, 'workflows_pfw'/'workflows_ptab'/'workflows_fpd' for integration patterns.
    """
    try:
        initialize_services()
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


@mcp.tool()
async def get_citation_details(
    citation_id: str, include_context: bool = True
) -> Dict[str, Any]:
    """Get complete details for specific citation by ID.

    Use for deep analysis of strategically important citations.
    Full record with all fields and complete citing context.

    ⚠️ IMPORTANT: Returns citation METADATA only, NOT actual documents.

    2-STEP PFW MCP WORKFLOW:
    Step 1: pfw_get_application_documents(app_number='{app_number}', document_code='CTFR', limit=20)

    Document Code Decoder:
    - CTFR: Non-Final Office Action (where citation appears)
    - CTNF: Final Office Action Rejection
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
        if result and "patentApplicationNumber" in result:
            app_number = result.get("patentApplicationNumber", "")
            result["pfw_document_retrieval_guidance"] = {
                "notice": "⚠️ This is citation METADATA only. To get actual documents, use PFW MCP (2-step process):",
                "step_1_get_documents": f"pfw_get_application_documents(app_number='{app_number}', document_code='CTFR', limit=20)",
                "common_citation_documents": {
                    "CTFR": "Non-Final Office Action (where this citation appears)",
                    "CTNF": "Final Office Action Rejection",
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
docs = pfw_get_application_documents(app_number='{app_number}', document_code='CTFR', limit=20)
content = pfw_get_document_content(app_number='{app_number}', document_identifier=docs['documents'][0]['documentIdentifier'])
# Analyze content and respond to user question
""",
                "example_workflow_download": f"""
# When user says "Get me the office action" or wants to review themselves:
docs = pfw_get_application_documents(app_number='{app_number}', document_code='CTFR', limit=20)
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
async def citations_get_guidance(section: str = "overview") -> str:
    """Get selective USPTO Citation guidance sections for context-efficient workflows

    🎯 QUICK REFERENCE - What section for your question?

    🔍 "Find citations by examiner/application/tech" → fields
    📄 "Understand citation categories (X/Y/NPL)" → citation_codes
    🔖 "Citation data coverage (2017+)" → data_coverage
    🤝 "PFW workflow for office action documents" → workflows_pfw
    🚩 "PTAB citation correlation" → workflows_ptab
    📊 "FPD petition citation patterns" → workflows_fpd
    🏢 "Complete lifecycle analysis" → workflows_complete
    ⚙️ "Tool guidance and parameters" → tools
    ❌ "Search errors or query issues" → errors
    💰 "Reduce API costs and optimize" → cost

    Available sections:
    - overview: Available sections and tool summary
    - workflows_pfw: Citation + PFW integration workflows
    - workflows_ptab: Citation + PTAB integration workflows
    - workflows_fpd: Citation + FPD integration workflows
    - workflows_complete: Four-MCP complete lifecycle analysis
    - citation_codes: X/Y/A/NPL category decoder and strategic guidance
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


def main():
    """Synchronous entry point for console scripts."""
    logger.info("Starting USPTO Enriched Citation MCP server...")
    initialize_services()
    logger.info("Progressive disclosure enabled - use minimal searches first")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
