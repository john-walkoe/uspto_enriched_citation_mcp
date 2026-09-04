"""Office Action Citations (v2 API) tools."""

from typing import Any, Callable, Dict, List, Optional

from fastmcp.apps import AppConfig

from .. import runtime
from ..app_uris import OA_CITATIONS_URI
from ..config.constants import MAX_BALANCED_SEARCH_ROWS, MAX_MINIMAL_SEARCH_ROWS
from ..shared.error_utils import format_error_response
from ..shared.injection_scan import RETRIEVED_TEXT_NOTE, scan_hits
from ..util.query_builder import (
    ALNUM_PARAM,
    DIGITS_PARAM,
    validate_string_param,
)
from ..util.query_validator import OA_VALID_FIELDS, validate_lucene_syntax
from ..util.request_context import RequestContext
from ..util.security_logger import get_security_logger
from ._shared import (
    PFW_LINK_HINT,
    _apply_resolution,
    _attach_patent_number_resolution,
    _build_query_info,
    _resolve_patent_number,
    run_with_deadline,
    validate_pagination,
)

security_logger = get_security_logger()


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

    # Same structural shapes as the enriched builder: these three parameters
    # were concatenated raw into the query while only `criteria` went through
    # the Lucene whitelist (S-12).
    for value, max_len, field_name, pattern in (
        (application_number, 20, "patentApplicationNumber", DIGITS_PARAM),
        (tech_center, 10, "techCenter", ALNUM_PARAM),
        (art_unit, 10, "groupArtUnitNumber", ALNUM_PARAM),
    ):
        if value:
            clean = validate_string_param(value, max_len, pattern)
            if clean:
                parts.append(f"{field_name}:{clean}")

    if examiner_cited is not None:
        parts.append(f"examinerCitedReferenceIndicator:{str(examiner_cited).lower()}")

    if not parts:
        return None, format_error_response("At least one search criterion required", 400)

    return " AND ".join(parts), None


async def _run_oa_search(**kwargs) -> Dict[str, Any]:
    """Public entry: the shared body under the whole-tool deadline."""
    return await run_with_deadline(
        lambda: _run_oa_search_body(**kwargs), "OA Citations search"
    )


async def _run_oa_search_body(
    *,
    tool_name: str,
    tier: str,
    service_method: str,
    max_rows: int,
    max_rows_message: str,
    criteria: str,
    rows: int,
    start: int,
    application_number: Optional[str],
    tech_center: Optional[str],
    art_unit: Optional[str],
    examiner_cited: Optional[bool],
    fields: Optional[List[str]],
    patent_number: Optional[str],
    guidance: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]],
) -> Dict[str, Any]:
    """Everything the two OA tiers do identically.

    The tiers were two copies of this body; only the minimal one set a
    guidance block, and neither opened a `RequestContext` or emitted security
    events. One implementation means a fix to the envelope lands on both.
    """
    with RequestContext():
        query = ""
        try:
            runtime.initialize_services()

            rows_error = validate_pagination(rows, start, max_rows, max_rows_message)
            if rows_error is not None:
                return rows_error

            # This lane has no patent-number field, so a granted patent number
            # is crosswalked into the application-number clause before the
            # query builds.
            resolution, resolution_error = await _resolve_patent_number(
                patent_number, application_number, allow_publication=False
            )
            if resolution_error is not None:
                return resolution_error
            _, application_number = _apply_resolution(
                resolution, patent_number, application_number
            )

            # Build criteria string from convenience params
            query, error = _build_oa_query(
                criteria, application_number, tech_center, art_unit, examiner_cited
            )
            if error is not None:
                return error
            search = getattr(runtime.oa_citation_service, service_method)
            result = await search(query, start, rows, fields)

            if "error" in result:
                # E-5: the upstream payload is USPTO's shape, not this
                # server's — no status, no code, no request_id — and it used
                # to be returned to the caller verbatim. Re-envelope it so
                # every failure the caller sees has one shape. The upstream
                # text is carried through as the message.
                return format_error_response(
                    str(result.get("error")) or "Upstream API error", 502
                )

            result["query_info"] = _build_query_info(
                query,
                tier=tier if fields is None else "custom",
                api="oa_citations_v2",
            )
            _attach_patent_number_resolution(result, resolution)
            result["pfw_link"] = PFW_LINK_HINT
            if guidance is not None:
                result["guidance"] = guidance(result)
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
            security_logger.query_validation_failure(
                query=query or criteria,
                reason=str(e),
                severity="medium",
            )
            return format_error_response("Invalid search parameters", 400, exception=e)
        except Exception as e:
            security_logger.api_error(
                endpoint=tool_name,
                error_code=500,
                error_type=type(e).__name__,
            )
            return format_error_response(
                "OA Citations search failed", 500, exception=e
            )


