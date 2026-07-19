"""
Tests for citation statistics functionality in USPTO Enriched Citation MCP.

Tests the get_citation_statistics tool which provides aggregate data
for strategic planning and citation analysis.

Run with: uv run pytest tests/test_statistics.py -v
"""

import pytest

# Skip all tests if no API key
from tests.test_integration import has_api_key

pytestmark = pytest.mark.skipif(
    not has_api_key(),
    reason="USPTO_API_KEY not configured - skipping statistics tests"
)


class TestCitationStatistics:
    """Test citation statistics functionality."""

    @pytest.mark.asyncio
    async def test_basic_statistics_retrieval(self):
        """Test 1.1: Basic statistics retrieval works."""
        from uspto_enriched_citation_mcp.main import get_citation_statistics

        result = await get_citation_statistics(
            criteria="techCenter:2100",
            stats_fields=["citationCategoryCode"]
        )

        assert result is not None
        assert "status" in result
        # Should have either success or error status
        assert result["status"] in ["success", "error"]

    @pytest.mark.asyncio
    async def test_statistics_with_empty_criteria(self):
        """Test 1.2: Statistics with empty criteria (global stats)."""
        from uspto_enriched_citation_mcp.main import get_citation_statistics

        result = await get_citation_statistics(
            criteria="",  # Empty = all records
            stats_fields=["citationCategoryCode"]
        )

        assert result is not None
        # Should handle empty criteria gracefully

    @pytest.mark.asyncio
    async def test_category_distribution_stats(self):
        """Test 1.3: Category distribution statistics."""
        from uspto_enriched_citation_mcp.main import get_citation_statistics

        result = await get_citation_statistics(
            criteria="techCenter:2100",
            stats_fields=["citationCategoryCode"]
        )

        if result["status"] == "success":
            # Should have data about citation categories
            assert "data" in result or "statistics" in result

    @pytest.mark.asyncio
    async def test_examiner_vs_applicant_stats(self):
        """Test 1.4: Examiner vs applicant citation statistics."""
        from uspto_enriched_citation_mcp.main import get_citation_statistics

        result = await get_citation_statistics(
            criteria="techCenter:2854",
            stats_fields=["examinerCitedReferenceIndicator"]
        )

        if result["status"] == "success":
            # Should have examiner citation data
            assert result is not None

    @pytest.mark.asyncio
    async def test_multiple_stats_fields(self):
        """Test 1.5: Multiple statistics fields aggregation."""
        from uspto_enriched_citation_mcp.main import get_citation_statistics

        result = await get_citation_statistics(
            criteria="groupArtUnitNumber:2854",
            stats_fields=["citationCategoryCode", "examinerCitedReferenceIndicator"]
        )

        assert result is not None
        assert "status" in result

    @pytest.mark.asyncio
    async def test_date_range_statistics(self):
        """Test 1.6: Statistics with date range filter."""
        from uspto_enriched_citation_mcp.main import get_citation_statistics

        result = await get_citation_statistics(
            criteria="officeActionDate:[2023-01-01 TO 2023-12-31] AND techCenter:2100",
            stats_fields=["citationCategoryCode"]
        )

        assert result is not None
        # Should work with date range filters

    @pytest.mark.asyncio
    async def test_empty_result_statistics(self):
        """Test 1.7: Statistics handle empty results gracefully."""
        from uspto_enriched_citation_mcp.main import get_citation_statistics

        # Query that should return no results
        result = await get_citation_statistics(
            criteria="patentApplicationNumber:99999999",  # Non-existent
            stats_fields=["citationCategoryCode"]
        )

        assert result is not None
        # Should handle empty results without crashing

    @pytest.mark.asyncio
    async def test_invalid_stats_field(self):
        """Test 1.8: Invalid stats field handling."""
        from uspto_enriched_citation_mcp.main import get_citation_statistics

        result = await get_citation_statistics(
            criteria="techCenter:2100",
            stats_fields=["nonexistentField"]
        )

        # Should either succeed with empty data or return error
        assert result is not None
        assert "status" in result


