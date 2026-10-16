"""Ready-made citation links on every citation record.

The defect these pin: a suite walkthrough (2026-09-05) named three references
in prose as bare numbers, because the record JSON carried no link. The MCP App
panels build Google Patents and Patent Center links in the browser; the JSON
return paths the model reads carried none, so a citation in an answer was a
number the reader could not click.

URL shapes are the ones probed live on 2026-09-05 and recorded in
util/citation_links: Google Patents answers 200 for US6694384, US20010056539,
USRE38124, USD456789 and USPP12345, and 404 for US99999999 and USZZ999999999,
so a built URL names a document that exists. No kind code is ever appended
(USRE38124E is a 404).

The foreign shapes were probed the same way on 2026-09-12, after a second
defect: `publicationNumber` (bare digits) outranked `citedDocumentIdentifier`
("DE 10 2004 012345 A1"), so a German reference keyed as `102004012345` and
`cite_as` linked the US document with those digits. Google Patents answers 200
for JP2001123456, EP1234567, WO2010012345, KR20100012345, CN101234567 and
DE102005001234, and 404 for DE999999999999, JP9999999999, XX1234567 and
ZZ2001123456. No kind code is appended to these either: EP1234567A1 is a 404
where EP1234567 and EP1234567B1 are 200s.
"""

import pytest

from uspto_enriched_citation_mcp.tools.details import get_citation_details
from uspto_enriched_citation_mcp.tools.oa import (
    search_oa_citations_balanced,
    search_oa_citations_minimal,
)
from uspto_enriched_citation_mcp.tools.search import (
    search_citations_balanced,
    search_citations_minimal,
)
from uspto_enriched_citation_mcp.tools.statistics import get_citation_statistics
from uspto_enriched_citation_mcp.util.citation_links import (
    APPLICATION_CITE_AS_FIELD,
    CITATION_NOTE,
    CITE_AS_FIELD,
    PATENT_CENTER_SIGN_IN_RULE,
    STATISTICS_CITATION_NOTE,
    autolink,
    cite_as_link,
    citation_links_for_doc,
    citation_note,
    google_patents_url,
    is_narrow,
    patent_center_url,
    reference_display_number,
    reference_name,
    wants_application_link,
)

_GOOGLE = "https://patents.google.com/patent/"
_PATENT_CENTER = "https://patentcenter.uspto.gov/applications/"


class TestGooglePatentsUrl:
    def test_eleven_digits_is_a_publication_number(self):
        """US 2001/0056539 normalises to 20010056539 (the Pavlin reference
        from the walkthrough)."""
        assert google_patents_url("20010056539") == _GOOGLE + "US20010056539"

    def test_seven_and_eight_digits_are_patent_numbers(self):
        assert google_patents_url("6694384") == _GOOGLE + "US6694384"
        assert google_patents_url("11656067") == _GOOGLE + "US11656067"

    def test_series_markers_keep_their_marker(self):
        assert google_patents_url("RE38124") == _GOOGLE + "USRE38124"
        assert google_patents_url("D456789") == _GOOGLE + "USD456789"
        assert google_patents_url("PP12345") == _GOOGLE + "USPP12345"

    @pytest.mark.parametrize(
        "key",
        [
            None,  # non-patent literature: referenceKey is None to begin with
            "",
            "123456",  # 6 digits: could be an 1870s patent, could be a page
            "12345",
            "123456789",  # 9 digits: neither a patent nor a publication
            "1234567890",
            "201005653900",  # 12 digits
            "DE1234",  # under the 5-digit floor, prefix or no prefix
            "JP",
            "ABC1234567",  # three letters: not a country code
        ],
    )
    def test_a_key_that_is_neither_gets_no_url(self, key):
        """No guess. A link that looks authoritative and points at the wrong
        document is worse than no link."""
        assert google_patents_url(key) is None

    @pytest.mark.parametrize(
        "key,url",
        [
            ("DE102004012345", _GOOGLE + "DE102004012345"),
            ("JP2001123456", _GOOGLE + "JP2001123456"),
            ("EP1234567", _GOOGLE + "EP1234567"),
            ("WO2010012345", _GOOGLE + "WO2010012345"),
            ("KR20100012345", _GOOGLE + "KR20100012345"),
            ("CN101234567", _GOOGLE + "CN101234567"),
        ],
    )
    def test_a_foreign_key_is_linked_at_its_own_country_document(self, key, url):
        """The defect: these used to get no link at all, and before the key
        kept its country prefix they got a US link to a different document."""
        assert google_patents_url(key) == url

    def test_a_series_marker_is_never_read_as_a_country_code(self):
        """`RE38124` and `PP12345` lead with two letters that are not a
        country, so they stay US documents."""
        assert google_patents_url("RE38124") == _GOOGLE + "USRE38124"
        assert google_patents_url("PP12345") == _GOOGLE + "USPP12345"


