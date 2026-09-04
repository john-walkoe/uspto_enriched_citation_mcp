"""Enriched Citations (v3) search tools — minimal/balanced tiers."""

from typing import Any, Callable, Dict, List, Optional

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
from ..util.reference_key import (
    ENRICHED_REFERENCE_SOURCE_FIELDS,
    attach_reference_keys,
    count_rows_without_reference,
    reference_keys_for_docs,
)
from ..util.request_context import RequestContext
from ..util.security_logger import get_security_logger
from ._shared import (
    _apply_resolution,
    _attach_patent_number_resolution,
    _attach_query_advisories,
    _build_query_info,
    _resolve_patent_number,
    run_with_deadline,
    validate_pagination,
)

security_logger = get_security_logger()


def _validate_search_input(
    criteria: str,
    rows: int,
    start: int,
    max_rows: int,
    max_rows_message: str,
) -> Optional[Dict[str, Any]]:
    """Pre-network guards shared by both enriched tiers. Returns an error
    response, or None when the arguments are acceptable. Extracted to keep
    _run_enriched_search under the C901 ceiling, the same reason
    _attach_query_advisories exists."""
    if criteria and len(criteria) > MAX_QUERY_LENGTH:
        return format_error_response(
            f"Query too long (max {MAX_QUERY_LENGTH} characters)", 400
        )
    if criteria:
        is_valid, validation_msg = validate_lucene_syntax(criteria)
        if not is_valid:
            return format_error_response(validation_msg, 400)
    return validate_pagination(rows, start, max_rows, max_rows_message)


async def _run_enriched_search(**kwargs) -> Dict[str, Any]:
    """Public entry: the shared body under the whole-tool deadline."""
    return await run_with_deadline(
        lambda: _run_enriched_search_body(**kwargs), "Search"
    )


async def _run_enriched_search_body(
    *,
    tool_name: str,
    tier: str,
    field_set: str,
    max_rows: int,
    max_rows_message: str,
    criteria: str,
    rows: int,
    start: int,
    fields: Optional[List[str]],
    patent_number: Optional[str],
    application_number: Optional[str],
    make_params: Callable[[Optional[str], Optional[str]], QueryParameters],
    guidance: Callable[[Dict[str, Any]], Dict[str, Any]],
    include_cross_mcp: bool,
) -> Dict[str, Any]:
    """Everything the two enriched tiers do identically.

    The tiers were two copies of this body and had drifted: only the minimal
    one opened a `RequestContext` (so half the enriched surface produced no
    `request_id`) and only the minimal one emitted security events. Running
    both through one implementation is what keeps that from happening again;
    the per-tier parts are the row cap, the field set, the QueryParameters
    fields and the guidance block, all passed in.
    """
    with RequestContext() as request_id:
        query = ""
        try:
            runtime.initialize_services()
            input_error = _validate_search_input(
                criteria, rows, start, max_rows, max_rows_message
            )
            if input_error is not None:
                return input_error

            # A granted patent number becomes an application-number clause; an
            # 11-digit publication number stays on publicationNumber.
            resolution, resolution_error = await _resolve_patent_number(
                patent_number, application_number
            )
            if resolution_error is not None:
                return resolution_error
            patent_number, application_number = _apply_resolution(
                resolution, patent_number, application_number
            )

            # Build query using parameter object
            built = build_query(make_params(patent_number, application_number))
            query, params = built.query, built.params_used
            warnings, coverage_notes = built.warnings, built.coverage_notes

            # Use custom fields if provided, otherwise use the tier's preset
            use_fields = (
                fields
                if fields is not None
                else runtime.field_manager.get_field_set(field_set)
            )
            result = await runtime.api_client.search_records(
                query, start, rows, use_fields
            )

            if "error" in result:
                # E-5: the upstream payload is USPTO's shape, not this
                # server's — no status, no code, no request_id — and it used
                # to be returned to the caller verbatim. Re-envelope it so
                # every failure the caller sees has one shape. The upstream
                # text is carried through as the message.
                return format_error_response(
                    str(result.get("error")) or "Upstream API error", 502
                )

            # The cross-lane join key is computed from the UNFILTERED upstream
            # docs, before the tier's field set is applied: an ultra-minimal
            # custom field list can drop both source fields, and the key would
            # then be unavailable for exactly the caller who most needs to
            # union the two lanes.
            reference_keys = reference_keys_for_docs(
                result.get("response", {}).get("docs"),
                ENRICHED_REFERENCE_SOURCE_FIELDS,
            )

            # Apply field filtering using centralized smart filter
            filtered = runtime.field_manager.filter_response_smart(
                result,
                field_set_name=field_set if fields is None else None,
                custom_fields=fields,
            )
            attach_reference_keys(
                filtered.get("response", {}).get("docs"), reference_keys
            )
            # Rows whose reference identifier is absent, null or empty (one
            # state, see util/reference_key) are counted on the envelope rather
            # than left for the caller to notice: measured 2 of 5 on 11752072,
            # 4 of 8 on 12849948 and 4 of 26 on 18407147. The key is ALWAYS
            # present, 0 included, so its absence cannot be read as "none".
            filtered["rows_without_reference_identifier"] = (
                count_rows_without_reference(reference_keys)
            )
            extra: Dict[str, Any] = {}
            if include_cross_mcp:
                extra["cross_mcp"] = runtime.citation_service.get_cross_mcp_links(
                    filtered
                )
            extra["request_id"] = request_id  # Include request ID for tracking
            filtered["query_info"] = _build_query_info(
                query,
                tier=tier if fields is None else "ultra-minimal",
                parameters=params,
                custom_fields=fields,
                field_count=len(use_fields),
                extra=extra,
            )
            _attach_patent_number_resolution(filtered, resolution)
            _attach_query_advisories(filtered, warnings, coverage_notes)
            filtered["guidance"] = guidance(filtered)
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
                query=query or criteria,
                reason=str(e),
                severity="medium",
            )
            return format_error_response("Invalid search parameters", 400, exception=e)
        except Exception as e:
            # Log API error for monitoring
            security_logger.api_error(
                endpoint=tool_name,
                error_code=500,
                error_type=type(e).__name__,
            )
            return format_error_response("Search failed", 500, exception=e)