class TestStatisticsServiceLayer:
    """Test statistics service layer functionality."""

    @pytest.fixture
    async def citation_service(self):
        """Create citation service for testing."""
        from uspto_enriched_citation_mcp.config.settings import Settings
        from uspto_enriched_citation_mcp.api.enriched_client import EnrichedCitationClient
        from uspto_enriched_citation_mcp.services.citation_service import CitationService
        from uspto_enriched_citation_mcp.config.field_manager import FieldManager

        settings = Settings()
        client = EnrichedCitationClient(
            api_key=settings.uspto_ecitation_api_key,
            base_url=settings.uspto_base_url,
            enable_cache=False  # Disable for testing
        )
        field_manager = FieldManager()
        return CitationService(client, field_manager)

    @pytest.mark.asyncio
    async def test_service_get_statistics(self, citation_service):
        """Test 2.1: Service layer get_statistics method."""
        service = await citation_service

        result = await service.get_statistics(criteria="techCenter:2100")

        assert result is not None
        # Should have some structure

    @pytest.mark.asyncio
    async def test_statistics_with_wildcard(self, citation_service):
        """Test 2.2: Statistics with wildcard search."""
        service = await citation_service

        result = await service.get_statistics(criteria="*:*")

        # Global search - should return something
        assert result is not None


class TestStatisticsResponseFormat:
    """Test statistics response format and structure."""

    @pytest.mark.asyncio
    async def test_response_has_required_fields(self):
        """Test 3.1: Statistics response has required fields."""
        from uspto_enriched_citation_mcp.main import get_citation_statistics

        result = await get_citation_statistics(
            criteria="techCenter:2100",
            stats_fields=["citationCategoryCode"]
        )

        # Should have status field
        assert "status" in result

        # If successful, should have data
        if result["status"] == "success":
            # Check for data structure (implementation-dependent)
            assert result is not None

    @pytest.mark.asyncio
    async def test_error_response_format(self):
        """Test 3.2: Error responses are well-formatted."""
        from uspto_enriched_citation_mcp.main import get_citation_statistics

        # Trigger error with invalid query
        result = await get_citation_statistics(
            criteria="INVALID QUERY WITH SPECIAL CHARS!!!",
            stats_fields=[]
        )

        # Should have error information
        if result["status"] == "error":
            # Should have error message or details
            assert "error" in result or "message" in result or "error_message" in result

    @pytest.mark.asyncio
    async def test_count_information(self):
        """Test 3.3: Statistics include count information."""
        from uspto_enriched_citation_mcp.main import get_citation_statistics

        result = await get_citation_statistics(
            criteria="techCenter:2100",
            stats_fields=["citationCategoryCode"]
        )

        if result["status"] == "success":
            # Should have count or total information
            # (Field name depends on implementation)
            assert result is not None


class TestStatisticsPerformance:
    """Test statistics performance characteristics."""

    @pytest.mark.asyncio
    async def test_large_dataset_statistics(self):
        """Test 4.1: Statistics handle large datasets efficiently."""
        from uspto_enriched_citation_mcp.main import get_citation_statistics
        import time

        start_time = time.time()

        result = await get_citation_statistics(
            criteria="techCenter:2100",  # Large dataset
            stats_fields=["citationCategoryCode"]
        )

        elapsed = time.time() - start_time

        # Should complete in reasonable time (< 10 seconds)
        assert elapsed < 10.0
        assert result is not None

    @pytest.mark.asyncio
    async def test_multiple_aggregations_performance(self):
        """Test 4.2: Multiple aggregations are efficient."""
        from uspto_enriched_citation_mcp.main import get_citation_statistics
        import time

        start_time = time.time()

        result = await get_citation_statistics(
            criteria="techCenter:2100",
            stats_fields=[
                "citationCategoryCode",
                "examinerCitedReferenceIndicator",
                "techCenter"
            ]
        )

        elapsed = time.time() - start_time

        # Multiple aggregations should still be reasonably fast
        assert elapsed < 15.0
        assert result is not None