class TestPatentCenterUrl:
    def test_eight_digit_serial(self):
        assert patent_center_url("11752072") == _PATENT_CENTER + "11752072"

    def test_separators_are_tolerated(self):
        assert patent_center_url("11/752,072") == _PATENT_CENTER + "11752072"

    @pytest.mark.parametrize("value", [None, "", "1175207", "117520722", "abcdefgh"])
    def test_anything_but_an_eight_digit_serial_is_none(self, value):
        assert patent_center_url(value) is None


class TestLabels:
    def test_display_numbers(self):
        assert reference_display_number("20010056539") == "US 2001/0056539"
        assert reference_display_number("6694384") == "US 6,694,384"
        assert reference_display_number("RE38124") == "US RE38124"
        assert reference_display_number("JP2001123456") == "JP 2001123456"
        assert reference_display_number("DE102004012345") == "DE 102004012345"
        assert reference_display_number("123456") is None

    def test_enriched_name_comes_from_the_inventor_field(self):
        """`SURNAME; GIVEN` is how USPTO writes these, so the label leads with
        the part before the separator."""
        doc = {"inventorNameText": "KAWAI; TAKESHI"}
        assert reference_name(doc, "20060075466") == "KAWAI"

    def test_oa_name_is_read_off_the_raw_892_string(self):
        doc = {"referenceIdentifier": "US-20060075466-A1 KAWAI; TAKESHI"}
        assert reference_name(doc, "20060075466") == "KAWAI"

    def test_a_record_with_only_a_number_has_no_name(self):
        assert reference_name({"referenceIdentifier": "20060075466"}, "20060075466") is None
        assert reference_name({}, "20060075466") is None

    def test_brackets_in_a_label_cannot_break_the_markdown_link(self):
        link = cite_as_link("Smith [Ex. 1001]", _GOOGLE + "US6694384")
        assert link == f"[Smith (Ex. 1001)]({_GOOGLE}US6694384)"

    def test_no_url_is_no_link(self):
        assert cite_as_link("Smith", None) is None


class TestLinksForOneRecord:
    def test_the_walkthrough_shape(self):
        """Label = what it is, target = the public record."""
        doc = {
            "patentApplicationNumber": "11752072",
            "publicationNumber": "20010056539",
            "citedDocumentIdentifier": "US 2001/0056539 A1",
            "inventorNameText": "PAVLIN",
        }
        cite_as, application_cite_as = citation_links_for_doc(doc, "20010056539")
        assert cite_as == f"[PAVLIN, US 2001/0056539]({_GOOGLE}US20010056539)"
        assert (
            application_cite_as
            == f"[Application 11752072]({_PATENT_CENTER}11752072)"
        )

    def test_a_record_with_no_name_is_labelled_by_number_alone(self):
        doc = {"patentApplicationNumber": "11752072"}
        cite_as, _ = citation_links_for_doc(doc, "6694384")
        assert cite_as == f"[US 6,694,384]({_GOOGLE}US6694384)"

    def test_non_patent_literature_gets_no_reference_link(self):
        """The reference key is None for NPL, so there is nothing to link. The
        application link is unaffected: the office action still has a record."""
        doc = {
            "patentApplicationNumber": "11752072",
            "citedDocumentIdentifier": "Smith et al., J. Chem. Phys. 112, 1999",
            "nplIndicator": True,
        }
        cite_as, application_cite_as = citation_links_for_doc(doc, None)
        assert cite_as is None
        assert application_cite_as is not None

    def test_a_foreign_reference_is_linked_at_its_own_country_document(self):
        """Option 2 (2026-09-12): build the correct country URL, not a US one
        and not a null."""
        doc = {"patentApplicationNumber": "11752072", "inventorNameText": "MUELLER"}
        cite_as, _ = citation_links_for_doc(doc, "DE102004012345")
        assert cite_as == f"[MUELLER, DE 102004012345]({_GOOGLE}DE102004012345)"
        compact, _ = citation_links_for_doc(doc, "JP2001123456", compact=True)
        assert compact == f"<{_GOOGLE}JP2001123456>"