def _oa_minimal_guidance(_result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "next_steps": [
            "Use Citations_search_oa_citations_balanced for full details on selected results",
            "Cross-reference with Citations_search_citations_minimal for AI-enriched passage data",
            "Use application numbers with PFW MCP for prosecution documents",
        ]
    }


async def search_oa_citations_minimal(
    criteria: str = "",
    rows: int = 50,
    start: int = 0,
    application_number: Optional[str] = None,
    tech_center: Optional[str] = None,
    art_unit: Optional[str] = None,
    examiner_cited: Optional[bool] = None,
    fields: Optional[List[str]] = None,
    patent_number: Optional[str] = None,
) -> Dict[str, Any]:
    """Search Office Action Citations (v2) for high-volume discovery (8 key fields).

    OA Citations v2 is the raw citation list transcribed from Form PTO-892 (examiner) and
    Form PTO-1449 (applicant IDS). Usually broader than the enriched lane in bulk
    (measured TC2100: 4.87M vs 4.32M records), with most of the surplus being applicant
    IDS references — but NOT a superset: on a given application the enriched lane can
    return more (measured: app 12849948 returns 4 here vs 8 enriched). For any
    completeness-sensitive question, run BOTH lanes and union the results.

    ⚠️ APPLICANT-CITED (1449/IDS) COVERAGE IS PARTIAL. This lane is documented upstream as
    transcribing Form 892 AND Form 1449, but on IDS-heavy files it returns close to what
    the examiner applied and little else, in every era. Measured against the patents' own
    References Cited pages (union of BOTH lanes):
      US 7,971,071 -> 5 of 91
      US 9,496,922 -> 1 of 251
      US 9,135,462 -> 0 of about 620 (both lanes return zero)
      US 11,656,067 -> 3 of 15, prosecuted 2021-2023 INSIDE the documented window, and
        all three are the examiner's own double-patenting family citations, none of them
        the twelve references a later IPR petition relied on.
    Treat a reference's absence here as NO evidence that the applicant did not disclose
    it, and never present a count from this lane as the applicant's full IDS. For a
    complete 1449 record, read the IDS documents themselves through the PFW MCP.

    Key fields returned: patentApplicationNumber, groupArtUnitNumber, techCenter,
    referenceIdentifier, parsedReferenceIdentifier, actionTypeCategory,
    examinerCitedReferenceIndicator, createDateTime.
    The OA API ignores `fl`, so this set is enforced client-side — the tier really does
    return only these eight. The PFW hand-off is stated once on the response
    envelope as `pfw_link`, not repeated on every row. legalSectionCode and
    paragraphNumber are NOT here; use the balanced tier or pass an explicit `fields`
    list for them.

    CROSS-LANE JOIN KEY: every row carries `referenceKey`, the normalised reference
    identifier, and it is the ONLY correct key for unioning this lane with the enriched
    lane. The two lanes write the same reference differently: on app 12849948 this lane's
    parsedReferenceIdentifier reads '20060075466' while the enriched
    citedDocumentIdentifier reads 'US 2006/0075466 A1'. Joining those two raw fields finds
    zero overlap on every application; the true answer there is four references in both
    lanes. `referenceKey` is digits only (a leading US, spaces, slashes, hyphens and the
    kind code stripped, series markers such as RE kept), derived from
    parsedReferenceIdentifier first and the raw referenceIdentifier second, and carried on
    both lanes at every tier including a custom `fields` list. It is null on a row whose
    identifier does not reduce to a document number, which is an unjoinable row rather
    than a missing one.

    Solr/Lucene Query Examples:
    - By application: criteria='patentApplicationNumber:18180061'
    - By tech center: criteria='techCenter:2100'
    - By art unit: criteria='groupArtUnitNumber:2854'
    - Examiner-cited only: criteria='examinerCitedReferenceIndicator:true'
    - Statutory basis (OA-ONLY capability): criteria='techCenter:2100 AND legalSectionCode:103'
    - Where a patent was cited: criteria='parsedReferenceIdentifier:9280610'

    ⚠️ NO DATE FIELD. officeActionDate does not exist here and returns HTTP 400 — the
    index already IS the 2017-10-01+ window, so omit any date clause.
    createDateTime is an ETL load stamp, NOT the office action date — never present it
    as prosecution chronology.

    ⚠️ publicationNumber IN `criteria` IS A DELIBERATE 400 HERE, AND THAT IS A FEATURE.
    The raw upstream API does not reject that field: it answers HTTP 200 with
    numFound 0, which reads exactly like "this patent was never cited" and is silently
    wrong. This server refuses the clause instead so the mistake is visible. Use the
    `patent_number` parameter, which crosswalks a granted patent number to the
    application serial this index does hold, or query parsedReferenceIdentifier to find
    where a patent was CITED.

    ⚠️ Use parsedReferenceIdentifier (normalized) rather than referenceIdentifier for
    reference lookups — the raw string format varies for the same patent.

    IDENTIFIERS: `application_number` is the APPLICATION serial. This index has no
    patent-number field (publicationNumber returns HTTP 400), so `patent_number` is
    crosswalked here: pass a GRANTED patent number (7-8 digits; commas, spaces and a
    `US` prefix accepted) and it is resolved to its application serial with one USPTO ODP
    applications-search call, then queried as `patentApplicationNumber`. The response
    reports the mapping in `patent_number_resolution` {input, interpreted_as,
    resolved_application_number, source}. An 11-digit pre-grant publication number is
    refused here (use Citations_search_citations_minimal for those), an unresolvable
    number is a 400 naming the accepted forms, and a `patent_number` that disagrees with
    a supplied `application_number` is a 400 rather than a query that can only return zero.

    Use Citations_search_oa_citations_balanced for full 16-field detail (adds
    legalSectionCode, paragraphNumber, parsedReferenceIdentifier).
    For passage locations, claim mapping, NPL flags, or date filtering, use
    Citations_search_citations_minimal — and run it alongside this tool by default.
    Coverage: USPTO documents both APIs as office actions mailed 2017-10-01 to ~30 days
    ago; in practice both have been observed serving older records, so do not treat an
    older application as out of scope without querying.
    Routing detail: Citations_get_guidance(section='oa_citations').
    """
    return await _run_oa_search(
        tool_name="search_oa_citations_minimal",
        tier="minimal",
        service_method="search_minimal",
        max_rows=MAX_MINIMAL_SEARCH_ROWS,
        max_rows_message=f"Max {MAX_MINIMAL_SEARCH_ROWS} rows for minimal search",
        criteria=criteria,
        rows=rows,
        start=start,
        application_number=application_number,
        tech_center=tech_center,
        art_unit=art_unit,
        examiner_cited=examiner_cited,
        fields=fields,
        patent_number=patent_number,
        guidance=_oa_minimal_guidance,
    )


