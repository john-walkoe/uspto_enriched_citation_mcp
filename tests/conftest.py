"""Shared pytest fixtures for tool-level tests.

`mock_runtime` patches the five service singletons on the `runtime` module
(the seam established by tests/test_query_validation_wiring.py and
tests/test_medium_security_fixes.py — tool modules look services up as
`runtime.<attr>` on every call, so patching `runtime` directly reaches them,
while patching `main.<attr>` would only rebind main.py's back-compat
re-export). It wires:

- `api_client` / `oa_client`: AsyncMock stand-ins for the HTTP-boundary
  clients (EnrichedCitationClient / OACitationsClient) — the network seam,
  same one tests/test_basic.py and tests/test_oa_citations_client.py mock.
- `field_manager`: a REAL FieldManager loaded from the project's actual
  field_configs.yaml, so field-filtering behaves exactly as in production
  instead of needing to be hand-mocked.
- `citation_service` / `oa_citation_service`: REAL CitationService /
  OACitationService instances wrapping the mocked clients above, so the
  tool tests exercise real service-layer logic (including
  `get_cross_mcp_links`, `get_statistics`'s fan-out, etc.) over a mocked
  network boundary rather than mocking the service layer itself.

`no_backoff` collapses `retry_async`'s real sleeps for the error-path tests
that otherwise spend seconds of suite wall time in genuine backoff.
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from uspto_enriched_citation_mcp import runtime
from uspto_enriched_citation_mcp.config.field_manager import FieldManager
from uspto_enriched_citation_mcp.services.citation_service import CitationService
from uspto_enriched_citation_mcp.services.oa_citation_service import OACitationService

_FIELD_CONFIGS_PATH = (
    Path(runtime.__file__).resolve().parent.parent.parent / "field_configs.yaml"
)


@pytest.fixture
def no_backoff(monkeypatch):
    """Collapse retry_async's sleeps.

    The delays themselves stay covered by test_resilience.py's
    calculate_backoff unit tests and by the one error-path test that
    deliberately measures elapsed time; everything else was paying roughly
    5 of the suite's 15 seconds to sleep through real backoff (T-5).
    """
    import asyncio

    real_sleep = asyncio.sleep

    async def instant(_seconds, *args, **kwargs):
        return await real_sleep(0)

    monkeypatch.setattr(
        "uspto_enriched_citation_mcp.util.retry.asyncio.sleep", instant
    )


@pytest.fixture
def mock_runtime(monkeypatch):
    """Patch runtime.* with mocked clients wrapped in real service objects.

    Returns a SimpleNamespace with `api_client`, `oa_client`,
    `crosswalk_client`, `field_manager`, `citation_service`,
    `oa_citation_service` so tests can configure
    `.search_records.return_value` / `.get_fields.return_value` etc. and
    assert on `.call_args`.
    """
    api_client = AsyncMock()
    oa_client = AsyncMock()
    # Patent-number crosswalk (ApplicationsCrosswalkClient stand-in). Defaults
    # to a MISS so a test that passes `patent_number` without configuring it
    # gets the deterministic "no application found" 400 rather than a truthy
    # AsyncMock return standing in for an application serial.
    crosswalk_client = AsyncMock()
    crosswalk_client.find_application_number.return_value = None
    field_manager = FieldManager(_FIELD_CONFIGS_PATH)
    citation_service = CitationService(api_client, field_manager)
    oa_citation_service = OACitationService(oa_client)

    monkeypatch.setattr(runtime, "initialize_services", lambda: None)
    monkeypatch.setattr(runtime, "api_client", api_client)
    monkeypatch.setattr(runtime, "oa_client", oa_client)
    monkeypatch.setattr(runtime, "crosswalk_client", crosswalk_client)
    monkeypatch.setattr(runtime, "field_manager", field_manager)
    monkeypatch.setattr(runtime, "citation_service", citation_service)
    monkeypatch.setattr(runtime, "oa_citation_service", oa_citation_service)

    return SimpleNamespace(
        api_client=api_client,
        oa_client=oa_client,
        crosswalk_client=crosswalk_client,
        field_manager=field_manager,
        citation_service=citation_service,
        oa_citation_service=oa_citation_service,
    )
