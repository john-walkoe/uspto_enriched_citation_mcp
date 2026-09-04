"""The cross-lane `referenceKey` and the blank-reference envelope count.

The defect these pin: the two citation lanes write the same reference
differently, so a client unioning them on the raw identifier fields found zero
overlap on every application. Measured on app 12849948, 2026-09-04 - OA
`parsedReferenceIdentifier` "20060075466" against enriched
`citedDocumentIdentifier` "US 2006/0075466 A1", when four references are in
fact in both lanes. Separately, enriched rows can carry an empty
`publicationNumber` with a null, empty or ABSENT `citedDocumentIdentifier`
(2 of 5 on 11752072, 4 of 8 on 12849948, 4 of 26 on 18407147) and nothing on
the envelope counted them.
"""

import json

import pytest

from uspto_enriched_citation_mcp.api.oa_citations_client import (
    OA_CITATIONS_MINIMAL_FIELDS,
)
from uspto_enriched_citation_mcp.tools.details import get_citation_details
from uspto_enriched_citation_mcp.tools.oa import (
    search_oa_citations_balanced,
    search_oa_citations_minimal,
)
from uspto_enriched_citation_mcp.tools.search import (
    search_citations_balanced,
    search_citations_minimal,
)
from uspto_enriched_citation_mcp.util.reference_key import (
    ENRICHED_REFERENCE_SOURCE_FIELDS,
    OA_REFERENCE_SOURCE_FIELDS,
    REFERENCE_KEY_FIELD,
    count_rows_without_reference,
    normalize_reference_key,
    reference_key_for_doc,
)


class TestNormalizeReferenceKey:
    def test_the_two_lanes_collapse_to_one_key(self):
        """The whole point: every form of the app-12849948 reference is one
        key, so a union across lanes actually joins."""
        assert normalize_reference_key("20060075466") == "20060075466"
        assert normalize_reference_key("US 2006/0075466 A1") == "20060075466"
        assert normalize_reference_key("US-2006/0075466-A1") == "20060075466"
        assert normalize_reference_key("US20060075466A1") == "20060075466"

    def test_granted_patent_forms(self):
        for written in (
            "9280610",
            "9,280,610",
            "US 9,280,610 B2",
            "US9280610B2",
            "US-9280610-B2",
        ):
            assert normalize_reference_key(written) == "9280610", written

    def test_series_markers_are_preserved(self):
        assert normalize_reference_key("US RE38,124 E") == "RE38124"
        assert normalize_reference_key("RE38124") == "RE38124"
        assert normalize_reference_key("US D456,789 S") == "D456789"

    def test_raw_892_string_with_inventor_name_attached(self):
        """The OA minimal tier's `referenceIdentifier` is the raw 892 string;
        the reference leads and the inventor name trails it."""
        assert (
            normalize_reference_key("20060075466 A1 KAWAI; TAKESHI")
            == "20060075466"
        )
        assert (
            normalize_reference_key("US-20060075466-A1 KAWAI; TAKESHI et al.")
            == "20060075466"
        )
        assert normalize_reference_key("US 9,280,610 B2 to Smith") == "9280610"

    def test_non_patent_literature_and_blanks_are_none(self):
        """A year or a page range inside a free-text citation must never be
        mistaken for a document number."""
        assert (
            normalize_reference_key(
                "Smith et al., 'Foo Bar', Journal of Things, 2006, pp. 123-145."
            )
            is None
        )
        assert normalize_reference_key("") is None
        assert normalize_reference_key("   ") is None
        assert normalize_reference_key(None) is None
        assert normalize_reference_key(True) is None
        assert normalize_reference_key({"a": 1}) is None

    def test_multivalued_and_numeric_values(self):
        assert normalize_reference_key(["US 2006/0075466 A1"]) == "20060075466"
        assert normalize_reference_key(20060075466) == "20060075466"


