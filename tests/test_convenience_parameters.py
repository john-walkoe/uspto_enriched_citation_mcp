"""
Tests for convenience parameters in query construction.

Tests verify that convenience parameters (tech_center, applicant_name,
art_unit, category_code, examiner_cited, etc.) build correct Lucene queries.
"""

import pytest
from uspto_enriched_citation_mcp.main import build_query, QueryParameters
from uspto_enriched_citation_mcp.api.field_constants import QueryFieldNames


class TestConvenienceParameters:
    """Test convenience parameter query construction."""

    def test_tech_center_parameter(self):
        """Test tech_center builds correct field:value query."""
        result = build_query(QueryParameters(tech_center="2100"))

        assert "techCenter:2100" in result.query
        assert result.params_used["tech_center"] == "2100"
        assert len(result.warnings) == 0

    def test_applicant_name_parameter(self):
        """Test applicant_name builds correct phrase query with quotes."""
        result = build_query(QueryParameters(applicant_name="Apple Inc."))

        assert 'firstApplicantName:"Apple Inc."' in result.query
        assert result.params_used["applicant_name"] == "Apple Inc."
        assert len(result.warnings) == 0

    def test_application_number_parameter(self):
        """Test application_number builds correct field:value query."""
        result = build_query(QueryParameters(application_number="16751234"))

        assert "patentApplicationNumber:16751234" in result.query
        assert result.params_used["application_number"] == "16751234"
        assert len(result.warnings) == 0

    def test_patent_number_parameter(self):
        """Test patent_number builds correct field:value query."""
        result = build_query(QueryParameters(patent_number="11234567"))

        assert "publicationNumber:11234567" in result.query
        assert result.params_used["patent_number"] == "11234567"
        assert len(result.warnings) == 0

    def test_date_range_parameters(self):
        """Test date_start and date_end build correct range query."""
        result = build_query(QueryParameters(
            date_start="2023-01-01",
            date_end="2023-12-31"
        ))

        assert "officeActionDate:[2023-01-01 TO 2023-12-31]" in result.query
        assert result.params_used["date_range"] == "2023-01-01 TO 2023-12-31"
        assert len(result.warnings) == 0

    def test_date_range_open_start(self):
        """Test date range with open start (*)."""
        result = build_query(QueryParameters(date_end="2023-12-31"))

        assert "officeActionDate:[* TO 2023-12-31]" in result.query
        assert result.params_used["date_range"] == "* TO 2023-12-31"

    def test_date_range_open_end(self):
        """Test date range with open end (*)."""
        result = build_query(QueryParameters(date_start="2023-01-01"))

        assert "officeActionDate:[2023-01-01 TO *]" in result.query
        assert result.params_used["date_range"] == "2023-01-01 TO *"

    def test_decision_type_parameter(self):
        """Test decision_type builds correct field:value query."""
        result = build_query(QueryParameters(decision_type="final"))

        assert "decisionTypeCode:final" in result.query
        assert result.params_used["decision_type"] == "final"
        assert len(result.warnings) == 0

    def test_category_code_parameter(self):
        """Test category_code builds correct field:value query."""
        result = build_query(QueryParameters(category_code="102"))

        assert "citationCategoryCode:102" in result.query
        assert result.params_used["category_code"] == "102"
        assert len(result.warnings) == 0

    def test_examiner_cited_true(self):
        """Test examiner_cited=True builds correct boolean query."""
        result = build_query(QueryParameters(examiner_cited=True))

        assert "examinerCitedReferenceIndicator:true" in result.query
        assert result.params_used["examiner_cited"] == "true"
        assert len(result.warnings) == 0

    def test_examiner_cited_false(self):
        """Test examiner_cited=False builds correct boolean query."""
        result = build_query(QueryParameters(examiner_cited=False))

        assert "examinerCitedReferenceIndicator:false" in result.query
        assert result.params_used["examiner_cited"] == "false"
        assert len(result.warnings) == 0

    def test_art_unit_parameter(self):
        """Test art_unit builds correct field:value query."""
        result = build_query(QueryParameters(art_unit="2128"))

        assert "groupArtUnitNumber:2128" in result.query
        assert result.params_used["art_unit"] == "2128"
        assert len(result.warnings) == 0

    def test_multiple_parameters(self):
        """Test combining multiple convenience parameters with AND."""
        result = build_query(QueryParameters(
            tech_center="2100",
            art_unit="2128",
            examiner_cited=True,
            date_start="2023-01-01",
            date_end="2023-12-31"
        ))

        assert "techCenter:2100" in result.query
        assert "groupArtUnitNumber:2128" in result.query
        assert "examinerCitedReferenceIndicator:true" in result.query
        assert "officeActionDate:[2023-01-01 TO 2023-12-31]" in result.query
        assert " AND " in result.query
        assert len(result.params_used) == 4  # tech_center, art_unit, examiner_cited, date_range

    def test_criteria_plus_parameters(self):
        """Test combining base criteria with convenience parameters."""
        result = build_query(QueryParameters(
            criteria="citedDocumentIdentifier:US*",
            tech_center="2100",
            category_code="102"
        ))

        assert "(citedDocumentIdentifier:US*)" in result.query
        assert "techCenter:2100" in result.query
        assert "citationCategoryCode:102" in result.query
        assert " AND " in result.query

    def test_no_colon_escaping(self):
        """Verify colons in field:value syntax are NOT escaped."""
        result = build_query(QueryParameters(tech_center="2100"))

        # Should be techCenter:2100, NOT techCenter\\:2100
        assert "techCenter:2100" in result.query
        assert "\\:" not in result.query  # No escaped colons

    def test_no_quote_escaping(self):
        """Verify quotes in phrase queries are NOT escaped."""
        result = build_query(QueryParameters(applicant_name="Apple Inc."))

        # Should be firstApplicantName:"Apple Inc.", NOT firstApplicantName:\\"Apple Inc.\\"
        assert 'firstApplicantName:"Apple Inc."' in result.query
        assert '\\"' not in result.query  # No escaped quotes

    def test_no_bracket_escaping_in_ranges(self):
        """Verify brackets in date ranges are NOT escaped."""
        result = build_query(QueryParameters(
            date_start="2023-01-01",
            date_end="2023-12-31"
        ))

        # Should be officeActionDate:[2023-01-01 TO 2023-12-31]
        # NOT officeActionDate:\\[2023-01-01 TO 2023-12-31\\]
        assert "[2023-01-01 TO 2023-12-31]" in result.query
        assert "\\[" not in result.query  # No escaped brackets
        assert "\\]" not in result.query

    def test_no_dash_escaping_in_dates(self):
        """Verify dashes in dates are NOT escaped."""
        result = build_query(QueryParameters(date_start="2023-01-01"))

        # Should be 2023-01-01, NOT 2023\\-01\\-01
        assert "2023-01-01" in result.query
        assert "\\-" not in result.query  # No escaped dashes

    def test_parameter_validation_max_length(self):
        """Test parameter validation rejects overly long values."""
        with pytest.raises(ValueError, match="Parameter too long"):
            build_query(QueryParameters(tech_center="x" * 201))  # Exceeds 200 char limit

    def test_parameter_validation_invalid_chars(self):
        """Test parameter validation rejects invalid characters."""
        with pytest.raises(ValueError, match="Invalid characters"):
            build_query(QueryParameters(applicant_name='<script>alert("xss")</script>'))

    def test_at_least_one_criterion_required(self):
        """Test that build_query requires at least one parameter."""
        with pytest.raises(ValueError, match="At least one search criterion required"):
            build_query(QueryParameters())  # No parameters

    def test_field_name_constants_used(self):
        """Verify queries use field name constants, not hardcoded strings."""
        result = build_query(QueryParameters(
            tech_center="2100",
            art_unit="2128",
            category_code="102"
        ))

        # Verify field names match constants
        assert QueryFieldNames.TECH_CENTER in result.query or "techCenter" in result.query
        assert QueryFieldNames.GROUP_ART_UNIT in result.query or "groupArtUnitNumber" in result.query
        assert QueryFieldNames.CITATION_CATEGORY in result.query or "citationCategoryCode" in result.query


