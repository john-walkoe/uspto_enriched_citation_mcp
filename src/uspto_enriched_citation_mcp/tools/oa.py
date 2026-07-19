"""Office Action Citations (v2 API) tools."""

from typing import Any, Dict, List, Optional

from fastmcp.apps import AppConfig

from .. import runtime
from ..app_uris import OA_CITATIONS_URI
from ..config.constants import MAX_BALANCED_SEARCH_ROWS, MAX_MINIMAL_SEARCH_ROWS
from ..shared.error_utils import format_error_response
from ..shared.injection_scan import RETRIEVED_TEXT_NOTE, scan_hits
from ..util.query_builder import validate_string_param
from ..util.query_validator import OA_VALID_FIELDS, validate_lucene_syntax
from ._shared import _build_query_info


def _validate_oa_criteria_clause(
    criteria: str,
) -> "tuple[Optional[str], Optional[Dict[str, Any]]]":
    """Validate the free-form `criteria` string and wrap it in parens for the
    combined query. Returns (clause, None) on success, or (None, error_response)
    if the criteria fails Lucene syntax validation.
    """
    # OA v2 has its own field schema (legalSectionCode, actionTypeCategory,
    # ...) — the default whitelist is the enriched v3 set and would reject
    # legitimate OA queries.
    is_valid, validation_msg = validate_lucene_syntax(
        criteria, valid_fields=OA_VALID_FIELDS
    )
    if not is_valid:
        return None, format_error_response(f"Invalid criteria: {validation_msg}", 400)
    return f"({criteria})", None


def _build_oa_query(
    criteria: str,
    application_number: Optional[str],
    tech_center: Optional[str],
    art_unit: Optional[str],
    examiner_cited: Optional[bool],
) -> "tuple[Optional[str], Optional[Dict[str, Any]]]":
    """Build the combined Lucene query string for the OA Citations search tools
    from `criteria` plus convenience params (shared by search_oa_citations_minimal
    and search_oa_citations_balanced).

    Returns (query, None) on success, or (None, error_response) if validation
    fails or no search criterion was supplied.
    """
    parts = []
    if criteria:
        clause, error = _validate_oa_criteria_clause(criteria)
        if error is not None:
            return None, error
        parts.append(clause)

    for value, max_len, field_name in (
        (application_number, 20, "patentApplicationNumber"),
        (tech_center, 10, "techCenter"),
        (art_unit, 10, "groupArtUnitNumber"),
    ):
        if value:
            clean = validate_string_param(value, max_len)
            if clean:
                parts.append(f"{field_name}:{clean}")

    if examiner_cited is not None:
        parts.append(f"examinerCitedReferenceIndicator:{str(examiner_cited).lower()}")

    if not parts:
        return None, format_error_response("At least one search criterion required", 400)

    return " AND ".join(parts), None


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
        runtime.initialize_services()

        if rows > MAX_MINIMAL_SEARCH_ROWS:
            return format_error_response(f"Max {MAX_MINIMAL_SEARCH_ROWS} rows for minimal search", 400)

        # Build criteria string from convenience params
        query, error = _build_oa_query(criteria, application_number, tech_center, art_unit, examiner_cited)
        if error is not None:
            return error
        result = await runtime.oa_citation_service.search_minimal(query, start, rows, fields)

        if "error" in result:
            return result

        result["query_info"] = _build_query_info(
            query,
            tier="minimal" if fields is None else "custom",
            api="oa_citations_v2",
        )
        result["guidance"] = {
            "next_steps": [
                "Use search_oa_citations_balanced for full details on selected results",
                "Cross-reference with search_citations_minimal for AI-enriched passage data",
                "Use application numbers with PFW MCP for prosecution documents",
            ]
        }
        # Provenance labeling + detection-only injection scan (kind labels
        # only, key ABSENT when clean). OA v2 fields are structured, but a
        # custom `fields` list keeps the envelope shape, so the scan stays
        # wired for consistency with the v3 search tools.
        result["provenance_note"] = RETRIEVED_TEXT_NOTE
        injection = scan_hits(result.get("response", {}).get("docs", []))
        if injection:
            result["injection_scan"] = injection
        return result

    except ValueError as e:
        return format_error_response("Invalid search parameters", 400, exception=e)
    except Exception as e:
        return format_error_response("OA Citations search failed", 500, exception=e)


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
        runtime.initialize_services()

        if rows > MAX_BALANCED_SEARCH_ROWS:
            return format_error_response(
                f"Max {MAX_BALANCED_SEARCH_ROWS} rows for balanced OA Citations search", 400
            )

        query, error = _build_oa_query(criteria, application_number, tech_center, art_unit, examiner_cited)
        if error is not None:
            return error
        result = await runtime.oa_citation_service.search_balanced(query, start, rows, fields)

        if "error" in result:
            return result

        result["query_info"] = _build_query_info(
            query,
            tier="balanced" if fields is None else "custom",
            api="oa_citations_v2",
        )
        # Provenance labeling + detection-only injection scan (kind labels
        # only, key ABSENT when clean) — same wiring as the minimal tier.
        result["provenance_note"] = RETRIEVED_TEXT_NOTE
        injection = scan_hits(result.get("response", {}).get("docs", []))
        if injection:
            result["injection_scan"] = injection
        return result

    except ValueError as e:
        return format_error_response("Invalid search parameters", 400, exception=e)
    except Exception as e:
        return format_error_response("OA Citations search failed", 500, exception=e)


async def get_oa_citation_fields() -> Dict[str, Any]:
    """Get all searchable fields from the USPTO Office Action Citations API v2.

    Returns the complete field list for building Lucene queries against the OA Citations dataset.
    OA Citations v2 is the simpler counterpart to the AI-enriched citations — it provides
    raw citation data from Form 892 and Form 1449 office actions.
    """
    try:
        runtime.initialize_services()
        fields = await runtime.oa_citation_service.get_fields()
        return {
            "status": "success",
            "api": "oa_citations_v2",
            "fields": fields.get("fields", []),
            "note": "OA Citations v2 — raw 892/1449 citation data, 2017-10-01 forward",
        }
    except Exception as e:
        return format_error_response("OA Citation field retrieval failed", 500, exception=e)


def register(mcp) -> None:
    """Register the three OA Citations tools (names/schemas unchanged)."""
    mcp.tool(
        app=AppConfig(resource_uri=OA_CITATIONS_URI),
        annotations={"defer_loading": False, "readOnlyHint": True},
    )(search_oa_citations_minimal)
    mcp.tool(
        app=AppConfig(resource_uri=OA_CITATIONS_URI),
        annotations={"defer_loading": True, "readOnlyHint": True},
    )(search_oa_citations_balanced)
    mcp.tool(annotations={"defer_loading": True, "readOnlyHint": True})(get_oa_citation_fields)