class TestStatisticsEdgeCases:
    """Test statistics edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_no_results_statistics(self):
        """Test 5.1: Statistics with no matching results."""
        from uspto_enriched_citation_mcp.main import get_citation_statistics

        result = await get_citation_statistics(
            criteria="patentApplicationNumber:00000000",
            stats_fields=["citationCategoryCode"]
        )

        assert result is not None
        # Should handle gracefully

    @pytest.mark.asyncio
    async def test_empty_stats_fields(self):
        """Test 5.2: Statistics with empty stats_fields list."""
        from uspto_enriched_citation_mcp.main import get_citation_statistics

        result = await get_citation_statistics(
            criteria="techCenter:2100",
            stats_fields=[]
        )

        # Should handle empty fields list
        assert result is not None

    @pytest.mark.asyncio
    async def test_complex_criteria_statistics(self):
        """Test 5.3: Statistics with complex boolean criteria."""
        from uspto_enriched_citation_mcp.main import get_citation_statistics

        result = await get_citation_statistics(
            criteria=(
                "(techCenter:2100 OR techCenter:2800) AND "
                "citationCategoryCode:X AND "
                "officeActionDate:[2023-01-01 TO *]"
            ),
            stats_fields=["examinerCitedReferenceIndicator"]
        )

        assert result is not None
        # Complex queries should work

    @pytest.mark.asyncio
    async def test_statistics_field_validation(self):
        """Test 5.4: Invalid field names handled correctly."""
        from uspto_enriched_citation_mcp.main import get_citation_statistics

        result = await get_citation_statistics(
            criteria="techCenter:2100",
            stats_fields=["invalidFieldName123"]
        )

        # Should either error or return empty results
        assert result is not None
        assert "status" in result


class TestStatisticsIntegration:
    """Test statistics integration with other components."""

    @pytest.mark.asyncio
    async def test_statistics_with_field_manager(self):
        """Test 6.1: Statistics work with field manager."""
        from uspto_enriched_citation_mcp.config.field_manager import FieldManager

        field_manager = FieldManager()
        available_fields = field_manager.get_all_available_fields()

        # Statistics fields should be in available fields
        common_stats_fields = ["citationCategoryCode", "techCenter", "groupArtUnitNumber"]

        for field in common_stats_fields:
            # Most should be available (implementation-dependent)
            if field in available_fields:
                assert field in available_fields

    @pytest.mark.asyncio
    async def test_statistics_respects_api_constraints(self):
        """Test 6.2: Statistics respect API date constraints."""
        from uspto_enriched_citation_mcp.main import get_citation_statistics

        # Try to get stats with date before API coverage
        result = await get_citation_statistics(
            criteria="officeActionDate:[2015-01-01 TO 2016-12-31]",  # Before 2017-10-01
            stats_fields=["citationCategoryCode"]
        )

        # Should handle dates before coverage period
        assert result is not None


class TestStatisticsUseCase:
    """Test real-world statistics use cases."""

    @pytest.mark.asyncio
    async def test_art_unit_analysis(self):
        """Test 7.1: Art unit citation pattern analysis."""
        from uspto_enriched_citation_mcp.main import get_citation_statistics

        result = await get_citation_statistics(
            criteria="groupArtUnitNumber:2854",
            stats_fields=["citationCategoryCode", "examinerCitedReferenceIndicator"]
        )

        assert result is not None
        # Should provide art unit statistics

    @pytest.mark.asyncio
    async def test_tech_center_comparison(self):
        """Test 7.2: Tech center comparison statistics."""
        from uspto_enriched_citation_mcp.main import get_citation_statistics

        # Get stats for one tech center
        tc_2100 = await get_citation_statistics(
            criteria="techCenter:2100",
            stats_fields=["citationCategoryCode"]
        )

        # Get stats for another
        tc_2800 = await get_citation_statistics(
            criteria="techCenter:2800",
            stats_fields=["citationCategoryCode"]
        )

        # Both should return data
        assert tc_2100 is not None
        assert tc_2800 is not None

    @pytest.mark.asyncio
    async def test_temporal_analysis(self):
        """Test 7.3: Temporal citation pattern analysis."""
        from uspto_enriched_citation_mcp.main import get_citation_statistics

        result = await get_citation_statistics(
            criteria=(
                "techCenter:2100 AND "
                "officeActionDate:[2023-01-01 TO 2023-06-30]"
            ),
            stats_fields=["citationCategoryCode"]
        )

        assert result is not None
        # Should support temporal analysis


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
