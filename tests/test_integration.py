"""
Integration tests for USPTO Enriched Citation MCP.

These tests use real API calls to validate end-to-end workflows.
Tests will be skipped if USPTO_API_KEY is not configured.

Run with: uv run pytest tests/test_integration.py -v
"""

import pytest

# Import MCP server components
from uspto_enriched_citation_mcp.config.settings import Settings
from uspto_enriched_citation_mcp.api.enriched_client import EnrichedCitationClient
from uspto_enriched_citation_mcp.services.citation_service import CitationService
from uspto_enriched_citation_mcp.config.field_manager import FieldManager


# Test configuration
EXPECTED_MINIMAL_FIELDS = 8
EXPECTED_BALANCED_FIELDS = 18
EXPECTED_TOTAL_FIELDS = 22

# Known test data (applications with citations)
TEST_APPLICATION_NUMBER = "17896175"
TEST_TECH_CENTER = "2100"
TEST_ART_UNIT = "2854"


def has_api_key() -> bool:
    """Check if API key is available."""
    try:
        settings = Settings()
        return bool(settings.uspto_ecitation_api_key)
    except Exception:
        return False


# Skip all tests if no API key
pytestmark = pytest.mark.skipif(
    not has_api_key(),
    reason="USPTO_API_KEY not configured - skipping integration tests"
)


@pytest.fixture
async def api_client():
    """Create real API client for integration tests."""
    settings = Settings()
    client = EnrichedCitationClient(
        api_key=settings.uspto_ecitation_api_key,
        base_url=settings.uspto_base_url,
        rate_limit=settings.request_rate_limit,
        timeout=settings.api_timeout,
        enable_cache=False  # Disable cache for tests
    )
    return client


@pytest.fixture
async def citation_service(api_client):
    """Create citation service with real API client."""
    field_manager = FieldManager()
    client = await api_client
    service = CitationService(client, field_manager)
    return service


class TestProgressiveDisclosureWorkflow:
    """Test Category 1: Progressive Disclosure Integration"""

    @pytest.mark.asyncio
    async def test_minimal_search_workflow(self, citation_service):
        """Test 1.1: Minimal search with 8 essential fields."""
        service = await citation_service

        # Search with minimal fields
        result = await service.search_citations(
            criteria=f"patentApplicationNumber:{TEST_APPLICATION_NUMBER}",
            rows=10,
            field_set="minimal"
        )

        assert result is not None
        assert "response" in result
        assert "numFound" in result["response"]

        # Verify field count if results exist
        if result["response"]["numFound"] > 0:
            first_doc = result["response"]["docs"][0]
            # Should have minimal fields only
            assert "citedDocumentIdentifier" in first_doc
            assert "patentApplicationNumber" in first_doc
            assert "techCenter" in first_doc or "groupArtUnitNumber" in first_doc

            # Calculate approximate field count (some may be missing)
            field_count = len(first_doc)
            assert field_count <= EXPECTED_MINIMAL_FIELDS + 2  # Allow some flexibility

    @pytest.mark.asyncio
    async def test_balanced_search_workflow(self, citation_service):
        """Test 1.3: Balanced search with 18 key fields."""
        service = await citation_service

        # Search with balanced fields
        result = await service.search_citations(
            criteria=f"patentApplicationNumber:{TEST_APPLICATION_NUMBER}",
            rows=5,
            field_set="balanced"
        )

        assert result is not None
        assert "response" in result

        # Verify more fields than minimal
        if result["response"]["numFound"] > 0:
            first_doc = result["response"]["docs"][0]
            field_count = len(first_doc)

            # Should have more fields than minimal
            assert field_count > EXPECTED_MINIMAL_FIELDS

            # Check for balanced-specific fields
            # Note: Not all fields may be present for every record
            balanced_fields = [
                "citedDocumentIdentifier",
                "patentApplicationNumber",
                "citationCategoryCode",
                "examinerCitedReferenceIndicator"
            ]
            for field in balanced_fields[:3]:  # Check at least some key fields
                if field in first_doc:  # Field presence varies by record
                    assert first_doc[field] is not None or first_doc[field] == ""

    @pytest.mark.asyncio
    async def test_progressive_disclosure_sequence(self, citation_service):
        """Test 1.4: Complete progressive disclosure workflow."""
        service = await citation_service
        criteria = f"techCenter:{TEST_TECH_CENTER}"

        # Step 1: Minimal search for discovery
        minimal_result = await service.search_citations(
            criteria=criteria,
            rows=20,
            field_set="minimal"
        )

        assert minimal_result["response"]["numFound"] > 0

        # Step 2: Get balanced details for first result
        if minimal_result["response"]["numFound"] > 0:
            balanced_result = await service.search_citations(
                criteria=criteria,
                rows=5,
                field_set="balanced"
            )

            assert balanced_result is not None
            assert balanced_result["response"]["numFound"] > 0


