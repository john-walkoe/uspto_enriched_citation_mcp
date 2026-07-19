"""Regression tests: the 4 search tools must reject invalid Lucene criteria
BEFORE making any network/service call.

search_citations_minimal/balanced previously never validated `criteria` at
all; search_oa_citations_minimal/balanced called validate_lucene_syntax()
inside a `try/except ValueError`, but the validator never raises — it
returns a (bool, str) tuple — so the except branch was always dead code and
invalid criteria passed straight through to the API client.

These tests monkeypatch the module-level service singletons with a guard
that raises on any attribute access, so a real network call would fail the
test loudly instead of silently succeeding against api.uspto.gov.
"""

import pytest

from uspto_enriched_citation_mcp import main, runtime

# Unbalanced parenthesis: fails validate_lucene_syntax() reliably and early
# (balance check runs before the field whitelist check).
_INVALID_CRITERIA = "techCenter:(unbalanced"


class _NetworkGuard:
    """Raises on any use — proves the tool returned before touching a
    service/client (initialize_services() short-circuits because these
    module globals are no longer None)."""

    def __getattr__(self, name):
        raise AssertionError(f"unexpected service/network access: {name!r}")


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    # Phase 6B seam switch: the search tools now live in tools/search.py and
    # tools/oa.py, which access services via `runtime.<attr>` module-attribute
    # lookups (not a name bound at import time), so the singletons must be
    # patched on the `runtime` module — patching `main.api_client` etc. would
    # only rebind main.py's back-compat re-export and never reach the tools.
    guard = _NetworkGuard()
    monkeypatch.setattr(runtime, "api_client", guard)
    monkeypatch.setattr(runtime, "oa_client", guard)
    monkeypatch.setattr(runtime, "citation_service", guard)
    monkeypatch.setattr(runtime, "oa_citation_service", guard)
    monkeypatch.setattr(runtime, "field_manager", guard)


@pytest.mark.asyncio
async def test_search_citations_minimal_rejects_invalid_criteria():
    result = await main.search_citations_minimal(criteria=_INVALID_CRITERIA)
    assert result["status"] == "error"
    assert result["code"] == 400


@pytest.mark.asyncio
async def test_search_citations_balanced_rejects_invalid_criteria():
    result = await main.search_citations_balanced(criteria=_INVALID_CRITERIA)
    assert result["status"] == "error"
    assert result["code"] == 400


@pytest.mark.asyncio
async def test_search_oa_citations_minimal_rejects_invalid_criteria():
    result = await main.search_oa_citations_minimal(criteria=_INVALID_CRITERIA)
    assert result["status"] == "error"
    assert result["code"] == 400


@pytest.mark.asyncio
async def test_search_oa_citations_balanced_rejects_invalid_criteria():
    result = await main.search_oa_citations_balanced(criteria=_INVALID_CRITERIA)
    assert result["status"] == "error"
    assert result["code"] == 400


# ---------------------------------------------------------------------------
# OA v2 field-set regression (found live 2026-07-09, TEST_SUITE.md OA-4/OA-7):
# the OA tools' validator call was dead code until fix H3 made it real, and
# the default whitelist (enriched v3 fields) then rejected legitimate OA-only
# fields like legalSectionCode/actionTypeCategory. The OA tools must validate
# against OA_VALID_FIELDS — these criteria must get PAST validation (the
# network guard raising AssertionError proves validation accepted them and
# the tool proceeded to the client).


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "criteria",
    [
        "legalSectionCode:103 AND techCenter:2600",
        "actionTypeCategory:rejected AND legalSectionCode:103",
        "referenceIdentifier:US* AND workGroup:2620",
        "paragraphNumber:3 AND parsedReferenceIdentifier:20070223739",
        # ISO-8601 timestamps in ranges (TEST_SUITE.md OA-9 live regression)
        "techCenter:2600 AND createDateTime:[2025-01-01T00:00:00Z TO 2025-12-31T23:59:59Z]",
    ],
)
async def test_oa_tools_accept_oa_only_fields(criteria):
    for tool in (main.search_oa_citations_minimal, main.search_oa_citations_balanced):
        result = await tool(criteria=criteria)
        # Validation accepted the criteria and the tool proceeded to the
        # service layer, where the network guard blew up -> the tool's
        # blanket except turns that into its 500 envelope. A 400 here would
        # mean the whitelist wrongly rejected an OA field again.
        assert result["status"] == "error"
        assert result["code"] == 500, result
        assert "Invalid" not in result["error"]


@pytest.mark.asyncio
async def test_enriched_tools_still_reject_oa_only_fields():
    # The enriched v3 schema has no legalSectionCode — the default whitelist
    # must keep rejecting it (the field-set split must not loosen enriched).
    result = await main.search_citations_minimal(criteria="legalSectionCode:103")
    assert result["status"] == "error"
    assert result["code"] == 400
    assert "legalSectionCode" in result["error"]
