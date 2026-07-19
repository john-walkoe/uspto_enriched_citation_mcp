"""Tool-level happy-path tests (audit item 1c) plus the 4a security-logging
side-effect test.

Each of the 10 non-admin MCP tool functions is invoked directly (imported
from its tools/ module) with the `mock_runtime` fixture (tests/conftest.py)
patching runtime.* to mocked clients wrapped in real service objects. For
each tool we assert the expected top-level response shape and, where cheap,
that the mocked client was called with the expected arguments.

`citations_manage_users` (admin) is intentionally excluded — out of scope
for this audit item.
"""

import json

import pytest

from uspto_enriched_citation_mcp import runtime
from uspto_enriched_citation_mcp.tools.details import get_citation_details
from uspto_enriched_citation_mcp.tools.oa import (
    get_oa_citation_fields,
    search_oa_citations_balanced,
    search_oa_citations_minimal,
)
from uspto_enriched_citation_mcp.tools.search import (
    search_citations_balanced,
    search_citations_minimal,
)
from uspto_enriched_citation_mcp.tools.statistics import get_citation_statistics
from uspto_enriched_citation_mcp.tools.utility import (
    citations_get_guidance,
    get_available_fields,
    validate_query,
)

# --------------------------------------------------------------------- data

_MINIMAL_DOC = {
    "id": "0de7ea10c59e03dab218a40dece9dffd",
    "patentApplicationNumber": "16751234",
    "publicationNumber": "US20200123456A1",
    "groupArtUnitNumber": "2854",
    "citedDocumentIdentifier": "US1234567B2",
    "citationCategoryCode": "X",
    "techCenter": "2100",
    "officeActionDate": "2023-01-01",
    "examinerCitedReferenceIndicator": True,
}

_BALANCED_DOC = {
    **_MINIMAL_DOC,
    "passageLocationText": "col. 3, ll. 12-20",
    "officeActionCategory": "CTNF",
    "relatedClaimNumberText": "1, 4",
    "nplIndicator": False,
    "workGroupNumber": "2854",
    "kindCode": "B2",
    "countryCode": "US",
    "qualitySummaryText": "High relevance",
    "inventorNameText": "Smith, John",
    "applicantCitedExaminerReferenceIndicator": False,
    "createDateTime": "2023-01-01T00:00:00Z",
}

_SEARCH_RESPONSE = {
    "response": {"start": 0, "numFound": 1, "docs": [dict(_MINIMAL_DOC)]}
}

_BALANCED_RESPONSE = {
    "response": {"start": 0, "numFound": 1, "docs": [dict(_BALANCED_DOC)]}
}

_FIELDS_RESPONSE = {
    "fields": [
        {"name": "patentApplicationNumber", "type": "string"},
        {"name": "techCenter", "type": "string"},
    ]
}

_OA_DOC = {
    "patentApplicationNumber": "16751234",
    "groupArtUnitNumber": "2854",
    "techCenter": "2100",
    "referenceIdentifier": "US1234567B2",
    "actionTypeCategory": "OA",
    "examinerCitedReferenceIndicator": True,
    "createDateTime": "2023-01-01T00:00:00Z",
}

_OA_SEARCH_RESPONSE = {"response": {"numFound": 1, "docs": [dict(_OA_DOC)]}}


# ------------------------------------------------------------- utility.py


class TestGetAvailableFields:
    @pytest.mark.asyncio
    async def test_returns_status_and_fields(self, mock_runtime):
        mock_runtime.api_client.get_fields.return_value = _FIELDS_RESPONSE

        result = await get_available_fields()

        assert result["status"] == "success"
        assert result["total_fields"] == 2
        assert result["fields"] == _FIELDS_RESPONSE["fields"]
        assert "usage_guidance" in result
        mock_runtime.api_client.get_fields.assert_awaited_once_with()


class TestValidateQuery:
    @pytest.mark.asyncio
    async def test_valid_query_returns_success(self, mock_runtime):
        query = "techCenter:2100 AND groupArtUnitNumber:2854"
        mock_runtime.api_client.validate_query.return_value = {
            "status": "success",
            "valid": True,
            "query": query,
            "message": "Query validation passed",
        }

        result = await validate_query(query, field_set="citations_minimal")

        assert result["status"] == "success"
        assert result["valid"] is True
        assert result["query"] == query
        assert result["field_set"] == "citations_minimal"
        mock_runtime.api_client.validate_query.assert_awaited_once_with(query)


