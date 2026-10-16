"""Context-budget ratchet for the four search tiers.

This server's product IS token budget, and the one budget regression it has
already shipped was invisible to every functional test: the OA minimal tier
served all 16 fields plus a per-row PFW hand-off, so the "high-volume
discovery" tier cost MORE context than the detail tier (13,020 vs 12,754
chars on app 16816197, fixed 2026-08-30 to 5,970 vs 11,374). Nothing asserted
the ordering the tier names claim (T-6).

The absolute ceilings are ratchets, not targets: tighten them when a tier
genuinely gets smaller, never loosen them to make a change pass.
"""

import json

import pytest

from uspto_enriched_citation_mcp.api.oa_citations_client import (
    OA_CITATIONS_ALL_FIELDS,
)
from uspto_enriched_citation_mcp.config.field_manager import (
    DEFAULT_BALANCED_FIELDS,
    DEFAULT_MINIMAL_FIELDS,
)
from uspto_enriched_citation_mcp.util.citation_links import (
    APPLICATION_CITE_AS_FIELD,
    CITE_AS_FIELD,
)
from uspto_enriched_citation_mcp.tools.oa import (
    search_oa_citations_balanced,
    search_oa_citations_minimal,
)
from uspto_enriched_citation_mcp.tools.search import (
    search_citations_balanced,
    search_citations_minimal,
)

_ROWS = 20


def _fixture(fields, rows=_ROWS):
    """A full-fat upstream payload: every field populated on every row, which
    is what both USPTO citation APIs actually return whatever `fl` asks for."""
    docs = []
    for i in range(rows):
        doc = {"id": f"{i:032x}", "patentApplicationNumber": f"168161{i:02d}"}
        for field in fields:
            doc.setdefault(field, f"{field}-value-{i}" * 3)
        docs.append(doc)
    return {"response": {"numFound": rows, "start": 0, "docs": docs}}


def _size(payload):
    return len(json.dumps(payload))


@pytest.mark.asyncio
async def test_oa_minimal_is_smaller_than_oa_balanced(mock_runtime):
    mock_runtime.oa_client.search_records.return_value = _fixture(
        OA_CITATIONS_ALL_FIELDS
    )
    minimal = await search_oa_citations_minimal(criteria="techCenter:2100")

    mock_runtime.oa_client.search_records.return_value = _fixture(
        OA_CITATIONS_ALL_FIELDS
    )
    balanced = await search_oa_citations_balanced(criteria="techCenter:2100")

    assert _size(minimal) < _size(balanced)


@pytest.mark.asyncio
async def test_enriched_minimal_is_smaller_than_enriched_balanced(mock_runtime):
    mock_runtime.api_client.search_records.return_value = _fixture(
        DEFAULT_BALANCED_FIELDS
    )
    minimal = await search_citations_minimal(criteria="techCenter:2100")

    mock_runtime.api_client.search_records.return_value = _fixture(
        DEFAULT_BALANCED_FIELDS
    )
    balanced = await search_citations_balanced(criteria="techCenter:2100")

    assert _size(minimal) < _size(balanced)


@pytest.mark.asyncio
async def test_oa_minimal_returns_only_its_eight_fields(mock_runtime):
    """Eight since 2026-09-04: `parsedReferenceIdentifier` joined the tier so
    the discovery lane carries a normalised reference, plus the cross-lane
    `referenceKey` the server derives for every row."""
    from uspto_enriched_citation_mcp.api.oa_citations_client import (
        OA_CITATIONS_MINIMAL_FIELDS,
    )
    from uspto_enriched_citation_mcp.util.reference_key import REFERENCE_KEY_FIELD

    mock_runtime.oa_client.search_records.return_value = _fixture(
        OA_CITATIONS_ALL_FIELDS
    )
    result = await search_oa_citations_minimal(criteria="techCenter:2100")

    # One link per minimal row since 2026-09-11: `cite_as`, no
    # `application_cite_as`.
    allowed = set(OA_CITATIONS_MINIMAL_FIELDS) | {
        "id",
        REFERENCE_KEY_FIELD,
        CITE_AS_FIELD,
    }
    for doc in result["response"]["docs"]:
        assert set(doc) <= allowed
        assert REFERENCE_KEY_FIELD in doc
    # The PFW hand-off is on the envelope, not repeated on every row.
    assert result["pfw_link"]
    assert "_pfw_link" not in result["response"]["docs"][0]


