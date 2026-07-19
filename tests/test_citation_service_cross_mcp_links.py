"""Unit tests for CitationService._get_cross_mcp_links (audit item 1a).

services/citation_service.py:_get_cross_mcp_links had zero tests prior to
this file (`grep -rn "_get_cross_mcp_links" tests/` returned no hits) despite
being non-trivial logic — dedupes 4 identifier types across docs, decides
`integration_ready` — that's injected directly into every
search_citations_minimal response (tools/search.py).
"""

from unittest.mock import Mock

from uspto_enriched_citation_mcp.services.citation_service import CitationService


def _service() -> CitationService:
    # _get_cross_mcp_links doesn't touch self.client/self.field_manager, so
    # Mocks are enough here (no network/service call happens).
    return CitationService(client=Mock(), field_manager=Mock())


class TestGetCrossMcpLinks:
    def test_empty_docs_returns_not_integration_ready(self):
        service = _service()

        result = service._get_cross_mcp_links({"response": {"docs": []}})

        assert result == {"available_links": {}, "integration_ready": False}

    def test_missing_response_key_treated_as_no_docs(self):
        service = _service()

        result = service._get_cross_mcp_links({})

        assert result == {"available_links": {}, "integration_ready": False}

    def test_dedupes_application_numbers_and_flags_ready(self):
        service = _service()

        result = service._get_cross_mcp_links(
            {
                "response": {
                    "docs": [
                        {"patentApplicationNumber": "16751234", "groupArtUnitNumber": "2854"},
                        {"patentApplicationNumber": "16751234", "techCenter": "2100"},
                        {"patentApplicationNumber": "16751235", "techCenter": "2100"},
                    ]
                }
            }
        )

        assert result["integration_ready"] is True
        links = result["available_links"]
        assert links["patent_file_wrapper"]["count"] == 2  # deduped from 3 docs
        assert set(links["patent_file_wrapper"]["sample"]) == {"16751234", "16751235"}
        assert links["art_units"]["count"] == 1
        assert links["art_units"]["sample"] == ["2854"]
        assert links["tech_centers"]["count"] == 1
        assert links["tech_centers"]["sample"] == ["2100"]
        # No publicationNumber in any doc -> ptab link stays empty
        assert links["ptab"]["count"] == 0
        assert links["ptab"]["sample"] == []

    def test_records_without_application_numbers_but_with_publication_numbers(self):
        service = _service()

        result = service._get_cross_mcp_links(
            {
                "response": {
                    "docs": [
                        {"publicationNumber": "US10701173B2"},
                        {"publicationNumber": "US10701173B2"},  # duplicate
                    ]
                }
            }
        )

        # No application numbers, but publication numbers alone still flip
        # integration_ready True (the `or` in the source).
        assert result["integration_ready"] is True
        links = result["available_links"]
        assert links["patent_file_wrapper"]["count"] == 0
        assert links["ptab"]["count"] == 1
        assert links["ptab"]["sample"] == ["US10701173B2"]

    def test_records_with_only_art_unit_and_tech_center_not_integration_ready(self):
        """art_units/tech_centers alone don't flip integration_ready — only
        application/patent numbers do (per the `or` condition in source)."""
        service = _service()

        result = service._get_cross_mcp_links(
            {
                "response": {
                    "docs": [
                        {"groupArtUnitNumber": "2854", "techCenter": "2100"},
                    ]
                }
            }
        )

        assert result["integration_ready"] is False
        links = result["available_links"]
        assert links["art_units"]["count"] == 1
        assert links["tech_centers"]["count"] == 1
        assert links["patent_file_wrapper"]["count"] == 0
        assert links["ptab"]["count"] == 0

    def test_sample_capped_at_five(self):
        service = _service()

        docs = [{"patentApplicationNumber": str(16000000 + i)} for i in range(8)]
        result = service._get_cross_mcp_links({"response": {"docs": docs}})

        assert result["available_links"]["patent_file_wrapper"]["count"] == 8
        assert len(result["available_links"]["patent_file_wrapper"]["sample"]) == 5

    def test_malformed_input_falls_back_to_error_response(self):
        """search_result that isn't dict-shaped (e.g. None) raises inside the
        try block; the except handler must degrade gracefully rather than
        propagate."""
        service = _service()

        result = service._get_cross_mcp_links(None)

        assert result["integration_ready"] is False
        assert result["available_links"] == {}
        assert "error" in result