class TestReferenceKeyForDoc:
    def test_enriched_prefers_publication_number(self):
        doc = {
            "publicationNumber": "20060075466",
            "citedDocumentIdentifier": "US 2006/0075466 A1",
        }
        assert (
            reference_key_for_doc(doc, ENRICHED_REFERENCE_SOURCE_FIELDS)
            == "20060075466"
        )

    def test_enriched_falls_back_to_cited_document_identifier(self):
        doc = {"publicationNumber": "", "citedDocumentIdentifier": "US 9,280,610 B2"}
        assert reference_key_for_doc(doc, ENRICHED_REFERENCE_SOURCE_FIELDS) == "9280610"

    def test_absent_null_and_empty_are_one_state(self):
        """Three JSON shapes, one meaning: this row has no joinable
        reference."""
        absent = {"publicationNumber": ""}
        null = {"publicationNumber": "", "citedDocumentIdentifier": None}
        empty = {"publicationNumber": "", "citedDocumentIdentifier": ""}
        for doc in (absent, null, empty):
            assert reference_key_for_doc(doc, ENRICHED_REFERENCE_SOURCE_FIELDS) is None

    def test_oa_falls_back_to_the_raw_892_string(self):
        """The minimal tier used to carry no parsed identifier at all."""
        doc = {"referenceIdentifier": "US-20060075466-A1 KAWAI; TAKESHI"}
        assert reference_key_for_doc(doc, OA_REFERENCE_SOURCE_FIELDS) == "20060075466"

    def test_count_rows_without_reference(self):
        assert count_rows_without_reference(["1", None, "2", None]) == 2
        assert count_rows_without_reference([]) == 0


def _enriched_payload():
    """Four rows in the shape app 12849948 actually returns: two joinable,
    and the three distinct blank shapes the tester round found."""
    return {
        "response": {
            "numFound": 4,
            "start": 0,
            "docs": [
                {
                    "id": "a" * 32,
                    "patentApplicationNumber": "12849948",
                    "publicationNumber": "20060075466",
                    "citedDocumentIdentifier": "US 2006/0075466 A1",
                },
                {
                    "id": "b" * 32,
                    "patentApplicationNumber": "12849948",
                    "publicationNumber": "",
                    "citedDocumentIdentifier": "US 9,280,610 B2",
                },
                # publicationNumber empty, citedDocumentIdentifier ABSENT
                {
                    "id": "c" * 32,
                    "patentApplicationNumber": "12849948",
                    "publicationNumber": "",
                },
                # publicationNumber empty, citedDocumentIdentifier null
                {
                    "id": "d" * 32,
                    "patentApplicationNumber": "12849948",
                    "publicationNumber": "",
                    "citedDocumentIdentifier": None,
                },
            ],
        }
    }


def _oa_payload():
    return {
        "response": {
            "numFound": 2,
            "start": 0,
            "docs": [
                {
                    "id": "e" * 32,
                    "patentApplicationNumber": "12849948",
                    "groupArtUnitNumber": "2854",
                    "techCenter": "2100",
                    "referenceIdentifier": "US-20060075466-A1 KAWAI; TAKESHI",
                    "parsedReferenceIdentifier": "20060075466",
                    "actionTypeCategory": "rejected",
                    "legalSectionCode": "103",
                    "examinerCitedReferenceIndicator": True,
                    "createDateTime": "2025-03-11T00:00:00Z",
                },
                {
                    "id": "f" * 32,
                    "patentApplicationNumber": "12849948",
                    "groupArtUnitNumber": "2854",
                    "techCenter": "2100",
                    # No parsed identifier at all: the key has to come off the
                    # raw 892 string.
                    "referenceIdentifier": "US 9,280,610 B2 to Smith",
                    "actionTypeCategory": "rejected",
                    "examinerCitedReferenceIndicator": True,
                    "createDateTime": "2025-03-11T00:00:00Z",
                },
            ],
        }
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool", [search_citations_minimal, search_citations_balanced]
)
async def test_enriched_tiers_carry_the_key_and_the_count(mock_runtime, tool):
    mock_runtime.api_client.search_records.return_value = _enriched_payload()

    result = await tool(criteria="patentApplicationNumber:12849948")

    keys = [doc[REFERENCE_KEY_FIELD] for doc in result["response"]["docs"]]
    assert keys == ["20060075466", "9280610", None, None]
    # Always present, 0 included: an absent key would read as "none", which is
    # exactly the silent loss this count exists to prevent.
    assert result["rows_without_reference_identifier"] == 2


@pytest.mark.asyncio
async def test_enriched_count_is_present_when_zero(mock_runtime):
    payload = _enriched_payload()
    payload["response"]["docs"] = payload["response"]["docs"][:2]
    mock_runtime.api_client.search_records.return_value = payload

    result = await search_citations_minimal(criteria="techCenter:2100")

    assert result["rows_without_reference_identifier"] == 0


