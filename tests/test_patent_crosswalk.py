"""Granted-patent-number crosswalk: normalizer, HTTP client, tool wiring.

Before this crosswalk existed, `patent_number` mapped straight to
`publicationNumber` — which holds 11-digit PRE-GRANT publication numbers — so a
granted patent number returned a clean zero that reads as "never cited", and the
OA lane had no patent-number path at all. These tests pin the three pieces that
replaced that: how a caller's value is read (`normalize_patent_number`), the one
metered ODP applications-search call that resolves it
(`ApplicationsCrosswalkClient`), and what each of the four search tools does with
the result, including the self-report and the refusals.

No network: the client's `_send` choke point is replaced with fake httpx
responses, and the tool tests use the `mock_runtime` fixture's crosswalk client.
"""

import httpx
import pytest

from uspto_enriched_citation_mcp.api.applications_client import (
    ApplicationsCrosswalkClient,
)
from uspto_enriched_citation_mcp.shared.circuit_breaker import CircuitBreaker
from uspto_enriched_citation_mcp.tools.oa import (
    search_oa_citations_balanced,
    search_oa_citations_minimal,
)
from uspto_enriched_citation_mcp.tools.search import (
    search_citations_balanced,
    search_citations_minimal,
)
from uspto_enriched_citation_mcp.util.cache import LRUCache
from uspto_enriched_citation_mcp.util.patent_crosswalk import (
    GRANTED_PATENT,
    PUBLICATION,
    NormalizedPatentNumber,
    PatentNumberConflictError,
    PatentNumberFormatError,
    PatentNumberNotFoundError,
    normalize_patent_number,
    resolve_patent_number_param,
)

# Patent 7,971,071 -> application 11752072 (live-verified 2026-09-03 against
# the ODP applications search endpoint; both citation lanes return records for
# that application).
PATENT = "7971071"
APPLICATION = "11752072"

_MINIMAL_DOC = {
    "id": "0de7ea10c59e03dab218a40dece9dffd",
    "patentApplicationNumber": APPLICATION,
    "publicationNumber": "US20080294901A1",
    "groupArtUnitNumber": "2432",
    "citedDocumentIdentifier": "US1234567B2",
    "citationCategoryCode": "X",
    "techCenter": "2400",
    "officeActionDate": "2008-09-08",
    "examinerCitedReferenceIndicator": True,
}
_SEARCH_RESPONSE = {"response": {"start": 0, "numFound": 1, "docs": [dict(_MINIMAL_DOC)]}}

_OA_DOC = {
    "patentApplicationNumber": APPLICATION,
    "groupArtUnitNumber": "2432",
    "techCenter": "2400",
    "referenceIdentifier": "PAVLIN et al. US 2001/0056539 A1",
    "actionTypeCategory": "",
    "examinerCitedReferenceIndicator": False,
    "createDateTime": "2025-07-17T18:12:44",
}
_OA_SEARCH_RESPONSE = {"response": {"numFound": 1, "docs": [dict(_OA_DOC)]}}


# ------------------------------------------------------------- normalizer


class TestNormalizePatentNumber:
    @pytest.mark.parametrize(
        "raw",
        ["7971071", "7,971,071", "US7971071", "US 7,971,071", "us-7971071", " 7971071 "],
    )
    def test_granted_forms_normalize_to_digits(self, raw):
        """Commas, whitespace and a US prefix are punctuation, not meaning."""
        result = normalize_patent_number(raw)

        assert result == NormalizedPatentNumber(
            raw=raw.strip(), number="7971071", kind=GRANTED_PATENT
        )

    def test_eight_digit_number_is_read_as_a_granted_patent(self):
        """Patent numbers passed 10,000,000 in 2018, so 8 digits is ambiguous
        with an application serial. `patent_number` resolves the ambiguity by
        namespace: this parameter always means a patent."""
        assert normalize_patent_number("10123456").kind == GRANTED_PATENT

    def test_eleven_digits_is_a_publication_number(self):
        result = normalize_patent_number("20060075466")

        assert result.kind == PUBLICATION
        assert result.number == "20060075466"

    @pytest.mark.parametrize(
        "raw", ["123456", "123456789", "123456789012", "US", "", "   ", "7971071B2"]
    )
    def test_unrecognized_shapes_are_refused_by_name(self, raw):
        with pytest.raises(PatentNumberFormatError) as excinfo:
            normalize_patent_number(raw)

        message = str(excinfo.value)
        assert "granted patent number" in message
        assert "publication number" in message
        assert "application serial" in message


# ------------------------------------------------------ crosswalk client


def _client(**kwargs):
    """A crosswalk client with its own cache and breaker (no global state)."""
    return ApplicationsCrosswalkClient(
        api_key="x" * 32,
        enable_cache=kwargs.pop("enable_cache", False),
        search_cache=kwargs.pop("search_cache", None),
        circuit_breaker=CircuitBreaker(failure_threshold=99),
        **kwargs,
    )


def _fake_send(response, calls):
    async def _send(method, url, **kwargs):
        calls.append({"method": method, "url": url, **kwargs})
        return response

    return _send


