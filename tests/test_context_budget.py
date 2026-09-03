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
async def test_oa_minimal_returns_only_its_seven_fields(mock_runtime):
    from uspto_enriched_citation_mcp.api.oa_citations_client import (
        OA_CITATIONS_MINIMAL_FIELDS,
    )

    mock_runtime.oa_client.search_records.return_value = _fixture(
        OA_CITATIONS_ALL_FIELDS
    )
    result = await search_oa_citations_minimal(criteria="techCenter:2100")

    allowed = set(OA_CITATIONS_MINIMAL_FIELDS) | {"id"}
    for doc in result["response"]["docs"]:
        assert set(doc) <= allowed
    # The PFW hand-off is on the envelope, not repeated on every row.
    assert result["pfw_link"]
    assert "_pfw_link" not in result["response"]["docs"][0]


@pytest.mark.asyncio
async def test_enriched_minimal_returns_only_its_eight_fields(mock_runtime):
    mock_runtime.api_client.search_records.return_value = _fixture(
        DEFAULT_BALANCED_FIELDS
    )
    result = await search_citations_minimal(criteria="techCenter:2100")

    allowed = set(DEFAULT_MINIMAL_FIELDS) | {"id", "_version_", "score"}
    for doc in result["response"]["docs"]:
        assert set(doc) <= allowed


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