def _enriched_payload():
    """Three rows in the shape app 11752072 returned during the 2026-09-05
    walkthrough: the Pavlin publication, the Moeller patent, and a piece of
    non-patent literature that must stay unlinked."""
    return {
        "response": {
            "numFound": 3,
            "start": 0,
            "docs": [
                {
                    "id": "a" * 32,
                    "patentApplicationNumber": "11752072",
                    "publicationNumber": "20010056539",
                    "citedDocumentIdentifier": "US 2001/0056539 A1",
                    "inventorNameText": "PAVLIN",
                },
                {
                    "id": "b" * 32,
                    "patentApplicationNumber": "11752072",
                    "publicationNumber": "",
                    "citedDocumentIdentifier": "US 6,694,384 B1",
                    "inventorNameText": "MOELLER",
                },
                {
                    "id": "c" * 32,
                    "patentApplicationNumber": "11752072",
                    "publicationNumber": "",
                    "citedDocumentIdentifier": (
                        "Moeller, Proc. SPIE vol. 4034, pp. 12-19, 2000"
                    ),
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
                    "examinerCitedReferenceIndicator": True,
                    "createDateTime": "2025-03-11T00:00:00Z",
                },
                {
                    "id": "f" * 32,
                    "patentApplicationNumber": "12849948",
                    "groupArtUnitNumber": "2854",
                    "techCenter": "2100",
                    "referenceIdentifier": (
                        "Anderson, 'Optical switching', IEEE J. 2003, pp. 1-9"
                    ),
                    "actionTypeCategory": "rejected",
                    "examinerCitedReferenceIndicator": True,
                    "createDateTime": "2025-03-11T00:00:00Z",
                },
            ],
        }
    }


@pytest.mark.asyncio
async def test_enriched_balanced_carries_both_labelled_links_and_the_note(mock_runtime):
    mock_runtime.api_client.search_records.return_value = _enriched_payload()

    result = await search_citations_balanced(criteria="patentApplicationNumber:11752072")

    docs = result["response"]["docs"]
    assert docs[0][CITE_AS_FIELD] == (
        f"[PAVLIN, US 2001/0056539]({_GOOGLE}US20010056539)"
    )
    assert docs[1][CITE_AS_FIELD] == f"[MOELLER, US 6,694,384]({_GOOGLE}US6694384)"
    # Non-patent literature: null, not a guess.
    assert docs[2][CITE_AS_FIELD] is None
    # Always present, null included, for the same reason referenceKey is: an
    # absent key would read as a server that does not build links at all.
    assert all(CITE_AS_FIELD in doc for doc in docs)
    assert all(
        doc[APPLICATION_CITE_AS_FIELD]
        == f"[Application 11752072]({_PATENT_CENTER}11752072)"
        for doc in docs
    )
    # Patent Center links on the rows, so the sign-in rule rides along.
    assert result["citation_note"] == citation_note(application_links=True)


@pytest.mark.asyncio
async def test_enriched_minimal_carries_one_compact_link_per_row(mock_runtime):
    """The narrow shape: `cite_as` as a markdown autolink, no label, and no
    `application_cite_as` (2026-09-11)."""
    mock_runtime.api_client.search_records.return_value = _enriched_payload()

    result = await search_citations_minimal(criteria="patentApplicationNumber:11752072")

    docs = result["response"]["docs"]
    assert docs[0][CITE_AS_FIELD] == f"<{_GOOGLE}US20010056539>"
    assert docs[1][CITE_AS_FIELD] == f"<{_GOOGLE}US6694384>"
    assert docs[2][CITE_AS_FIELD] is None
    assert all(CITE_AS_FIELD in doc for doc in docs)
    assert not any(APPLICATION_CITE_AS_FIELD in doc for doc in docs)
    assert result["citation_note"] == CITATION_NOTE


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", [search_citations_minimal, search_citations_balanced])
async def test_enriched_custom_fields_get_those_fields_and_one_link(mock_runtime, tool):
    """A custom `fields` list on either tier is a narrow request: the named
    fields, the `id` the filter re-adds, and a compact `cite_as` built from
    the UNFILTERED upstream doc, so the smallest rows are still citable.
    Nothing else unless named."""
    mock_runtime.api_client.search_records.return_value = _enriched_payload()

    result = await tool(criteria="techCenter:2100", fields=["patentApplicationNumber"])

    first = result["response"]["docs"][0]
    assert set(first) == {"patentApplicationNumber", "id", CITE_AS_FIELD}
    assert first[CITE_AS_FIELD] == f"<{_GOOGLE}US20010056539>"
    assert result["citation_note"] == CITATION_NOTE