class TestApplicationsCrosswalkClient:
    @pytest.mark.asyncio
    async def test_hit_returns_the_application_number(self):
        client = _client()
        calls = []
        client._send = _fake_send(
            httpx.Response(
                200,
                json={
                    "count": 1,
                    "patentFileWrapperDataBag": [
                        {
                            "applicationNumberText": APPLICATION,
                            "applicationMetaData": {"patentNumber": PATENT},
                        }
                    ],
                },
            ),
            calls,
        )

        assert await client.find_application_number(PATENT) == APPLICATION
        assert calls[0]["method"] == "POST"
        assert calls[0]["url"].endswith("/api/v1/patent/applications/search")
        assert calls[0]["json"]["q"] == f"applicationMetaData.patentNumber:{PATENT}"
        assert calls[0]["json"]["pagination"]["limit"] == 1

    @pytest.mark.asyncio
    async def test_404_is_a_miss_not_a_failure(self):
        """USPTO answers an empty applications search with HTTP 404 and
        "No matching records found" (verified live). That is an answer about
        the patent number, not a transport error, so it must not raise."""
        client = _client()
        client._send = _fake_send(
            httpx.Response(
                404,
                json={
                    "code": "404",
                    "detailedMessage": "No matching records found, refine your "
                    "search criteria and try again",
                },
            ),
            [],
        )

        assert await client.find_application_number("99999999") is None

    @pytest.mark.asyncio
    async def test_empty_bag_is_a_miss(self):
        client = _client()
        client._send = _fake_send(
            httpx.Response(200, json={"count": 0, "patentFileWrapperDataBag": []}), []
        )

        assert await client.find_application_number("99999999") is None

    @pytest.mark.asyncio
    async def test_hit_on_a_different_patent_number_is_reported_as_a_miss(self):
        """Answering about the wrong application is worse than answering
        nothing, so a record whose patentNumber is not the one asked for is
        discarded rather than returned."""
        client = _client()
        client._send = _fake_send(
            httpx.Response(
                200,
                json={
                    "patentFileWrapperDataBag": [
                        {
                            "applicationNumberText": "16816197",
                            "applicationMetaData": {"patentNumber": "11752072"},
                        }
                    ]
                },
            ),
            [],
        )

        assert await client.find_application_number(PATENT) is None

    @pytest.mark.asyncio
    async def test_repeat_lookup_is_served_from_cache(self):
        """A granted patent's application serial never changes, so the second
        ask costs no USPTO call."""
        calls = []
        client = _client(enable_cache=True, search_cache=LRUCache(max_size=10))
        client._send = _fake_send(
            httpx.Response(
                200,
                json={
                    "patentFileWrapperDataBag": [
                        {
                            "applicationNumberText": APPLICATION,
                            "applicationMetaData": {"patentNumber": PATENT},
                        }
                    ]
                },
            ),
            calls,
        )

        assert await client.find_application_number(PATENT) == APPLICATION
        assert await client.find_application_number(PATENT) == APPLICATION
        assert len(calls) == 1


# --------------------------------------------------- resolve_patent_number_param


async def _hit(patent_number):
    return APPLICATION


async def _miss(patent_number):
    return None


class TestResolvePatentNumberParam:
    @pytest.mark.asyncio
    async def test_granted_patent_note_reports_the_whole_mapping(self):
        resolution = await resolve_patent_number_param("7,971,071", resolver=_hit)

        assert resolution.application_number == APPLICATION
        assert resolution.publication_number is None
        assert resolution.note == {
            "input": "7,971,071",
            "interpreted_as": "granted_patent",
            "resolved_application_number": APPLICATION,
            "queried_field": "patentApplicationNumber",
            "source": "USPTO ODP applications search",
        }

    @pytest.mark.asyncio
    async def test_publication_number_is_not_crosswalked(self):
        resolution = await resolve_patent_number_param("20060075466", resolver=_hit)

        assert resolution.publication_number == "20060075466"
        assert resolution.application_number is None
        assert resolution.note == {
            "input": "20060075466",
            "interpreted_as": "publication",
            "queried_field": "publicationNumber",
        }

    @pytest.mark.asyncio
    async def test_miss_raises_with_the_accepted_forms(self):
        with pytest.raises(PatentNumberNotFoundError) as excinfo:
            await resolve_patent_number_param("9999998", resolver=_miss)

        assert "granted patent number" in str(excinfo.value)
        assert "application serial" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_agreeing_application_number_is_accepted(self):
        """A slash-and-comma serial is the same application as the crosswalk's
        digits, so it is not a conflict."""
        resolution = await resolve_patent_number_param(
            PATENT, "11/752,072", resolver=_hit
        )

        assert resolution.application_number == APPLICATION

    @pytest.mark.asyncio
    async def test_disagreeing_application_number_is_refused(self):
        with pytest.raises(PatentNumberConflictError) as excinfo:
            await resolve_patent_number_param(PATENT, "16816197", resolver=_hit)

        assert APPLICATION in str(excinfo.value)
        assert "16816197" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_publication_number_is_refused_where_the_lane_has_no_field(self):
        with pytest.raises(PatentNumberFormatError) as excinfo:
            await resolve_patent_number_param(
                "20060075466", resolver=_hit, allow_publication=False
            )

        assert "Office Action Citations" in str(excinfo.value)


