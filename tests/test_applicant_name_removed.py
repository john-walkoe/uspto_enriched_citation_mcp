"""MCP-2 / CQ-R-1 (review 2026-09-28): `applicant_name` on the two enriched
search tools built a query against `firstApplicantName`, a field
field_configs.yaml lists under "Fields NOT Available in API v3" — so the
parameter could only ever return zero results, which reads to a model as
"no citations". No real field on this API carries applicant/assignee name
(checked against field_configs.yaml, reference/README.md and
reference/tool_guidance.md, none of which name a substitute), so the
parameter is removed rather than remapped.

These tests pin the removal so it cannot silently regress.
"""

import inspect

from uspto_enriched_citation_mcp.api.field_constants import QueryFieldNames
from uspto_enriched_citation_mcp.tools.search import (
    search_citations_balanced,
    search_citations_minimal,
)
from uspto_enriched_citation_mcp.util.query_builder import QueryParameters


def test_applicant_name_is_not_a_minimal_search_parameter():
    assert "applicant_name" not in inspect.signature(search_citations_minimal).parameters


def test_applicant_name_is_not_a_balanced_search_parameter():
    assert "applicant_name" not in inspect.signature(search_citations_balanced).parameters


def test_applicant_name_is_not_a_query_parameters_field():
    assert "applicant_name" not in inspect.signature(QueryParameters).parameters


def test_first_applicant_name_is_not_a_query_field_constant():
    """firstApplicantName is not a real field on this API; nothing should
    still build a query against it."""
    assert not hasattr(QueryFieldNames, "FIRST_APPLICANT_NAME")
