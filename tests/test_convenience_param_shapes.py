"""Convenience parameters must not smuggle Lucene syntax past the whitelist.

`criteria` goes through validate_lucene_syntax (field whitelist, wildcard cap,
nesting cap, range cap); the convenience parameters were concatenated raw, so
`application_number="1 OR techCenter:*"` emitted
`patentApplicationNumber:1 OR techCenter:*` — 17 characters, no forbidden
character (S-12).
"""

import pytest

from uspto_enriched_citation_mcp.tools.oa import search_oa_citations_minimal
from uspto_enriched_citation_mcp.tools.search import search_citations_minimal
from uspto_enriched_citation_mcp.util.query_builder import (
    QueryParameters,
    build_query,
    validate_string_param,
)

_EMPTY = {"response": {"numFound": 0, "start": 0, "docs": []}}

SMUGGLED = [
    "1 OR techCenter:*",
    "16816197 OR *:*",
    "2100 AND groupArtUnitNumber:2854",
    "*",
    "[1 TO 99999999]",
    "(2100)",
]


@pytest.mark.parametrize("value", SMUGGLED)
def test_build_query_rejects_smuggled_syntax_in_application_number(value):
    with pytest.raises(ValueError):
        build_query(QueryParameters(application_number=value))


@pytest.mark.parametrize("value", SMUGGLED)
def test_build_query_rejects_smuggled_syntax_in_tech_center(value):
    with pytest.raises(ValueError):
        build_query(QueryParameters(tech_center=value))


def test_plain_values_still_build():
    result = build_query(
        QueryParameters(
            application_number="16816197",
            tech_center="2100",
            art_unit="2854",
            category_code="X",
            decision_type="CTNF",
        )
    )
    assert "patentApplicationNumber:16816197" in result.query
    assert "techCenter:2100" in result.query
    assert "groupArtUnitNumber:2854" in result.query


def test_applicant_name_stays_free_text_but_quoted():
    result = build_query(QueryParameters(applicant_name="Acme Corp. of Delaware"))
    assert 'firstApplicantName:"Acme Corp. of Delaware"' in result.query


def test_validate_string_param_without_a_pattern_is_unchanged():
    assert validate_string_param("anything goes here", 200) == "anything goes here"


@pytest.mark.asyncio
@pytest.mark.parametrize("value", SMUGGLED)
async def test_enriched_tool_returns_400_for_smuggled_syntax(mock_runtime, value):
    mock_runtime.api_client.search_records.return_value = dict(_EMPTY)
    result = await search_citations_minimal(application_number=value)
    assert result["status"] == "error"
    assert result["code"] == 400
    mock_runtime.api_client.search_records.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("value", SMUGGLED)
async def test_oa_tool_returns_400_for_smuggled_syntax(mock_runtime, value):
    mock_runtime.oa_client.search_records.return_value = dict(_EMPTY)
    result = await search_oa_citations_minimal(application_number=value)
    assert result["status"] == "error"
    assert result["code"] == 400
    mock_runtime.oa_client.search_records.assert_not_called()