def _minimal_guidance(_filtered: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "next_steps": [
            "Filter results and use Citations_search_citations_balanced for 10-20 important citations",
            "Extract IDs for cross-MCP integration (PFW/PTAB)",
        ]
    }


def _balanced_guidance(filtered: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "analysis_ready": True,
        "passage_analysis": len(
            [
                d
                for d in filtered.get("response", {}).get("docs", [])
                if d.get("passageLocationText")
            ]
        ),
        "next_steps": [
            "Use Citations_get_citation_details for 1-5 important citations",
            "Cross-reference with PFW using patentApplicationNumber",
        ],
    }


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

    Date handling: USPTO documents this API as office actions mailed 2017-10-01 to
    ~30 days ago. In practice ~44% of TC2100 records carry an earlier officeActionDate
    (verified against PFW document dates back to 2010-2012). Do NOT add a blanket
    officeActionDate:[2017-10-01 TO *] clause unless you specifically want the
    documented window — it discards records the index actually serves.

    Lane routing — TRY BOTH: this is the ENRICHED lane (passage locations, claim
    mapping, quality scores, NPL flag, date filtering). For completeness-sensitive
    questions also run Citations_search_oa_citations_minimal (raw 892/1449 lists,
    statutory basis, broader applicant-IDS coverage) and union the results — neither
    lane is a superset of the other.
    See Citations_get_guidance(section='oa_citations').

    CROSS-LANE JOIN KEY: every row carries `referenceKey`, the normalised reference
    identifier, and it is the ONLY correct key for unioning this lane with the OA lane.
    The two lanes write the same reference differently: on app 12849948 the OA
    parsedReferenceIdentifier reads '20060075466' while the enriched
    citedDocumentIdentifier reads 'US 2006/0075466 A1'. Joining those two raw fields
    finds zero overlap on every application; the true answer there is four references in
    both lanes. `referenceKey` is digits only (a leading US, spaces, slashes, hyphens and
    the kind code stripped, series markers such as RE kept), derived from
    publicationNumber first and citedDocumentIdentifier second, and carried on both lanes
    at every tier including a custom `fields` list.

    ROWS WITH NO REFERENCE: `referenceKey` is null when the row carries no usable
    identifier, and the response envelope reports how many such rows the page holds as
    `rows_without_reference_identifier` (always present, 0 included). An absent
    citedDocumentIdentifier key, a null one and an empty string are ONE state, not three:
    a row can carry an empty publicationNumber with the citedDocumentIdentifier key
    missing from the JSON entirely. Measured: 2 of 5 on app 11752072, 4 of 8 on 12849948,
    4 of 26 on 18407147. Those rows are real citations and must be reported as
    unresolved, never dropped.

    IDENTIFIERS: `patent_number` takes either a GRANTED patent number (7-8 digits;
    commas, spaces and a `US` prefix are accepted) or an 11-digit pre-grant publication
    number. A granted patent number is crosswalked to its application serial with one
    USPTO ODP applications-search call and queried as `patentApplicationNumber`; an
    11-digit value queries `publicationNumber` directly. The response reports which
    reading was used in `patent_number_resolution` {input, interpreted_as,
    resolved_application_number when crosswalked, source}. A number that resolves to no
    application is a 400 naming the accepted forms, not a zero-result. `application_number`
    remains the application serial; passing one that disagrees with the crosswalked patent
    number is also a 400.

    Note: Returns citation metadata only. For the office action text itself, use the PFW
    MCP's PFW_get_oa_text / PFW_get_oa_rejections (direct, no document-bag + OCR round trip).

    For complex workflows and cross-MCP integration, use Citations_get_guidance(section).
    Quick reference: 'fields' section for Solr syntax, 'workflows_pfw' for PFW integration.
    """
    return await _run_enriched_search(
        tool_name="search_citations_minimal",
        tier="minimal",
        field_set="citations_minimal",
        max_rows=MAX_MINIMAL_SEARCH_ROWS,
        max_rows_message=f"Max {MAX_MINIMAL_SEARCH_ROWS} rows for minimal search",
        criteria=criteria,
        rows=rows,
        start=start,
        fields=fields,
        patent_number=patent_number,
        application_number=application_number,
        make_params=lambda pat, app: QueryParameters(
            criteria=criteria,
            applicant_name=applicant_name,
            application_number=app,
            patent_number=pat,
            tech_center=tech_center,
            date_start=date_start,
            date_end=date_end,
            examiner_cited=examiner_cited,
            art_unit=art_unit,
        ),
        guidance=_minimal_guidance,
        include_cross_mcp=True,
    )


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
    Prior art references cited by an examiner, cited passage, column and line locator, figure, mapped claim, art unit, tech center, examiner vs applicant citation.

    Use after minimal search for detailed study of selected citations (10-20 results).
    19 fields including passages, claims, office action category.

    Solr/Lucene Query Examples:
    - Field search: criteria='groupArtUnitNumber:2854'
    - Date range: criteria='officeActionDate:[2023-01-01 TO 2023-12-31]'
    - Boolean: criteria='(citationCategoryCode:X OR citationCategoryCode:Y) AND techCenter:2100'
    - NPL only: criteria='nplIndicator:true AND techCenter:2100'
    - Complex: criteria='groupArtUnitNumber:2854 AND citationCategoryCode:X AND officeActionDate:[2020-01-01 TO *]'

    NOT searchable: examinerNameText and firstApplicantNameText do NOT exist on this API.
    Examiner queries 400; applicant queries silently return 0. Resolve examiners and
    applicants through the PFW MCP, then query citations by application number.

    Ultra-minimal mode: Pass custom fields list for 99% token reduction (2-3 fields only).
    Example: fields=['citedDocumentIdentifier', 'citationCategoryCode', 'passageLocationText']

    Date handling: documented window is office actions mailed 2017-10-01 to ~30 days
    ago, but ~44% of TC2100 records carry an earlier officeActionDate in practice. Add
    an officeActionDate:[2017-10-01 TO *] clause only when you want the documented
    window specifically. For completeness, also query the OA lane and union.

    Convenience parameters (balanced mode only):
    - decision_type: Office action type — use "CTNF" (non-final rejection) or "CTFR" (final rejection)
    - category_code: Citation relevance code — X (anticipatory §102/103), Y (combined §103), A (background)
    - examiner_cited: Boolean filter for examiner-cited references (true/false)
    - art_unit: Group art unit number (e.g., '2128', '3600')

    CROSS-LANE JOIN KEY: every row carries `referenceKey`, the normalised reference
    identifier, and it is the ONLY correct key for unioning this lane with the OA lane.
    The two lanes write the same reference differently: on app 12849948 the OA
    parsedReferenceIdentifier reads '20060075466' while the enriched
    citedDocumentIdentifier reads 'US 2006/0075466 A1'. Joining those two raw fields
    finds zero overlap on every application; the true answer there is four references in
    both lanes. `referenceKey` is digits only (a leading US, spaces, slashes, hyphens and
    the kind code stripped, series markers such as RE kept), derived from
    publicationNumber first and citedDocumentIdentifier second, and carried on both lanes
    at every tier including a custom `fields` list.

    ROWS WITH NO REFERENCE: `referenceKey` is null when the row carries no usable
    identifier, and the response envelope reports how many such rows the page holds as
    `rows_without_reference_identifier` (always present, 0 included). An absent
    citedDocumentIdentifier key, a null one and an empty string are ONE state, not three:
    a row can carry an empty publicationNumber with the citedDocumentIdentifier key
    missing from the JSON entirely. Measured: 2 of 5 on app 11752072, 4 of 8 on 12849948,
    4 of 26 on 18407147. Those rows are real citations and must be reported as
    unresolved, never dropped.

    IDENTIFIERS: `patent_number` takes either a GRANTED patent number (7-8 digits;
    commas, spaces and a `US` prefix are accepted) or an 11-digit pre-grant publication
    number. A granted patent number is crosswalked to its application serial with one
    USPTO ODP applications-search call and queried as `patentApplicationNumber`; an
    11-digit value queries `publicationNumber` directly. The response reports which
    reading was used in `patent_number_resolution` {input, interpreted_as,
    resolved_application_number when crosswalked, source}. A number that resolves to no
    application is a 400 naming the accepted forms, not a zero-result. `application_number`
    remains the application serial; passing one that disagrees with the crosswalked patent
    number is also a 400.

    Note: Returns citation metadata only. For the office action text itself, use the PFW
    MCP's PFW_get_oa_text / PFW_get_oa_rejections (direct, no document-bag + OCR round trip).

    For complex workflows and cross-MCP integration, use Citations_get_guidance(section).
    Quick reference: 'oa_citations' for OA-vs-enriched routing, 'fields' for Solr syntax,
    'workflows_pfw'/'workflows_ptab'/'workflows_fpd' for integration patterns.
    """
    return await _run_enriched_search(
        tool_name="search_citations_balanced",
        tier="balanced",
        field_set="citations_balanced",
        max_rows=MAX_BALANCED_SEARCH_ROWS,
        max_rows_message=f"Max {MAX_BALANCED_SEARCH_ROWS} rows for balanced search",
        criteria=criteria,
        rows=rows,
        start=start,
        fields=fields,
        patent_number=patent_number,
        application_number=application_number,
        make_params=lambda pat, app: QueryParameters(
            criteria=criteria,
            applicant_name=applicant_name,
            application_number=app,
            patent_number=pat,
            tech_center=tech_center,
            date_start=date_start,
            date_end=date_end,
            decision_type=decision_type,
            category_code=category_code,
            examiner_cited=examiner_cited,
            art_unit=art_unit,
        ),
        guidance=_balanced_guidance,
        include_cross_mcp=False,
    )


def register(mcp) -> None:
    """Register the two enriched-citation search tools (Citations_-prefixed
    display names; function names/schemas unchanged)."""
    mcp.tool(
        name="Citations_search_citations_minimal",
        app=AppConfig(resource_uri=CITATION_RESULTS_URI),
        annotations={"defer_loading": False, "readOnlyHint": True},
    )(search_citations_minimal)
    mcp.tool(
        name="Citations_search_citations_balanced",
        app=AppConfig(resource_uri=CITATION_RESULTS_URI),
        annotations={"defer_loading": True, "readOnlyHint": True},
    )(search_citations_balanced)