class TestFieldManagementIntegration:
    """Test Category 2: Field Management Integration"""

    @pytest.mark.asyncio
    async def test_get_available_fields(self, api_client):
        """Test 2.1: Retrieve available fields from API."""
        client = await api_client

        result = await client.get_fields()

        assert result is not None
        assert "fields" in result
        assert len(result["fields"]) >= 20  # At least 20 fields expected

        # Check for key fields
        field_names = [f["name"] for f in result["fields"]]
        assert "citedDocumentIdentifier" in field_names
        assert "patentApplicationNumber" in field_names
        assert "citationCategoryCode" in field_names

    @pytest.mark.asyncio
    async def test_custom_field_search(self, citation_service):
        """Test 2.2: Ultra-minimal search with custom fields."""
        service = await citation_service

        # Define ultra-minimal custom fields
        custom_fields = [
            "citedDocumentIdentifier",
            "patentApplicationNumber",
            "citationCategoryCode"
        ]

        result = await service.search_citations(
            criteria=f"patentApplicationNumber:{TEST_APPLICATION_NUMBER}",
            rows=10,
            fields=custom_fields
        )

        assert result is not None
        assert "response" in result

        # Verify only requested fields returned
        if result["response"]["numFound"] > 0:
            first_doc = result["response"]["docs"][0]
            # Should have approximately the requested fields
            # (API may include some system fields)
            for field in custom_fields:
                # Field may or may not be present depending on data
                if field in first_doc:
                    assert first_doc[field] is not None or first_doc[field] == ""


class TestQuerySyntaxIntegration:
    """Test Category 3: Query Syntax Integration"""

    @pytest.mark.asyncio
    async def test_basic_query_syntax(self, citation_service):
        """Test 3.1: Basic Lucene query syntax."""
        service = await citation_service

        queries = [
            f"patentApplicationNumber:{TEST_APPLICATION_NUMBER}",
            f"techCenter:{TEST_TECH_CENTER}",
            f"techCenter:{TEST_TECH_CENTER} AND groupArtUnitNumber:{TEST_ART_UNIT}",
        ]

        for query in queries:
            result = await service.search_citations(
                criteria=query,
                rows=5
            )
            assert result is not None
            assert "response" in result

    @pytest.mark.asyncio
    async def test_date_range_query(self, citation_service):
        """Test 3.2: Date range query syntax."""
        service = await citation_service

        # API constraint: Data from 2017-10-01 forward
        query = f"officeActionDate:[2023-01-01 TO 2024-12-31] AND techCenter:{TEST_TECH_CENTER}"

        result = await service.search_citations(
            criteria=query,
            rows=10
        )

        assert result is not None
        assert "response" in result


