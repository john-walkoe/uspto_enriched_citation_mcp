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
            warning = (
                f"Warning: Office action dates before {API_DATA_CUTOFF_DATE_STRING} "
                f"not available in API. Using {clean_date} may return no results."
            )

    return clean_date, warning


def validate_string_param(param: str, max_length: int = 200) -> Optional[str]:
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
        # officeActionCategory is the populated field: CTNF (non-final) or CTFR (final)
        parts.append(f"officeActionCategory:{decision_type}")
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