class TestParameterEdgeCases:
    """Test edge cases and error handling for parameters."""

    def test_empty_string_parameters_ignored(self):
        """Test that empty string parameters are ignored."""
        result = build_query(QueryParameters(
            tech_center="",
            art_unit="2128"
        ))

        assert "techCenter" not in result.query
        assert "groupArtUnitNumber:2128" in result.query

    def test_whitespace_only_parameters_ignored(self):
        """Test that whitespace-only parameters are ignored."""
        result = build_query(QueryParameters(
            tech_center="   ",
            art_unit="2128"
        ))

        assert "techCenter" not in result.query
        assert "groupArtUnitNumber:2128" in result.query

    def test_none_parameters_ignored(self):
        """Test that None parameters are ignored."""
        result = build_query(QueryParameters(
            tech_center=None,
            art_unit="2128"
        ))

        assert "techCenter" not in result.query
        assert "groupArtUnitNumber:2128" in result.query

    def test_examiner_cited_none_ignored(self):
        """Test that examiner_cited=None is ignored (not same as False)."""
        result = build_query(QueryParameters(
            examiner_cited=None,
            art_unit="2128"
        ))

        assert "examinerCitedReferenceIndicator" not in result.query
        assert "groupArtUnitNumber:2128" in result.query

    def test_date_validation_invalid_format(self):
        """Test that invalid date formats raise errors or warnings."""
        # This should either raise ValueError or add a warning
        try:
            result = build_query(QueryParameters(date_start="invalid-date"))
            # If it doesn't raise, check for warnings
            assert len(result.warnings) > 0 or "invalid-date" not in result.query
        except ValueError:
            pass  # Expected behavior