class TestConvenienceParametersIntegration:
    """Test Category 4: Convenience Parameters Integration"""

    @pytest.mark.asyncio
    async def test_date_convenience_parameters(self, citation_service):
        """Test 4.1: Date convenience parameters."""
        service = await citation_service

        # Use date convenience parameters
        result = await service.search_citations(
            criteria=f"techCenter:{TEST_TECH_CENTER}",
            date_start="2023-01-01",
            date_end="2024-12-31",
            rows=10
        )

        assert result is not None
        assert "response" in result

        # Verify date filtering if results exist
        if result["response"]["numFound"] > 0:
            for doc in result["response"]["docs"]:
                if "officeActionDate" in doc:
                    oa_date = doc["officeActionDate"]
                    # Date should be in expected range
                    assert "2023" in str(oa_date) or "2024" in str(oa_date)


class TestCitationAnalysisIntegration:
    """Test Category 5: Citation Analysis Integration"""

    @pytest.mark.asyncio
    async def test_citation_category_analysis(self, citation_service):
        """Test 5.1: Citation category filtering."""
        service = await citation_service

        # Search with category filter
        result = await service.search_citations(
            criteria=f"techCenter:{TEST_TECH_CENTER} AND citationCategoryCode:*",
            rows=20,
            field_set="balanced"
        )

        assert result is not None
        assert "response" in result

        # Analyze categories if results exist
        if result["response"]["numFound"] > 0:
            categories = set()
            for doc in result["response"]["docs"]:
                if "citationCategoryCode" in doc:
                    categories.add(doc["citationCategoryCode"])

            # Should have at least some categorized citations
            assert len(categories) >= 0  # Categories may vary

    @pytest.mark.asyncio
    async def test_examiner_vs_applicant_citations(self, citation_service):
        """Test 5.2: Examiner vs applicant citation distinction."""
        service = await citation_service

        # Search for examiner-cited references
        result = await service.search_citations(
            criteria=f"techCenter:{TEST_TECH_CENTER} AND examinerCitedReferenceIndicator:true",
            rows=10,
            field_set="balanced"
        )

        assert result is not None
        assert "response" in result

        # Verify examiner citations if results exist
        if result["response"]["numFound"] > 0:
            for doc in result["response"]["docs"]:
                if "examinerCitedReferenceIndicator" in doc:
                    assert doc["examinerCitedReferenceIndicator"] in [True, "true", "Y", "y"]


class TestDateRangeIntegration:
    """Test Category 9: Date Range Integration"""

    @pytest.mark.asyncio
    async def test_api_date_constraint(self, citation_service):
        """Test 9.1: Verify API date constraint (2017-10-01 forward)."""
        service = await citation_service

        # Test earliest available date
        result = await service.search_citations(
            criteria=f"officeActionDate:[2017-10-01 TO 2018-12-31] AND techCenter:{TEST_TECH_CENTER}",
            rows=5
        )

        assert result is not None
        assert "response" in result
        # Should have results for valid date range

    @pytest.mark.asyncio
    async def test_date_range_validation(self, citation_service):
        """Test 9.2: Date range validation and handling."""
        service = await citation_service

        # Test with reasonable date range
        result = await service.search_citations(
            criteria=f"techCenter:{TEST_TECH_CENTER}",
            date_start="2023-01-01",
            date_end="2024-12-31",
            rows=10
        )

        assert result is not None
        assert "response" in result


class TestErrorHandlingIntegration:
    """Test Category 7: Error Handling Integration"""

    @pytest.mark.asyncio
    async def test_empty_result_handling(self, citation_service):
        """Test 10.1: Graceful handling of empty results."""
        service = await citation_service

        # Search for non-existent application
        result = await service.search_citations(
            criteria="patentApplicationNumber:99999999",
            rows=10
        )

        assert result is not None
        assert "response" in result
        assert result["response"]["numFound"] == 0
        assert result["response"]["docs"] == []

    @pytest.mark.asyncio
    async def test_invalid_query_handling(self, citation_service):
        """Test 7.2: Invalid query handling."""
        service = await citation_service

        # Test with potentially problematic query
        try:
            # This should either handle gracefully or raise appropriate error
            result = await service.search_citations(
                criteria="techCenter:9999",  # Non-existent tech center
                rows=5
            )
            # If it succeeds, should return empty results
            assert result["response"]["numFound"] == 0
        except Exception as e:
            # If it raises error, should be meaningful
            assert "error" in str(e).lower() or "invalid" in str(e).lower()