class TestCitationsGetGuidance:
    @pytest.mark.asyncio
    async def test_overview_section_returns_focused_text(self):
        result = await citations_get_guidance(section="overview")

        # citations_get_guidance returns a plain guidance string (its own
        # docstring documents "Returns: str"), not a dict — asserted here to
        # pin the actual contract.
        assert isinstance(result, str)
        assert "Overview" in result
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_invalid_section_returns_message_listing_available(self):
        result = await citations_get_guidance(section="not_a_real_section")

        assert isinstance(result, str)
        assert "Invalid section" in result
        assert "overview" in result


# -------------------------------------------------------------- search.py


class TestSearchCitationsMinimal:
    @pytest.mark.asyncio
    async def test_happy_path_returns_results_and_query_info(self, mock_runtime):
        mock_runtime.api_client.search_records.return_value = _SEARCH_RESPONSE

        result = await search_citations_minimal(criteria="techCenter:2100", rows=10)

        assert "response" in result
        assert result["response"]["docs"][0]["patentApplicationNumber"] == "16751234"
        assert "query_info" in result
        assert result["query_info"]["tier"] == "minimal"
        assert "cross_mcp" in result["query_info"]
        assert result["query_info"]["cross_mcp"]["integration_ready"] is True
        assert "guidance" in result

        args, _ = mock_runtime.api_client.search_records.call_args
        query, start, rows, fields = args
        assert "techCenter:2100" in query
        assert start == 0
        assert rows == 10
        assert isinstance(fields, list) and len(fields) == 8  # citations_minimal set

    @pytest.mark.asyncio
    async def test_rejects_invalid_criteria_before_calling_client(self, mock_runtime):
        result = await search_citations_minimal(criteria="techCenter:(unbalanced")

        assert result["status"] == "error"
        assert result["code"] == 400
        mock_runtime.api_client.search_records.assert_not_awaited()


class TestSearchCitationsBalanced:
    @pytest.mark.asyncio
    async def test_happy_path_returns_results_and_query_info(self, mock_runtime):
        mock_runtime.api_client.search_records.return_value = _BALANCED_RESPONSE

        result = await search_citations_balanced(criteria="techCenter:2100", rows=5)

        assert "response" in result
        assert result["response"]["docs"][0]["passageLocationText"]
        assert result["query_info"]["tier"] == "balanced"
        assert result["guidance"]["analysis_ready"] is True
        assert result["guidance"]["passage_analysis"] == 1

        args, _ = mock_runtime.api_client.search_records.call_args
        query, start, rows, fields = args
        assert "techCenter:2100" in query
        assert rows == 5
        assert len(fields) == 19  # citations_balanced set (field_configs.yaml)


# ------------------------------------------------------------- details.py


class TestGetCitationDetails:
    @pytest.mark.asyncio
    async def test_happy_path_returns_status_and_pfw_guidance(self, mock_runtime):
        citation_id = "0de7ea10c59e03dab218a40dece9dffd"
        # CitationService.get_details() delegates straight to
        # client.get_citation_details() (not search_records) — mock that
        # method with the shape EnrichedCitationClient.get_citation_details
        # actually returns (see api/enriched_client.py).
        mock_runtime.api_client.get_citation_details.return_value = {
            "status": "success",
            "citation_id": citation_id,
            "citation": {
                "id": citation_id,
                "patentApplicationNumber": "16751234",
                "officeActionCategory": "CTNF",
            },
            "context_level": "full",
            "note": "Citation record with full context level",
        }

        result = await get_citation_details(citation_id)

        assert result["status"] == "success"
        assert result["citation"]["patentApplicationNumber"] == "16751234"
        assert "pfw_document_retrieval_guidance" in result
        assert (
            result["pfw_document_retrieval_guidance"]["suggested_document_code"]
            == "CTNF"
        )
        mock_runtime.api_client.get_citation_details.assert_awaited_once_with(
            citation_id=citation_id, include_context=True
        )

    @pytest.mark.asyncio
    async def test_rejects_malformed_id_before_calling_client(self, mock_runtime):
        result = await get_citation_details("not-a-valid-id")

        assert result["status"] == "error"
        assert result["code"] == 400
        mock_runtime.api_client.get_citation_details.assert_not_awaited()


# ----------------------------------------------------------- statistics.py