@pytest.mark.asyncio
async def test_enriched_custom_fields_can_name_the_derived_keys(mock_runtime):
    mock_runtime.api_client.search_records.return_value = _enriched_payload()

    result = await search_citations_minimal(
        criteria="techCenter:2100",
        fields=["patentApplicationNumber", "application_cite_as", "referenceKey"],
    )

    first = result["response"]["docs"][0]
    assert first[APPLICATION_CITE_AS_FIELD] == f"<{_PATENT_CENTER}11752072>"
    assert first["referenceKey"] == "20010056539"
    # A Patent Center link was served, so the note carries the sign-in rule.
    assert result["citation_note"] == citation_note(application_links=True)


@pytest.mark.asyncio
async def test_oa_balanced_carries_both_labelled_links_and_the_note(mock_runtime):
    mock_runtime.oa_client.search_records.return_value = _oa_payload()

    result = await search_oa_citations_balanced(application_number="12849948")

    docs = result["response"]["docs"]
    assert docs[0][CITE_AS_FIELD] == f"[KAWAI, US 2006/0075466]({_GOOGLE}US20060075466)"
    assert docs[1][CITE_AS_FIELD] is None
    assert all(
        doc[APPLICATION_CITE_AS_FIELD]
        == f"[Application 12849948]({_PATENT_CENTER}12849948)"
        for doc in docs
    )
    assert result["citation_note"] == citation_note(application_links=True)


@pytest.mark.asyncio
async def test_oa_minimal_carries_one_compact_link_per_row(mock_runtime):
    mock_runtime.oa_client.search_records.return_value = _oa_payload()

    result = await search_oa_citations_minimal(application_number="12849948")

    docs = result["response"]["docs"]
    assert docs[0][CITE_AS_FIELD] == f"<{_GOOGLE}US20060075466>"
    assert docs[1][CITE_AS_FIELD] is None
    assert not any(APPLICATION_CITE_AS_FIELD in doc for doc in docs)
    # The default minimal tier keeps the cross-lane join key.
    assert all("referenceKey" in doc for doc in docs)
    assert result["citation_note"] == CITATION_NOTE


@pytest.mark.asyncio
async def test_oa_custom_fields_get_those_fields_and_one_link(mock_runtime):
    """`_pfw_link` stays on a custom list: that is the established per-row
    hand-off (eval tr-hp-07), not a citation link."""
    mock_runtime.oa_client.search_records.return_value = _oa_payload()

    result = await search_oa_citations_balanced(
        application_number="12849948", fields=["patentApplicationNumber"]
    )

    first = result["response"]["docs"][0]
    assert set(first) == {"patentApplicationNumber", CITE_AS_FIELD, "_pfw_link"}
    assert first[CITE_AS_FIELD] == f"<{_GOOGLE}US20060075466>"
    assert result["citation_note"] == CITATION_NOTE


@pytest.mark.asyncio
async def test_details_carries_the_links_and_the_note(mock_runtime):
    mock_runtime.api_client.get_citation_details.return_value = {
        "citation": {
            "patentApplicationNumber": "11752072",
            "publicationNumber": "",
            "citedDocumentIdentifier": "US 2001/0056539 A1",
            "inventorNameText": "PAVLIN; DENNIS J.",
        }
    }

    result = await get_citation_details("0de7ea10c59e03dab218a40dece9dffd")

    citation = result["citation"]
    assert citation[CITE_AS_FIELD] == f"[PAVLIN, US 2001/0056539]({_GOOGLE}US20010056539)"
    assert citation[APPLICATION_CITE_AS_FIELD] == (
        f"[Application 11752072]({_PATENT_CENTER}11752072)"
    )
    assert result["citation_note"] == citation_note(application_links=True)


