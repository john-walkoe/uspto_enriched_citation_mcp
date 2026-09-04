"""What each lane cannot do, said where the caller finds out.

Two defects from the 2026-09-03 skill-QA round:

- `Citations_get_citation_statistics` validates `criteria` against the enriched
  whitelist only, so a `legalSectionCode` clause is a 400 and there is no way
  to aggregate the OA lane. The choice made here is to DOCUMENT the limit (no
  `lane` parameter was added) and to make the 400 name the lane that holds the
  field, plus the count-it-yourself recipe in the tool docstring and guidance.
- The MCP's 400 on `publicationNumber` on the OA lane is deliberate: the raw
  upstream API answers that field with HTTP 200 and `numFound: 0`, which reads
  as "this patent was never cited". A refusal you can see beats a silent zero,
  so the message now says so.
"""

import inspect

import pytest

from uspto_enriched_citation_mcp.tools.oa import search_oa_citations_minimal
from uspto_enriched_citation_mcp.tools.statistics import get_citation_statistics
from uspto_enriched_citation_mcp.util.query_validator import (
    OA_VALID_FIELDS,
    VALID_FIELDS,
    validate_lucene_syntax,
)


class TestWrongLaneHint:
    @pytest.mark.parametrize(
        "field",
        ["legalSectionCode", "actionTypeCategory", "paragraphNumber", "workGroup"],
    )
    def test_oa_only_field_on_the_enriched_lane_names_the_oa_tools(self, field):
        is_valid, message = validate_lucene_syntax(f"techCenter:2100 AND {field}:103")
        assert is_valid is False
        assert f"Invalid field name: {field}" in message
        assert "Office Action Citations (v2) lane" in message
        assert "Citations_search_oa_citations_minimal/balanced" in message

    @pytest.mark.parametrize(
        "field", ["officeActionDate", "citationCategoryCode", "nplIndicator"]
    )
    def test_enriched_only_field_on_the_oa_lane_names_the_enriched_tools(self, field):
        is_valid, message = validate_lucene_syntax(
            f"techCenter:2100 AND {field}:X", valid_fields=OA_VALID_FIELDS
        )
        assert is_valid is False
        assert "Enriched Citations (v3) lane" in message
        assert "Citations_search_citations_minimal/balanced" in message

    def test_publication_number_on_the_oa_lane_explains_the_deliberate_400(self):
        is_valid, message = validate_lucene_syntax(
            "publicationNumber:9049188", valid_fields=OA_VALID_FIELDS
        )
        assert is_valid is False
        assert "HTTP 200" in message
        assert "numFound 0" in message
        assert "never cited" in message
        assert "`patent_number` parameter" in message

    def test_a_field_in_neither_lane_gets_no_lane_hint(self):
        """The hint must not fire on a genuine typo, or it sends the caller to
        the wrong tool."""
        is_valid, message = validate_lucene_syntax("notAField:1600")
        assert is_valid is False
        assert message == (
            "Invalid field name: notAField. Use Citations_get_available_fields "
            "tool for valid fields."
        )

    def test_the_two_whitelists_still_disagree(self):
        """The hint is only meaningful while each lane holds fields the other
        does not; this pins the premise rather than assuming it."""
        assert OA_VALID_FIELDS - VALID_FIELDS
        assert VALID_FIELDS - OA_VALID_FIELDS


class TestStatisticsIsEnrichedOnly:
    @pytest.mark.asyncio
    async def test_an_oa_only_clause_is_a_400_naming_the_oa_lane(self, mock_runtime):
        result = await get_citation_statistics(
            criteria="techCenter:2100 AND legalSectionCode:103"
        )

        assert result["status"] == "error"
        assert result["code"] == 400
        assert "legalSectionCode" in result["error"]
        assert "Citations_search_oa_citations_minimal/balanced" in result["error"]
        # No upstream call was made: the refusal is pre-network.
        assert not mock_runtime.api_client.search_citations.called

    def test_there_is_no_lane_parameter(self):
        """The documented choice. If a `lane` parameter is ever added, this
        test and the docstring have to change together."""
        params = inspect.signature(get_citation_statistics).parameters
        assert list(params) == ["criteria"]

    def test_the_docstring_states_the_limit_and_the_workaround(self):
        doc = inspect.getdoc(get_citation_statistics)
        assert "ENRICHED LANE ONLY" in doc
        assert "no `lane` parameter" in doc
        assert "Citations_search_oa_citations_minimal" in doc
        assert "numFound" in doc


class TestOADocstringsDiscloseTheLimits:
    def test_publication_number_400_is_documented_as_deliberate(self):
        doc = inspect.getdoc(search_oa_citations_minimal)
        assert "DELIBERATE 400" in doc
        assert "numFound 0" in doc

    def test_the_1449_undercount_is_disclosed_at_the_tool(self):
        """OPEN_ITEMS.md 2026-08-29: the description said this lane transcribes
        Form 892 AND 1449, while on IDS-heavy files it returns close to what
        the examiner applied. The undercount is now stated where the caller
        reads the tool, not only in a repo document."""
        doc = inspect.getdoc(search_oa_citations_minimal)
        assert "APPLICANT-CITED (1449/IDS) COVERAGE IS PARTIAL" in doc
        assert "5 of 91" in doc
        assert "1 of 251" in doc
        assert "no evidence" in doc.lower()

    @pytest.mark.asyncio
    async def test_a_publication_number_clause_is_refused_with_the_reason(
        self, mock_runtime
    ):
        result = await search_oa_citations_minimal(
            criteria="publicationNumber:9049188"
        )

        assert result["status"] == "error"
        assert result["code"] == 400
        assert "numFound 0" in result["error"]
        assert not mock_runtime.oa_client.search_records.called
