"""
Unit tests for USPTO Office Action Citations API v2 service layer.

Tests OACitationService with mocked OACitationsClient.

Run with: uv run pytest tests/test_oa_citation_service.py -v
"""

import pytest
from unittest.mock import AsyncMock

from uspto_enriched_citation_mcp.services.oa_citation_service import (
    OACitationService,
)
from uspto_enriched_citation_mcp.api.oa_citations_client import (
    OA_CITATIONS_MINIMAL_FIELDS,
    OA_CITATIONS_ALL_FIELDS,
)


class TestOACitationServiceSearch:
    """Tests for search methods in OACitationService."""

    @pytest.fixture
    def mock_client(self):
        """Create a mocked OACitationsClient."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_client):
        return OACitationService(mock_client)

    @pytest.mark.asyncio
    async def test_search_minimal_default_fields(self, service, mock_client):
        """Test 1: search_minimal uses correct default fields and filters docs."""
        # Mock client returns full doc with many fields
        mock_client.search_records.return_value = {
            "response": {
                "numFound": 2,
                "docs": [
                    {
                        "patentApplicationNumber": "17896175",
                        "groupArtUnitNumber": "2854",
                        "techCenter": "2100",
                        "referenceIdentifier": "US-REF-001",
                        "actionTypeCategory": "OA",
                        "examinerCitedReferenceIndicator": True,
                        "createDateTime": "2023-05-01T00:00:00Z",
                        # These should be filtered out by client-side filtering
                        "parsedReferenceIdentifier": "SHOULD_BE_REMOVED",
                        "legalSectionCode": "SHOULD_BE_REMOVED",
                    },
                    {
                        "patentApplicationNumber": "17896176",
                        "groupArtUnitNumber": "2855",
                        "techCenter": "2100",
                        "referenceIdentifier": "US-REF-002",
                        "actionTypeCategory": "FA",
                        "examinerCitedReferenceIndicator": False,
                        "createDateTime": "2023-05-02T00:00:00Z",
                        "parsedReferenceIdentifier": "SHOULD_ALSO_BE_REMOVED",
                    },
                ]
            }
        }

        result = await service.search_minimal(criteria="techCenter:2100", rows=50)

        # Verify client was called with minimal fields (positional args)
        args, kwargs = mock_client.search_records.call_args
        assert args == ("techCenter:2100", 0, 50, OA_CITATIONS_MINIMAL_FIELDS)

        # Verify response structure
        assert "response" in result
        assert len(result["response"]["docs"]) == 2

        # The OA API ignores `fl`, so the tier's default set is enforced
        # client-side: fields outside OA_CITATIONS_MINIMAL_FIELDS are dropped
        # on the default path. Nothing is injected on top — the PFW hand-off
        # is stated once on the response envelope (tools/oa.py `pfw_link`)
        # instead of repeating the same sentence on every row.
        for doc in result["response"]["docs"]:
            assert "patentApplicationNumber" in doc
            assert "_pfw_link" not in doc
            assert "parsedReferenceIdentifier" not in doc
            assert "legalSectionCode" not in doc
            assert set(doc) <= set(OA_CITATIONS_MINIMAL_FIELDS)

    @pytest.mark.asyncio
    async def test_search_minimal_custom_fields(self, service, mock_client):
        """Test 2: search_minimal with custom fields passes them to client."""
        custom_fields = ["patentApplicationNumber", "groupArtUnitNumber", "techCenter"]

        mock_client.search_records.return_value = {
            "response": {
                "numFound": 1,
                "docs": [
                    {
                        "patentApplicationNumber": "17896175",
                        "groupArtUnitNumber": "2854",
                        "techCenter": "2100",
                        "actionTypeCategory": "OA",  # Should be filtered
                    }
                ]
            }
        }

        result = await service.search_minimal(
            criteria="techCenter:2100",
            rows=50,
            custom_fields=custom_fields,
        )

        # Verify custom fields were passed to client
        args, kwargs = mock_client.search_records.call_args
        assert args == ("techCenter:2100", 0, 50, custom_fields)

        # Verify client-side filtering applied
        docs = result["response"]["docs"]
        for doc in docs:
            assert "patentApplicationNumber" in doc
            assert "groupArtUnitNumber" in doc
            assert "actionTypeCategory" not in doc  # not in custom_fields
            # A caller-chosen doc shape keeps the inline annotation.
            assert "_pfw_link" in doc

    @pytest.mark.asyncio
    async def test_search_balanced_fields(self, service, mock_client):
        """Test 3: search_balanced uses balanced field set and filters correctly."""
        mock_client.search_records.return_value = {
            "response": {
                "numFound": 1,
                "docs": [
                    {
                        "patentApplicationNumber": "17896175",
                        "groupArtUnitNumber": "2854",
                        "techCenter": "2100",
                        "referenceIdentifier": "US-REF-001",
                        "parsedReferenceIdentifier": "PARSED-001",
                        "actionTypeCategory": "OA",
                        "legalSectionCode": "35 USC 102",
                        "examinerCitedReferenceIndicator": True,
                        "applicantCitedExaminerReferenceIndicator": False,
                        "officeActionCitationReferenceIndicator": True,
                        "workGroup": "2854",
                        "paragraphNumber": "0010",
                        "createDateTime": "2023-05-01T00:00:00Z",
                        "createUserIdentifier": "examiner1",
                        "obsoleteDocumentIdentifier": "OLD-ID",
                        "id": "internal-id",
                        "extraField": "REMOVE_ME",
                    }
                ]
            }
        }

        result = await service.search_balanced(criteria="techCenter:2100", rows=25)

        # Verify client was called with balanced fields (rows=25 default)
        args, kwargs = mock_client.search_records.call_args
        assert args == ("techCenter:2100", 0, 25, OA_CITATIONS_ALL_FIELDS)

        docs = result["response"]["docs"]
        assert len(docs) == 1
        doc = docs[0]

        # Balanced fields should be present
        assert "patentApplicationNumber" in doc
        assert "parsedReferenceIdentifier" in doc
        assert "legalSectionCode" in doc
        assert "createUserIdentifier" in doc
        assert "obsoleteDocumentIdentifier" in doc

        # The tier's own field set is enforced client-side, so a field the API
        # volunteers outside OA_CITATIONS_ALL_FIELDS is dropped, and the
        # default path injects nothing on top of it.
        assert "extraField" not in doc
        assert "_pfw_link" not in doc

    @pytest.mark.asyncio
    async def test_search_balanced_custom_fields(self, service, mock_client):
        """Test 3b: search_balanced with custom fields."""
        custom_fields = ["patentApplicationNumber", "actionTypeCategory"]

        mock_client.search_records.return_value = {
            "response": {
                "numFound": 1,
                "docs": [
                    {
                        "patentApplicationNumber": "17896175",
                        "actionTypeCategory": "OA",
                        "groupArtUnitNumber": "2854",  # Should be filtered
                    }
                ]
            }
        }

        result = await service.search_balanced(
            criteria="techCenter:2100",
            custom_fields=custom_fields,
        )

        args, kwargs = mock_client.search_records.call_args
        assert args == ("techCenter:2100", 0, 25, custom_fields)

        doc = result["response"]["docs"][0]
        assert "patentApplicationNumber" in doc
        assert "actionTypeCategory" in doc
        assert "groupArtUnitNumber" not in doc


class TestOACitationServicePfwLink:
    """Tests for _pfw_link injection in OACitationService."""

    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_client):
        return OACitationService(mock_client)

    @pytest.mark.asyncio
    async def test_pfw_link_injection(self, service, mock_client):
        """Test 4: On a CUSTOM field list, each doc with a
        patentApplicationNumber gets _pfw_link injected. The default tiers
        state the hand-off once on the envelope instead (see
        TestOACitationServicePfwLink.test_default_path_has_no_per_row_link)."""
        mock_client.search_records.return_value = {
            "response": {
                "numFound": 3,
                "docs": [
                    {
                        "patentApplicationNumber": "17896175",
                        "groupArtUnitNumber": "2854",
                    },
                    {
                        "patentApplicationNumber": "17896176",
                        "groupArtUnitNumber": "2855",
                    },
                    {
                        # No app number - should NOT get _pfw_link
                        "groupArtUnitNumber": "2856",
                    },
                ]
            }
        }

        result = await service.search_minimal(
            criteria="techCenter:2100",
            rows=50,
            custom_fields=["patentApplicationNumber", "groupArtUnitNumber"],
        )

        docs = result["response"]["docs"]

        # First doc has app number → _pfw_link
        assert "_pfw_link" in docs[0]
        assert "17896175" in docs[0]["_pfw_link"]
        assert "PFW_get_application_documents" in docs[0]["_pfw_link"]

        # Second doc has app number → _pfw_link
        assert "_pfw_link" in docs[1]
        assert "17896176" in docs[1]["_pfw_link"]

        # Third doc has NO app number → no _pfw_link
        assert "_pfw_link" not in docs[2]

    @pytest.mark.asyncio
    async def test_pfw_link_format(self, service, mock_client):
        """Test 4b: _pfw_link has the correct MCP command format."""
        mock_client.search_records.return_value = {
            "response": {
                "numFound": 1,
                "docs": [
                    {
                        "patentApplicationNumber": "17901234",
                        "groupArtUnitNumber": "2854",
                    }
                ]
            }
        }

        result = await service.search_minimal(
            criteria="techCenter:2100",
            custom_fields=["patentApplicationNumber", "groupArtUnitNumber"],
        )

        link = result["response"]["docs"][0]["_pfw_link"]
        assert link == "Use PFW MCP: PFW_get_application_documents(app_number='17901234')"

    @pytest.mark.asyncio
    async def test_pfw_link_balanced(self, service, mock_client):
        """Test 4c: the custom-fields path injects _pfw_link on the balanced
        tier too."""
        mock_client.search_records.return_value = {
            "response": {
                "numFound": 1,
                "docs": [
                    {
                        "patentApplicationNumber": "17896175",
                        "groupArtUnitNumber": "2854",
                        "techCenter": "2100",
                    }
                ]
            }
        }

        result = await service.search_balanced(
            criteria="techCenter:2100",
            custom_fields=["patentApplicationNumber", "groupArtUnitNumber"],
        )

        assert "_pfw_link" in result["response"]["docs"][0]
        assert "17896175" in result["response"]["docs"][0]["_pfw_link"]

    @pytest.mark.asyncio
    async def test_default_path_has_no_per_row_link(self, service, mock_client):
        """The dedupe: the default tiers repeat nothing per row."""
        mock_client.search_records.return_value = {
            "response": {
                "numFound": 2,
                "docs": [
                    {"patentApplicationNumber": "17896175", "techCenter": "2100"},
                    {"patentApplicationNumber": "17896176", "techCenter": "2100"},
                ]
            }
        }

        minimal = await service.search_minimal(criteria="techCenter:2100")
        balanced = await service.search_balanced(criteria="techCenter:2100")

        for result in (minimal, balanced):
            for doc in result["response"]["docs"]:
                assert "_pfw_link" not in doc


class TestOACitationServiceGetFields:
    """Tests for get_fields delegation."""

    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_client):
        return OACitationService(mock_client)

    @pytest.mark.asyncio
    async def test_get_fields(self, service, mock_client):
        """Test 5: get_fields delegates to client.get_fields()."""
        expected_fields = {
            "fields": [
                {"name": "patentApplicationNumber", "type": "string"},
                {"name": "groupArtUnitNumber", "type": "string"},
            ]
        }
        mock_client.get_fields.return_value = expected_fields

        result = await service.get_fields()

        mock_client.get_fields.assert_called_once()
        assert result == expected_fields


class TestOACitationServiceErrorHandling:
    """Tests for error handling in OACitationService."""

    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_client):
        return OACitationService(mock_client)

    @pytest.mark.asyncio
    async def test_error_response_passed_through(self, service, mock_client):
        """API error response is passed through without modification."""
        error_response = {
            "error": "Invalid query syntax",
            "code": 400,
        }
        mock_client.search_records.return_value = error_response

        result = await service.search_minimal(criteria="INVALID_QUERY")

        # Error responses are returned as-is (service doesn't add _pfw_link to errors)
        assert result == error_response
        assert "error" in result
        assert mock_client.search_records.called

    @pytest.mark.asyncio
    async def test_empty_docs_list(self, service, mock_client):
        """Empty docs list is handled gracefully (no _pfw_link injection crash)."""
        mock_client.search_records.return_value = {
            "response": {
                "numFound": 0,
                "docs": []
            }
        }

        result = await service.search_minimal(criteria="techCenter:9999")

        assert result["response"]["docs"] == []
        assert result["response"]["numFound"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
