"""
Lucene query building utilities for USPTO Citation MCP tools.

Provides QueryParameters, QueryBuildResult, and build_query for constructing
validated Lucene queries from convenience parameters.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, NamedTuple, Optional

from ..api.field_constants import QueryFieldNames
from ..config.constants import (
    API_DATA_CUTOFF_DATE_STRING,
    API_DATA_START_DATE,
)


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

    `warnings` carries hard problems with the query; `coverage_notes` carries
    soft, advisory context about what the index is likely to hold. The two are
    kept apart deliberately — a coverage note must never read to an agent as a
    reason to abandon a query.

    RESERVED: nothing appends to `warnings` today. Its only writer was the
    pre-2017 refusal, removed 2026-08-30 in favor of coverage_notes, so the
    `warnings` key is currently unreachable in the response envelope. The
    field and its plumbing stay because the channel is part of the documented
    contract and a future hard-problem check belongs in it; the absence is
    pinned by tests/test_convenience_parameters.py (R-14 / D-5).
    """

    query: str
    params_used: Dict[str, str]
    warnings: List[str]
    coverage_notes: List[str]


def validate_date_range(
    date_str: str, field_name: str = "officeActionDate"
) -> tuple[Optional[str], Optional[str]]:
    """Validate date string in YYYY-MM-DD format.

    Returns: (validated_date, coverage_note)

    A date below the documented 2017-10-01 floor is NOT refused and NOT
    warned about. USPTO documents both citation APIs as 2017-10-01 forward,
    but the live enriched index serves records well below it (measured
    2026-08-30: 1,252,784 TC2100 records in the 2010-2015 band, with
    officeActionDate values verified against PFW document dates back to
    2010-2012). The old warning — "not available in API ... may return no
    results" — contradicted the response it was attached to and told an
    agent mid-task that data it was about to receive did not exist. A soft
    coverage note is returned instead.
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

    # Advisory only — see the docstring. The query is served either way.
    note = None
    if field_name == "officeActionDate":
        if date_obj < API_DATA_START_DATE:
            note = (
                f"Coverage before {API_DATA_CUTOFF_DATE_STRING} is officially "
                f"undocumented; the index does serve older office actions, but "
                f"results may be sparse."
            )

    return clean_date, note


# Structural shapes for the convenience parameters. Each says what its own
# name claims, which is what closes S-12: `criteria` goes through
# validate_lucene_syntax (field whitelist, wildcard cap, nesting cap, range
# cap) and the convenience parameters did not, so a 17-character value like
# `application_number="1 OR techCenter:*"` was concatenated raw as
# `patentApplicationNumber:1 OR techCenter:*`. None of these shapes admits a
# colon, space, parenthesis, bracket, wildcard or a bare AND/OR/NOT, so the
# assembled clause cannot carry Lucene syntax the whitelist never saw.
DIGITS_PARAM = r"^[0-9]{1,20}$"
ALNUM_PARAM = r"^[A-Za-z0-9]{1,15}$"
CODE_PARAM = r"^[A-Za-z0-9_\-]{1,50}$"


def validate_string_param(
    param: str, max_length: int = 200, pattern: Optional[str] = None
) -> Optional[str]:
    """Validate and clean string parameter.

    `pattern`, when given, is a full-match structural shape for this
    parameter. Omit it only for genuinely free text (an applicant name),
    which is emitted as a quoted phrase and so cannot carry syntax out.
    """
    clean = param.strip() if param else None
    if not clean:
        return None

    if len(clean) > max_length:
        raise ValueError(f"Parameter too long (max {max_length} chars)")

    if re.search(r'[<>"\\]', clean):
        raise ValueError("Invalid characters in parameter")

    if pattern is not None and not re.fullmatch(pattern, clean):
        raise ValueError(
            "Invalid parameter value. Put Lucene syntax in `criteria`, which "
            "is validated against the field whitelist; the convenience "
            "parameters take a plain value only."
        )

    return clean


def _build_date_range_clause(
    date_start: Optional[str], date_end: Optional[str]
) -> "tuple[Optional[str], Optional[str], List[str]]":
    """Build the officeActionDate range clause from date_start/date_end.

    Returns (clause, params_used_value, coverage_notes):
    - clause: the Lucene range clause, or None if neither date is set or both
      resolve to an unbounded "*" range.
    - params_used_value: the "start TO end" string to record in params_used
      (mirrors clause — None when clause is None).
    - coverage_notes: any soft coverage notes raised while validating the dates.
    """
    notes: List[str] = []
    if not (date_start or date_end):
        return None, None, notes

    start_date, start_note = (
        validate_date_range(date_start) if date_start else (None, None)
    )
    end_date, end_note = (
        validate_date_range(date_end) if date_end else (None, None)
    )

    if start_note:
        notes.append(start_note)
    if end_note:
        notes.append(end_note)

    start = start_date or "*"
    end = end_date or "*"
    if start != "*" or end != "*":
        clause = f"{QueryFieldNames.OFFICE_ACTION_DATE}:[{start} TO {end}]"
        return clause, f"{start} TO {end}", notes

    return None, None, notes


def _append_simple_clause(
    parts: List[str],
    params_used: Dict[str, str],
    raw_value: Optional[str],
    max_length: int,
    field_name: str,
    param_key: str,
    quoted: bool = False,
    pattern: Optional[str] = None,
) -> None:
    """Validate `raw_value` and, if non-empty, append its Lucene clause to
    `parts` and record the cleaned value under `param_key` in `params_used`.
    No-op if the value is empty/None after validation.
    """
    clean = validate_string_param(raw_value, max_length, pattern)
    if not clean:
        return
    value = f'"{clean}"' if quoted else clean
    parts.append(f"{field_name}:{value}")
    params_used[param_key] = clean


def build_query(params: QueryParameters) -> QueryBuildResult:
    """Build Lucene query from parameters.

    Args:
        params: Query parameters consolidated in a single object

    Returns:
        QueryBuildResult with query string, params used, warnings, and
        soft coverage notes
    """
    parts: List[str] = []
    params_used: Dict[str, str] = {}
    warnings: List[str] = []
    coverage_notes: List[str] = []

    if params.criteria:
        parts.append(f"({params.criteria})")
        params_used["base_criteria"] = params.criteria

    _append_simple_clause(
        parts, params_used, params.applicant_name, 200,
        QueryFieldNames.FIRST_APPLICANT_NAME, "applicant_name", quoted=True,
    )

    _append_simple_clause(
        parts, params_used, params.application_number, 20,
        QueryFieldNames.APPLICATION_NUMBER, "application_number",
        pattern=DIGITS_PARAM,
    )

    _append_simple_clause(
        parts, params_used, params.patent_number, 15,
        QueryFieldNames.PUBLICATION_NUMBER, "patent_number",
        pattern=ALNUM_PARAM,
    )

    _append_simple_clause(
        parts, params_used, params.tech_center, 10,
        QueryFieldNames.TECH_CENTER, "tech_center",
        pattern=ALNUM_PARAM,
    )

    date_clause, date_range_used, date_notes = _build_date_range_clause(
        params.date_start, params.date_end
    )
    coverage_notes.extend(date_notes)
    if date_clause:
        parts.append(date_clause)
        params_used["date_range"] = date_range_used

    # officeActionCategory is the populated field: CTNF (non-final) or CTFR (final)
    _append_simple_clause(
        parts, params_used, params.decision_type, 50,
        "officeActionCategory", "decision_type",
        pattern=CODE_PARAM,
    )

    _append_simple_clause(
        parts, params_used, params.category_code, 10,
        QueryFieldNames.CITATION_CATEGORY, "category_code",
        pattern=ALNUM_PARAM,
    )

    if params.examiner_cited is not None:
        # Convert boolean to lowercase string for Lucene query
        examiner_cited_str = str(params.examiner_cited).lower()
        parts.append(f"{QueryFieldNames.EXAMINER_CITED}:{examiner_cited_str}")
        params_used["examiner_cited"] = examiner_cited_str

    _append_simple_clause(
        parts, params_used, params.art_unit, 10,
        QueryFieldNames.GROUP_ART_UNIT, "art_unit",
        pattern=ALNUM_PARAM,
    )

    if not parts:
        raise ValueError("At least one search criterion required")

    query = " AND ".join(parts)
    return QueryBuildResult(query, params_used, warnings, coverage_notes)