@pytest.mark.asyncio
async def test_statistics_carries_the_note_and_no_row_links(mock_runtime):
    """Counts are not citations: the note says so and there is nothing to
    attach a link to."""
    mock_runtime.api_client.search_citations.return_value = {
        "response": {"numFound": 7, "docs": []}
    }

    result = await get_citation_statistics(criteria="techCenter:2100")

    assert result["citation_note"] == STATISTICS_CITATION_NOTE
    assert CITE_AS_FIELD not in result


def test_the_measured_byte_cost_of_the_two_link_fields():
    """What the tier's byte budget pays for a citable row. A ratchet, not a
    target: tighten it if the shape gets smaller, never loosen it to pass."""
    import json

    row = {
        "patentApplicationNumber": "11752072",
        "publicationNumber": "20010056539",
        "citedDocumentIdentifier": "US 2001/0056539 A1",
        "referenceKey": "20010056539",
    }
    cite_as, application_cite_as = citation_links_for_doc(
        dict(row, inventorNameText="PAVLIN"), "20010056539"
    )
    linked = dict(row, cite_as=cite_as, application_cite_as=application_cite_as)

    assert len(json.dumps(linked)) - len(json.dumps(row)) == 192
    # About 9,600 characters on a full 50-row minimal page, and that is the
    # price of the product: a page of numbers nobody can click is cheaper and
    # answers nothing. An unlinkable row pays 45 of those characters for the
    # two nulls, which is what states that no public record link exists.
    unlinkable = dict(row, cite_as=None, application_cite_as=None)
    assert len(json.dumps(unlinkable)) - len(json.dumps(row)) == 46


def test_the_measured_byte_cost_of_the_compact_link():
    """What a narrow row pays for being citable. A ratchet, like the one
    above: tighten it if the shape gets smaller, never loosen it to pass."""
    import json

    row = {"citedDocumentIdentifier": "US 2001/0056539 A1", "patentApplicationNumber": "11752072"}
    cite_as, _ = citation_links_for_doc(
        dict(row, inventorNameText="PAVLIN"), "20010056539", compact=True
    )
    assert cite_as == f"<{_GOOGLE}US20010056539>"
    # 64 characters against the 192 the two labelled links cost a full row.
    assert len(json.dumps(dict(row, cite_as=cite_as))) - len(json.dumps(row)) == 64
    # A null still states that no public record link exists.
    assert len(json.dumps(dict(row, cite_as=None))) - len(json.dumps(row)) == 17


class TestNarrowShapes:
    def test_which_requests_are_narrow(self):
        assert is_narrow("minimal", None) is True
        assert is_narrow("balanced", None) is False
        assert is_narrow("balanced", ["patentApplicationNumber"]) is True

    def test_which_requests_get_the_application_link(self):
        assert wants_application_link("balanced", None) is True
        assert wants_application_link("minimal", None) is False
        assert wants_application_link("balanced", ["patentApplicationNumber"]) is False
        assert wants_application_link("minimal", [APPLICATION_CITE_AS_FIELD]) is True

    def test_autolink(self):
        assert autolink(f"{_GOOGLE}US6694384") == f"<{_GOOGLE}US6694384>"
        assert autolink(None) is None
        assert autolink("") is None


class TestEnvelopeNote:
    """A few sentences on every envelope; the full rules live in the
    overview section of Citations_get_guidance."""

    def test_it_is_short(self):
        assert len(CITATION_NOTE) <= 400
        assert len(citation_note(application_links=True)) <= 800

    def test_it_says_what_to_do(self):
        assert "cite_as" in CITATION_NOTE
        assert "null" in CITATION_NOTE
        assert "never build a URL yourself" in CITATION_NOTE
        assert "Citations_get_guidance(section='overview')" in CITATION_NOTE
        assert "\u2014" not in CITATION_NOTE

    def test_the_sign_in_rule_rides_only_with_patent_center_links(self):
        assert PATENT_CENTER_SIGN_IN_RULE not in citation_note(application_links=False)
        assert citation_note(application_links=True).endswith(PATENT_CENTER_SIGN_IN_RULE)

    def test_the_overview_carries_the_full_rules(self):
        from uspto_enriched_citation_mcp.config.tool_reflections import (
            _get_overview_section,
        )

        flat = " ".join(_get_overview_section().split())
        assert "### CITATIONS ARE LINKS" in flat
        assert "compact" in flat and "markdown autolink" in flat
        assert (
            "Patent Center shows an application only to a signed-in reader: without "
            "a free USPTO.gov account the link lands on its own front page rather "
            "than on the desired application."
        ) in flat
