"""Enriched Citations (v3) search tools — minimal/balanced tiers."""

from typing import Any, Dict, List, Optional

from fastmcp.apps import AppConfig

from .. import runtime
from ..app_uris import CITATION_RESULTS_URI
from ..config.constants import (
    MAX_BALANCED_SEARCH_ROWS,
    MAX_MINIMAL_SEARCH_ROWS,
    MAX_QUERY_LENGTH,
)
from ..shared.error_utils import format_error_response
from ..shared.injection_scan import RETRIEVED_TEXT_NOTE, scan_hits
from ..util.query_builder import QueryParameters, build_query
from ..util.query_validator import validate_lucene_syntax
from ..util.request_context import RequestContext
from ..util.security_logger import get_security_logger
from ._shared import _build_query_info

security_logger = get_security_logger()


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
            runtime.initialize_services()
            if criteria and len(criteria) > MAX_QUERY_LENGTH:
                return format_error_response(
                    f"Query too long (max {MAX_QUERY_LENGTH} characters)", 400
                )
            if criteria:
                is_valid, validation_msg = validate_lucene_syntax(criteria)
                if not is_valid:
                    return format_error_response(validation_msg, 400)
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
                else runtime.field_manager.get_fields("citations_minimal")
            )
            result = await runtime.api_client.search_records(query, start, rows, use_fields)

            if "error" in result:
                return result

            # Apply field filtering using centralized smart filter
            filtered = runtime.field_manager.filter_response_smart(
                result,
                field_set_name="citations_minimal" if fields is None else None,
                custom_fields=fields,
            )
            filtered["query_info"] = _build_query_info(
                query,
                tier="minimal" if fields is None else "ultra-minimal",
                parameters=params,
                custom_fields=fields,
                field_count=len(use_fields),
                extra={
                    "cross_mcp": runtime.citation_service._get_cross_mcp_links(filtered),
                    "request_id": request_id,  # Include request ID for tracking
                },
            )
            if warnings:
                filtered["warnings"] = warnings
            filtered["guidance"] = {
                "next_steps": [
                    "Filter results and use search_citations_balanced for 10-20 important citations",
                    "Extract IDs for cross-MCP integration (PFW/PTAB)",
                ]
            }
            # Provenance labeling + detection-only injection scan (kind labels
            # only, key ABSENT when clean; text is never modified).
            filtered["provenance_note"] = RETRIEVED_TEXT_NOTE
            injection = scan_hits(filtered.get("response", {}).get("docs", []))
            if injection:
                filtered["injection_scan"] = injection

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
        runtime.initialize_services()
        if criteria and len(criteria) > MAX_QUERY_LENGTH:
            return format_error_response(
                f"Query too long (max {MAX_QUERY_LENGTH} characters)", 400
            )
        if criteria:
            is_valid, validation_msg = validate_lucene_syntax(criteria)
            if not is_valid:
                return format_error_response(validation_msg, 400)
        if rows > MAX_BALANCED_SEARCH_ROWS:
            return format_error_response(
                f"Max {MAX_BALANCED_SEARCH_ROWS} rows for balanced search", 400
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
            else runtime.field_manager.get_fields("citations_balanced")
        )
        result = await runtime.api_client.search_records(query, start, rows, use_fields)

        if "error" in result:
            return result

        # Apply field filtering using centralized smart filter
        filtered = runtime.field_manager.filter_response_smart(
            result,
            field_set_name="citations_balanced" if fields is None else None,
            custom_fields=fields,
        )
        filtered["query_info"] = _build_query_info(
            query,
            tier="balanced" if fields is None else "ultra-minimal",
            parameters=params,
            custom_fields=fields,
            field_count=len(use_fields),
        )
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
        # Provenance labeling + detection-only injection scan (kind labels
        # only, key ABSENT when clean; text is never modified).
        filtered["provenance_note"] = RETRIEVED_TEXT_NOTE
        injection = scan_hits(filtered.get("response", {}).get("docs", []))
        if injection:
            filtered["injection_scan"] = injection

        return filtered
    except ValueError as e:
        return format_error_response("Invalid search parameters", 400, exception=e)
    except Exception as e:
        return format_error_response("Search failed", 500, exception=e)


def register(mcp) -> None:
    """Register the two enriched-citation search tools (names/schemas unchanged)."""
    mcp.tool(
        app=AppConfig(resource_uri=CITATION_RESULTS_URI),
        annotations={"defer_loading": False, "readOnlyHint": True},
    )(search_citations_minimal)
    mcp.tool(
        app=AppConfig(resource_uri=CITATION_RESULTS_URI),
        annotations={"defer_loading": True, "readOnlyHint": True},
    )(search_citations_balanced)