async def search_oa_citations_balanced(
    criteria: str = "",
    rows: int = 25,
    start: int = 0,
    application_number: Optional[str] = None,
    tech_center: Optional[str] = None,
    art_unit: Optional[str] = None,
    examiner_cited: Optional[bool] = None,
    fields: Optional[List[str]] = None,
    patent_number: Optional[str] = None,
) -> Dict[str, Any]:
    """Search Office Action Citations (v2) with all 16 available fields.
    Prior art cited against an application, Form 892, Form 1449, IDS references, 102 103 112 statutory basis, action type, paragraph number.

    Use after Citations_search_oa_citations_minimal for detailed analysis of selected applications.
    All fields: patentApplicationNumber, groupArtUnitNumber, techCenter, referenceIdentifier,
    parsedReferenceIdentifier, actionTypeCategory, legalSectionCode, examinerCitedReferenceIndicator,
    applicantCitedExaminerReferenceIndicator, officeActionCitationReferenceIndicator,
    workGroup, paragraphNumber, createDateTime, createUserIdentifier, obsoleteDocumentIdentifier, id.

    This tier is where the OA-only analytical fields live: legalSectionCode (102/103/112
    statutory basis) and actionTypeCategory ('rejected') have no equivalent in the
    enriched lane, and paragraphNumber locates the citation within the office action.

    ⚠️ APPLICANT-CITED (1449/IDS) COVERAGE IS PARTIAL. This lane is documented upstream as
    transcribing Form 892 AND Form 1449, but on IDS-heavy files it returns close to what
    the examiner applied and little else, in every era. Measured against the patents' own
    References Cited pages (union of BOTH lanes):
      US 7,971,071 -> 5 of 91
      US 9,496,922 -> 1 of 251
      US 9,135,462 -> 0 of about 620
      US 11,656,067 -> 3 of 15, prosecuted 2021-2023 INSIDE the documented window
    A reference's absence here is NO evidence that the applicant did not disclose it, and
    a count from this lane is not the applicant's full IDS. For a complete 1449 record,
    read the IDS documents through the PFW MCP.

    CROSS-LANE JOIN KEY: every row carries `referenceKey`, the normalised reference
    identifier, and it is the ONLY correct key for unioning this lane with the enriched
    lane. On app 12849948 this lane's parsedReferenceIdentifier reads '20060075466' while
    the enriched citedDocumentIdentifier reads 'US 2006/0075466 A1'; joining those two raw
    fields finds zero overlap on every application, when the true answer there is four
    references in both lanes. `referenceKey` is digits only (a leading US, spaces, slashes,
    hyphens and the kind code stripped, series markers such as RE kept) and is carried on
    both lanes at every tier. It is null on a row whose identifier does not reduce to a
    document number.

    OA Citations v2 documented window: office actions mailed 2017-10-01 to ~30 days
    prior to today (older records have been observed in practice). No office-action date
    field exists — do not add an officeActionDate clause (HTTP 400).

    ⚠️ publicationNumber IN `criteria` IS A DELIBERATE 400 HERE, AND THAT IS A FEATURE.
    The raw upstream API answers that field with HTTP 200 and numFound 0, which reads as
    "this patent was never cited" and is silently wrong. This server refuses the clause so
    the mistake is visible. Use the `patent_number` parameter for the subject patent, or
    parsedReferenceIdentifier to find where a patent was CITED.

    IDENTIFIERS: `application_number` is the APPLICATION serial. This index has no
    patent-number field (publicationNumber returns HTTP 400), so `patent_number` is
    crosswalked here: pass a GRANTED patent number (7-8 digits; commas, spaces and a
    `US` prefix accepted) and it is resolved to its application serial with one USPTO ODP
    applications-search call, then queried as `patentApplicationNumber`. The response
    reports the mapping in `patent_number_resolution` {input, interpreted_as,
    resolved_application_number, source}. An 11-digit pre-grant publication number is
    refused here (use Citations_search_citations_balanced for those), an unresolvable
    number is a 400 naming the accepted forms, and a `patent_number` that disagrees with
    a supplied `application_number` is a 400 rather than a query that can only return zero.
    """
    return await _run_oa_search(
        tool_name="search_oa_citations_balanced",
        tier="balanced",
        service_method="search_balanced",
        max_rows=MAX_BALANCED_SEARCH_ROWS,
        max_rows_message=(
            f"Max {MAX_BALANCED_SEARCH_ROWS} rows for balanced OA Citations search"
        ),
        criteria=criteria,
        rows=rows,
        start=start,
        application_number=application_number,
        tech_center=tech_center,
        art_unit=art_unit,
        examiner_cited=examiner_cited,
        fields=fields,
        patent_number=patent_number,
        guidance=None,
    )