@pytest.mark.asyncio
async def test_enriched_minimal_returns_only_its_eight_fields(mock_runtime):
    from uspto_enriched_citation_mcp.util.reference_key import REFERENCE_KEY_FIELD

    mock_runtime.api_client.search_records.return_value = _fixture(
        DEFAULT_BALANCED_FIELDS
    )
    result = await search_citations_minimal(criteria="techCenter:2100")

    # Two derived keys ride on top of the tier's eight fields: the cross-lane
    # join key and one compact citation link (no `application_cite_as` on the
    # minimal tier since 2026-09-11).
    allowed = set(DEFAULT_MINIMAL_FIELDS) | {
        "id",
        "_version_",
        "score",
        REFERENCE_KEY_FIELD,
        CITE_AS_FIELD,
    }
    for doc in result["response"]["docs"]:
        assert set(doc) <= allowed
        assert REFERENCE_KEY_FIELD in doc


@pytest.mark.asyncio
async def test_a_custom_field_list_beats_the_minimal_tier(mock_runtime):
    """The ultra-minimal path is the smallest thing this server can return."""
    mock_runtime.api_client.search_records.return_value = _fixture(
        DEFAULT_BALANCED_FIELDS
    )
    minimal = await search_citations_minimal(criteria="techCenter:2100")

    mock_runtime.api_client.search_records.return_value = _fixture(
        DEFAULT_BALANCED_FIELDS
    )
    ultra = await search_citations_minimal(
        criteria="techCenter:2100",
        fields=["citedDocumentIdentifier", "patentApplicationNumber"],
    )

    assert _size(ultra) < _size(minimal)
    assert ultra["query_info"]["tier"] == "ultra-minimal"


# ---------------------------------------------------------------------------
# Recorded pages: the two call shapes the eval gate measures (2026-09-11)
# ---------------------------------------------------------------------------
# Upstream rows recorded live on app 16816197 (18 OA rows, 33 enriched rows),
# with the server-derived keys stripped so the replay rebuilds them. Replayed
# through the pre-fix code the OA page measures 11,658 characters, the same
# figure the live eval recorded, so the fixture is faithful.

_FIXTURES = __import__("pathlib").Path(__file__).resolve().parent / "fixtures"


def _recorded(name):
    return json.loads((_FIXTURES / name).read_text())


@pytest.mark.asyncio
async def test_recorded_ultra_minimal_page_is_back_under_eight_thousand(mock_runtime):
    """Eval tr-cost-03: a two-field custom list on 33 rows. 5,914 characters
    before the link rollout, 13,834 after it (six fields per row), 7,838 with
    the narrow shape. The 8,000 bound was the eval's own; 8,093 since
    2026-09-12, because 6 of these 33 recorded rows are WO references
    ("WO-2010098305-A1") whose bare-digit key linked to nothing, and each now
    carries a verified Google Patents link to the WO document (+255 characters
    net, against a 22-character shorter envelope note). Re-baselining the eval
    bound is a judgment call; the assertion here records what the page measures.
    Ratchet: tighten, never loosen."""
    from uspto_enriched_citation_mcp.util.reference_key import REFERENCE_KEY_FIELD

    mock_runtime.api_client.search_records.return_value = _recorded(
        "enriched_minimal_16816197.json"
    )

    result = await search_citations_minimal(
        application_number="16816197",
        rows=50,
        fields=["citedDocumentIdentifier", "patentApplicationNumber"],
    )

    docs = result["response"]["docs"]
    assert len(docs) == 33
    for doc in docs:
        assert set(doc) <= {
            "citedDocumentIdentifier",
            "patentApplicationNumber",
            "id",
            CITE_AS_FIELD,
        }
        assert CITE_AS_FIELD in doc
        assert REFERENCE_KEY_FIELD not in doc
        assert APPLICATION_CITE_AS_FIELD not in doc
    assert _size(result) <= 8_100


@pytest.mark.asyncio
async def test_recorded_oa_minimal_page_ratchet(mock_runtime):
    """Eval tr-amb-07 bounds this call at 6,000 characters. That bound was set
    on the 7-field tier with no link and no join key (5,970), and the 2026-09-04
    `parsedReferenceIdentifier` addition alone takes the same 18 rows to 6,742,
    so it cannot hold a per-row link. 11,658 with two labelled links per row;
    8,488 with the narrow shape; 8,707 since 2026-09-12, when 5 of these 18
    recorded rows stopped keying their WO reference as bare digits ("GOTO K
    WO-2010098305-A1") and started carrying a link to the WO document (+219
    characters net). Ratchet: tighten, never loosen."""
    mock_runtime.oa_client.search_records.return_value = _recorded(
        "oa_minimal_16816197.json"
    )

    result = await search_oa_citations_minimal(application_number="16816197", rows=50)

    docs = result["response"]["docs"]
    assert len(docs) == 18
    assert not any(APPLICATION_CITE_AS_FIELD in doc for doc in docs)
    assert all(CITE_AS_FIELD in doc for doc in docs)
    assert _size(result) <= 8_707