# ------------------------------------------------------------- tool wiring


class TestEnrichedSearchCrosswalk:
    @pytest.mark.asyncio
    async def test_granted_patent_number_queries_the_application(self, mock_runtime):
        mock_runtime.crosswalk_client.find_application_number.return_value = APPLICATION
        mock_runtime.api_client.search_records.return_value = _SEARCH_RESPONSE

        result = await search_citations_minimal(patent_number="7,971,071", rows=5)

        query = mock_runtime.api_client.search_records.call_args[0][0]
        assert f"patentApplicationNumber:{APPLICATION}" in query
        assert "publicationNumber" not in query
        assert result["patent_number_resolution"]["interpreted_as"] == "granted_patent"
        assert (
            result["patent_number_resolution"]["resolved_application_number"]
            == APPLICATION
        )
        mock_runtime.crosswalk_client.find_application_number.assert_awaited_once_with(
            "7971071"
        )

    @pytest.mark.asyncio
    async def test_publication_number_still_queries_publication_number(
        self, mock_runtime
    ):
        mock_runtime.api_client.search_records.return_value = _SEARCH_RESPONSE

        result = await search_citations_balanced(patent_number="20060075466", rows=3)

        query = mock_runtime.api_client.search_records.call_args[0][0]
        assert "publicationNumber:20060075466" in query
        assert result["patent_number_resolution"]["interpreted_as"] == "publication"
        assert "resolved_application_number" not in result["patent_number_resolution"]
        mock_runtime.crosswalk_client.find_application_number.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unresolvable_patent_number_is_a_400_not_a_zero_result(
        self, mock_runtime
    ):
        mock_runtime.crosswalk_client.find_application_number.return_value = None

        result = await search_citations_minimal(patent_number="9999998")

        assert result["status"] == "error"
        assert result["code"] == 400
        assert "granted patent number" in result["error"]
        mock_runtime.api_client.search_records.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_conflicting_identifiers_are_a_400(self, mock_runtime):
        mock_runtime.crosswalk_client.find_application_number.return_value = APPLICATION

        result = await search_citations_balanced(
            patent_number=PATENT, application_number="16816197"
        )

        assert result["code"] == 400
        assert "conflicts" in result["error"]
        mock_runtime.api_client.search_records.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_patent_number_leaves_the_response_unchanged(self, mock_runtime):
        mock_runtime.api_client.search_records.return_value = _SEARCH_RESPONSE

        result = await search_citations_minimal(criteria="techCenter:2400", rows=5)

        assert "patent_number_resolution" not in result


class TestOASearchCrosswalk:
    @pytest.mark.asyncio
    async def test_granted_patent_number_reaches_the_oa_lane(self, mock_runtime):
        mock_runtime.crosswalk_client.find_application_number.return_value = APPLICATION
        mock_runtime.oa_client.search_records.return_value = _OA_SEARCH_RESPONSE

        result = await search_oa_citations_minimal(patent_number=PATENT, rows=5)

        query = mock_runtime.oa_client.search_records.call_args[0][0]
        assert query == f"patentApplicationNumber:{APPLICATION}"
        assert (
            result["patent_number_resolution"]["resolved_application_number"]
            == APPLICATION
        )

    @pytest.mark.asyncio
    async def test_balanced_tier_crosswalks_too(self, mock_runtime):
        mock_runtime.crosswalk_client.find_application_number.return_value = APPLICATION
        mock_runtime.oa_client.search_records.return_value = _OA_SEARCH_RESPONSE

        result = await search_oa_citations_balanced(patent_number=PATENT, rows=5)

        query = mock_runtime.oa_client.search_records.call_args[0][0]
        assert query == f"patentApplicationNumber:{APPLICATION}"
        assert result["patent_number_resolution"]["source"] == (
            "USPTO ODP applications search"
        )

    @pytest.mark.asyncio
    async def test_publication_number_is_refused_on_the_oa_lane(self, mock_runtime):
        result = await search_oa_citations_minimal(patent_number="20060075466")

        assert result["code"] == 400
        assert "publication number" in result["error"]
        mock_runtime.oa_client.search_records.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_conflicting_identifiers_are_a_400(self, mock_runtime):
        mock_runtime.crosswalk_client.find_application_number.return_value = APPLICATION

        result = await search_oa_citations_minimal(
            patent_number=PATENT, application_number="16816197"
        )

        assert result["code"] == 400
        assert "conflicts" in result["error"]
        mock_runtime.oa_client.search_records.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_patent_number_is_the_last_parameter(self):
        """Appended last on purpose: the OA tools' existing positional order is
        part of their published schema."""
        import inspect

        for tool in (search_oa_citations_minimal, search_oa_citations_balanced):
            params = list(inspect.signature(tool).parameters)
            assert params[-1] == "patent_number"