class TestGetCitationStatistics:
    @pytest.mark.asyncio
    async def test_happy_path_returns_status_and_breakdowns(self, mock_runtime):
        mock_runtime.api_client.search_citations.return_value = {
            "response": {"numFound": 42}
        }

        result = await get_citation_statistics(criteria="techCenter:2100")

        assert result["status"] == "success"
        assert result["total_citations"] == 42
        assert "breakdowns" in result
        assert mock_runtime.api_client.search_citations.await_count == 6


# ------------------------------------------------------------------ oa.py


class TestSearchOACitationsMinimal:
    @pytest.mark.asyncio
    async def test_happy_path_returns_response_and_query_info(self, mock_runtime):
        mock_runtime.oa_client.search_records.return_value = _OA_SEARCH_RESPONSE

        result = await search_oa_citations_minimal(
            criteria="", application_number="16751234", rows=10
        )

        assert "response" in result
        assert result["response"]["docs"][0]["_pfw_link"]
        assert result["query_info"]["api"] == "oa_citations_v2"
        assert result["query_info"]["tier"] == "minimal"
        assert "guidance" in result

        args, _ = mock_runtime.oa_client.search_records.call_args
        query, start, rows, fields = args
        assert "patentApplicationNumber:16751234" in query
        assert start == 0
        assert rows == 10

    @pytest.mark.asyncio
    async def test_requires_at_least_one_criterion(self, mock_runtime):
        result = await search_oa_citations_minimal()

        assert result["status"] == "error"
        assert result["code"] == 400
        mock_runtime.oa_client.search_records.assert_not_awaited()


class TestSearchOACitationsBalanced:
    @pytest.mark.asyncio
    async def test_happy_path_returns_response_and_query_info(self, mock_runtime):
        mock_runtime.oa_client.search_records.return_value = _OA_SEARCH_RESPONSE

        result = await search_oa_citations_balanced(
            criteria="", tech_center="2100", rows=25
        )

        assert "response" in result
        assert result["query_info"]["api"] == "oa_citations_v2"
        assert result["query_info"]["tier"] == "balanced"

        args, _ = mock_runtime.oa_client.search_records.call_args
        query, start, rows, fields = args
        assert "techCenter:2100" in query


class TestGetOACitationFields:
    @pytest.mark.asyncio
    async def test_happy_path_returns_status_and_fields(self, mock_runtime):
        mock_runtime.oa_client.get_fields.return_value = _FIELDS_RESPONSE

        result = await get_oa_citation_fields()

        assert result["status"] == "success"
        assert result["api"] == "oa_citations_v2"
        assert result["fields"] == _FIELDS_RESPONSE["fields"]
        mock_runtime.oa_client.get_fields.assert_awaited_once_with()


# ------------------------------------------------------- 4a: security logging
# side effect from a real tool function. A criteria string containing an
# injection pattern is rejected by validate_lucene_syntax's
# _check_injection_patterns check, which logs a security event through the
# module-level singleton returned by get_security_logger(). Patch that
# singleton's underlying stdlib logger.log (same seam used by
# tests/test_medium_security_fixes.py's M6 tests) to capture the event
# without needing real file I/O, and assert the raw criteria text never
# appears in the emitted payload.


class TestSecurityLoggingSideEffect:
    @pytest.mark.asyncio
    async def test_injection_pattern_in_search_criteria_logs_sanitized_event(
        self, mock_runtime
    ):
        from unittest.mock import patch

        from uspto_enriched_citation_mcp.util.security_logger import (
            get_security_logger,
        )

        secret_criteria = "techCenter:<script>confidential-matter-9001</script>"
        security_logger = get_security_logger()

        with patch.object(security_logger.logger, "log") as mock_log:
            result = await search_citations_minimal(criteria=secret_criteria)

        assert result["status"] == "error"
        assert result["code"] == 400
        mock_runtime.api_client.search_records.assert_not_awaited()

        assert mock_log.called
        found_injection_event = False
        for call in mock_log.call_args_list:
            logged_json = call.args[1]
            assert secret_criteria not in logged_json
            assert "confidential-matter-9001" not in logged_json
            payload = json.loads(logged_json)
            if payload["event_type"] == "injection_attempt":
                found_injection_event = True
                assert payload["query_len"] == len(secret_criteria)
                assert len(payload["query_sha"]) == 12
                assert "query" not in payload
                assert "criteria" not in payload
        assert found_injection_event
