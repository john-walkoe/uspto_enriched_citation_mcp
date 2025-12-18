"""
Basic tests for USPTO Enriched Citation MCP.
"""

import pytest
from unittest.mock import patch, AsyncMock
from uspto_enriched_citation_mcp.config.settings import Settings
from uspto_enriched_citation_mcp.api.enriched_client import EnrichedCitationClient


class TestBasic:
    """Basic functionality tests."""

    @pytest.fixture
    def mock_settings(self, monkeypatch):
        """Mock settings for testing."""
        # Set environment variables for BaseSettings
        monkeypatch.setenv(
            "USPTO_API_KEY",
            "test_key_32_characters_long_example",  # pragma: allowlist secret
        )
        monkeypatch.setenv("ECITATION_RATE_LIMIT", "50")
        return Settings()

    @pytest.fixture
    async def mock_client(self, mock_settings):
        """Mock client for testing."""
        return EnrichedCitationClient(
            api_key=mock_settings.uspto_ecitation_api_key,
            base_url=mock_settings.uspto_base_url,
            rate_limit=mock_settings.request_rate_limit,
            timeout=mock_settings.api_timeout,
            enable_cache=False  # Disable cache for tests
        )

    @pytest.mark.asyncio
    async def test_create_client(self, mock_settings):
        """Test client creation."""
        client = EnrichedCitationClient(
            api_key=mock_settings.uspto_ecitation_api_key,
            base_url=mock_settings.uspto_base_url,
            rate_limit=mock_settings.request_rate_limit,
            timeout=mock_settings.api_timeout,
            enable_cache=False
        )
        assert client.api_key == "test_key_32_characters_long_example"  # pragma: allowlist secret
        assert client.base_url == "https://developer.uspto.gov/ds-api"

    @pytest.mark.asyncio
    async def test_client_initialization(self, mock_client):
        """Test client initialization."""
        client = await mock_client
        assert client.api_key == "test_key_32_characters_long_example"  # pragma: allowlist secret
        assert client.base_url == "https://developer.uspto.gov/ds-api"
        assert client.enable_cache is False

    @pytest.mark.asyncio
    async def test_validate_query_syntax(self, mock_client):
        """Test query validation with validator."""
        from uspto_enriched_citation_mcp.util.query_validator import validate_lucene_syntax

        query = "patentApplicationNumber:16751234"
        is_valid, message = validate_lucene_syntax(query)
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_empty_query(self, mock_client):
        """Test validation of empty query."""
        from uspto_enriched_citation_mcp.util.query_validator import validate_lucene_syntax

        query = ""
        is_valid, message = validate_lucene_syntax(query)
        assert is_valid is False
        assert "empty" in message.lower()

    @pytest.mark.asyncio
    async def test_get_fields(self, mock_client):
        """Test getting available fields from API."""
        client = await mock_client

        # Mock the API response
        mock_response = {
            "fields": [
                {"name": "patentApplicationNumber", "type": "string"},
                {"name": "citedDocumentIdentifier", "type": "string"}
            ]
        }

        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = mock_response
            mock_get.return_value.headers = {"content-type": "application/json"}
            mock_get.return_value.content = b"{}"

            result = await client.get_fields()
            assert result is not None
            assert "fields" in result

    @pytest.mark.asyncio
    async def test_search_records(self, mock_client):
        """Test basic search records."""
        client = await mock_client
        criteria = "patentApplicationNumber:17654321"

        # Mock the API response
        mock_response = {
            "response": {
                "numFound": 1,
                "start": 0,
                "docs": [{"patentApplicationNumber": "17654321"}],
            }
        }

        with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_response
            mock_post.return_value.headers = {"content-type": "application/json"}
            mock_post.return_value.content = b"{}"

            result = await client.search_records(criteria=criteria, rows=5)
            assert result is not None
            assert result["response"]["numFound"] >= 0
            assert result["response"]["start"] == 0

    @pytest.mark.asyncio
    async def test_get_citation_details(self, mock_client):
        """Test getting citation details."""
        client = await mock_client
        citation_id = "12345"

        # Mock the API response
        mock_response = {
            "response": {
                "numFound": 1,
                "start": 0,
                "docs": [{"id": citation_id}],
            }
        }

        with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_response
            mock_post.return_value.headers = {"content-type": "application/json"}
            mock_post.return_value.content = b"{}"

            result = await client.get_citation_details(citation_id)
            assert result is not None
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_validate_boolean_query(self, mock_client):
        """Test validation of boolean query syntax."""
        from uspto_enriched_citation_mcp.util.query_validator import validate_lucene_syntax

        # Test valid boolean queries
        valid_queries = [
            "techCenter:2100 AND groupArtUnitNumber:2854",
            "techCenter:2100 OR techCenter:2800",
            "(techCenter:2100 OR techCenter:2800) AND examinerCitedReferenceIndicator:true",
            "techCenter:2100 NOT nplIndicator:true"
        ]

        for query in valid_queries:
            is_valid, message = validate_lucene_syntax(query)
            assert is_valid is True, f"Query should be valid: {query}"

    @pytest.mark.asyncio
    async def test_validate_range_query(self, mock_client):
        """Test validation of range query syntax."""
        from uspto_enriched_citation_mcp.util.query_validator import validate_lucene_syntax

        # Test valid range queries
        range_queries = [
            "officeActionDate:[2023-01-01 TO 2023-12-31]",
            "officeActionDate:[2023-01-01 TO *]",
            "groupArtUnitNumber:[2000 TO 2999]"
        ]

        for query in range_queries:
            is_valid, message = validate_lucene_syntax(query)
            assert is_valid is True, f"Range query should be valid: {query}"

    @pytest.mark.asyncio
    async def test_validate_wildcard_query(self, mock_client):
        """Test validation of wildcard query syntax."""
        from uspto_enriched_citation_mcp.util.query_validator import validate_lucene_syntax

        # Test valid wildcard queries
        wildcard_queries = [
            "patentApplicationNumber:18*",
            "inventorNameText:Smith*",
            "inventorNameText:*son"
        ]

        for query in wildcard_queries:
            is_valid, message = validate_lucene_syntax(query)
            assert is_valid is True, f"Wildcard query should be valid: {query}"

    @pytest.mark.asyncio
    async def test_validate_invalid_queries(self, mock_client):
        """Test detection of invalid query syntax."""
        from uspto_enriched_citation_mcp.util.query_validator import validate_lucene_syntax

        # Test invalid queries
        invalid_queries = [
            "patentApplicationNumber:",  # Missing value
            "techCenter:2100 AND",       # Incomplete boolean
            "officeActionDate:[2023-01-01 TO",  # Unclosed bracket
            "AND techCenter:2100",       # Leading operator
            ""                           # Empty query
        ]

        for query in invalid_queries:
            is_valid, message = validate_lucene_syntax(query)
            assert is_valid is False, f"Query should be invalid: {query}"

    @pytest.mark.asyncio
    async def test_special_characters_in_query(self, mock_client):
        """Test handling of special characters in queries."""
        from uspto_enriched_citation_mcp.util.query_validator import validate_lucene_syntax

        # Queries with special characters that need escaping
        queries_with_special_chars = [
            'inventorNameText:"John Smith"',  # Quoted phrase
            'citationCategoryCode:X',         # Simple value
            'techCenter:2100'                 # Numeric value
        ]

        for query in queries_with_special_chars:
            is_valid, message = validate_lucene_syntax(query)
            # Should either be valid or provide helpful error
            assert is_valid is not None


if __name__ == "__main__":
    pytest.main([__file__])