@pytest.mark.asyncio
async def test_enriched_ultra_minimal_still_gets_the_best_key(mock_runtime):
    """A custom `fields` list can drop both source fields. The key is computed
    from the UNFILTERED upstream doc, so it survives anyway."""
    mock_runtime.api_client.search_records.return_value = _enriched_payload()

    result = await search_citations_minimal(
        criteria="techCenter:2100", fields=["patentApplicationNumber"]
    )

    first = result["response"]["docs"][0]
    assert set(first) <= {"patentApplicationNumber", "id", REFERENCE_KEY_FIELD}
    assert first[REFERENCE_KEY_FIELD] == "20060075466"
    assert result["rows_without_reference_identifier"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool", [search_oa_citations_minimal, search_oa_citations_balanced]
)
async def test_oa_tiers_carry_the_key(mock_runtime, tool):
    mock_runtime.oa_client.search_records.return_value = _oa_payload()

    result = await tool(application_number="12849948")

    keys = [doc[REFERENCE_KEY_FIELD] for doc in result["response"]["docs"]]
    assert keys == ["20060075466", "9280610"]


@pytest.mark.asyncio
async def test_the_two_lanes_actually_join(mock_runtime):
    """The end-to-end statement of the defect: the same two references, read
    out of the two lanes, now union to two entries instead of four."""
    mock_runtime.api_client.search_records.return_value = _enriched_payload()
    enriched = await search_citations_minimal(
        criteria="patentApplicationNumber:12849948"
    )
    mock_runtime.oa_client.search_records.return_value = _oa_payload()
    oa = await search_oa_citations_minimal(application_number="12849948")

    enriched_keys = {
        d[REFERENCE_KEY_FIELD]
        for d in enriched["response"]["docs"]
        if d[REFERENCE_KEY_FIELD]
    }
    oa_keys = {
        d[REFERENCE_KEY_FIELD] for d in oa["response"]["docs"] if d[REFERENCE_KEY_FIELD]
    }

    assert enriched_keys & oa_keys == {"20060075466", "9280610"}
    assert enriched_keys | oa_keys == {"20060075466", "9280610"}

    # Joining the raw fields instead is the shipped falsehood: zero overlap.
    raw_enriched = {
        d.get("citedDocumentIdentifier")
        for d in _enriched_payload()["response"]["docs"]
        if d.get("citedDocumentIdentifier")
    }
    raw_oa = {
        d.get("parsedReferenceIdentifier")
        for d in _oa_payload()["response"]["docs"]
        if d.get("parsedReferenceIdentifier")
    }
    assert raw_enriched & raw_oa == set()


@pytest.mark.asyncio
async def test_details_carries_the_key(mock_runtime):
    mock_runtime.api_client.get_citation_details.return_value = {
        "citation": {
            "patentApplicationNumber": "12849948",
            "publicationNumber": "",
            "citedDocumentIdentifier": "US 2006/0075466 A1",
        }
    }

    result = await get_citation_details("0de7ea10c59e03dab218a40dece9dffd")

    assert result["citation"][REFERENCE_KEY_FIELD] == "20060075466"


def test_parsed_reference_identifier_is_in_the_oa_minimal_tier():
    """Added 2026-09-04: the discovery tier used to carry only the raw 892
    string, so it had no normalised reference at all."""
    assert "parsedReferenceIdentifier" in OA_CITATIONS_MINIMAL_FIELDS
    assert len(OA_CITATIONS_MINIMAL_FIELDS) == 8


def test_the_measured_byte_cost_of_the_two_new_row_fields():
    """What the tier's byte budget actually pays, so the number in
    api/oa_citations_client.py stays honest. A ratchet, not a target."""
    row = {
        "patentApplicationNumber": "16816197",
        "groupArtUnitNumber": "2854",
        "techCenter": "2100",
        "referenceIdentifier": "US-20060075466-A1 KAWAI; TAKESHI et al.",
        "actionTypeCategory": "rejected",
        "examinerCitedReferenceIndicator": True,
        "createDateTime": "2025-03-11T00:00:00Z",
    }
    with_parsed = dict(row, parsedReferenceIdentifier="20060075466")
    with_key = dict(with_parsed, referenceKey="20060075466")

    parsed_cost = len(json.dumps(with_parsed)) - len(json.dumps(row))
    key_cost = len(json.dumps(with_key)) - len(json.dumps(with_parsed))

    assert parsed_cost == 44
    assert key_cost == 31
    # A full 50-row minimal page grows by about 3,750 characters, which leaves
    # the discovery tier well under the balanced tier it is meant to undercut.
    assert 50 * (parsed_cost + key_cost) < 4000