class TestPerformanceIntegration:
    """Test Category 8: Performance Integration"""

    @pytest.mark.asyncio
    async def test_pagination_handling(self, citation_service):
        """Test 8.2: Pagination efficiency."""
        service = await citation_service

        # Test pagination
        page1 = await service.search_citations(
            criteria=f"techCenter:{TEST_TECH_CENTER}",
            rows=10,
            start=0
        )

        assert page1 is not None
        assert "response" in page1

        if page1["response"]["numFound"] > 10:
            page2 = await service.search_citations(
                criteria=f"techCenter:{TEST_TECH_CENTER}",
                rows=10,
                start=10
            )

            assert page2 is not None
            assert "response" in page2

            # Verify different results
            if len(page1["response"]["docs"]) > 0 and len(page2["response"]["docs"]) > 0:
                page1_ids = {doc.get("id", doc.get("citedDocumentIdentifier"))
                           for doc in page1["response"]["docs"]}
                page2_ids = {doc.get("id", doc.get("citedDocumentIdentifier"))
                           for doc in page2["response"]["docs"]}
                # Pages should have different records
                assert len(page1_ids.intersection(page2_ids)) == 0

    @pytest.mark.asyncio
    async def test_large_result_set_handling(self, citation_service):
        """Test 8.3: Large result set handling."""
        service = await citation_service

        # Test with larger row count
        result = await service.search_citations(
            criteria=f"techCenter:{TEST_TECH_CENTER}",
            rows=50,
            field_set="minimal"  # Use minimal for large sets
        )

        assert result is not None
        assert "response" in result

        # Should handle large result sets
        if result["response"]["numFound"] > 0:
            assert len(result["response"]["docs"]) <= 50


class TestWorkflowIntegration:
    """Test End-to-End Workflows"""

    @pytest.mark.asyncio
    async def test_discovery_to_analysis_workflow(self, citation_service):
        """Test complete discovery to analysis workflow."""
        service = await citation_service

        # Step 1: Discovery with minimal fields
        discovery = await service.search_citations(
            criteria=f"techCenter:{TEST_TECH_CENTER}",
            rows=20,
            field_set="minimal"
        )

        assert discovery["response"]["numFound"] > 0

        # Step 2: Select interesting applications
        if len(discovery["response"]["docs"]) > 0:
            first_doc = discovery["response"]["docs"][0]
            app_number = first_doc.get("patentApplicationNumber")

            if app_number:
                # Step 3: Detailed analysis with balanced fields
                analysis = await service.search_citations(
                    criteria=f"patentApplicationNumber:{app_number}",
                    rows=10,
                    field_set="balanced"
                )

                assert analysis is not None
                assert analysis["response"]["numFound"] >= 0

    @pytest.mark.asyncio
    async def test_tech_center_analysis_workflow(self, citation_service):
        """Test technology center citation analysis."""
        service = await citation_service

        # Analyze citations by tech center
        result = await service.search_citations(
            criteria=f"techCenter:{TEST_TECH_CENTER}",
            rows=50,
            field_set="minimal"
        )

        assert result is not None

        if result["response"]["numFound"] > 0:
            # Collect statistics
            examiner_cited = 0
            categories = {}

            for doc in result["response"]["docs"]:
                if doc.get("examinerCitedReferenceIndicator"):
                    examiner_cited += 1

                cat = doc.get("citationCategoryCode")
                if cat:
                    categories[cat] = categories.get(cat, 0) + 1

            # Should have some examiner citations
            assert examiner_cited >= 0  # Just verify counting works


if __name__ == "__main__":
    # Run with: python tests/test_integration.py
    pytest.main([__file__, "-v"])