async def get_oa_citation_fields() -> Dict[str, Any]:
    """Get all searchable fields from the USPTO Office Action Citations API v2.
    Fields, available fields, columns, schema, what can I query, field names, query syntax for the OA citations lane.

    Returns the complete field list for building Lucene queries against the OA Citations dataset.
    OA Citations v2 is the simpler counterpart to the AI-enriched citations — it provides
    raw citation data from Form 892 and Form 1449 office actions.
    """
    with RequestContext():
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
            security_logger.api_error(
                endpoint="get_oa_citation_fields",
                error_code=500,
                error_type=type(e).__name__,
            )
            return format_error_response(
                "OA Citation field retrieval failed", 500, exception=e
            )


def register(mcp) -> None:
    """Register the three OA Citations tools (Citations_-prefixed display
    names; function names/schemas unchanged)."""
    mcp.tool(
        name="Citations_search_oa_citations_minimal",
        app=AppConfig(resource_uri=OA_CITATIONS_URI),
        annotations={"defer_loading": False, "readOnlyHint": True},
    )(search_oa_citations_minimal)
    mcp.tool(
        name="Citations_search_oa_citations_balanced",
        app=AppConfig(resource_uri=OA_CITATIONS_URI),
        annotations={"defer_loading": True, "readOnlyHint": True},
    )(search_oa_citations_balanced)
    mcp.tool(
        name="Citations_get_oa_citation_fields",
        annotations={"defer_loading": True, "readOnlyHint": True},
    )(get_oa_citation_fields)
