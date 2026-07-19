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
  `_get_cross_mcp_links`, `get_statistics`'s fan-out, etc.) over a mocked
  network boundary rather than mocking the service layer itself.
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
def mock_runtime(monkeypatch):
    """Patch runtime.* with mocked clients wrapped in real service objects.

    Returns a SimpleNamespace with `api_client`, `oa_client`, `field_manager`,
    `citation_service`, `oa_citation_service` so tests can configure
    `.search_records.return_value` / `.get_fields.return_value` etc. and
    assert on `.call_args`.
    """
    api_client = AsyncMock()
    oa_client = AsyncMock()
    field_manager = FieldManager(_FIELD_CONFIGS_PATH)
    citation_service = CitationService(api_client, field_manager)
    oa_citation_service = OACitationService(oa_client)

    monkeypatch.setattr(runtime, "initialize_services", lambda: None)
    monkeypatch.setattr(runtime, "api_client", api_client)
    monkeypatch.setattr(runtime, "oa_client", oa_client)
    monkeypatch.setattr(runtime, "field_manager", field_manager)
    monkeypatch.setattr(runtime, "citation_service", citation_service)
    monkeypatch.setattr(runtime, "oa_citation_service", oa_citation_service)

    return SimpleNamespace(
        api_client=api_client,
        oa_client=oa_client,
        field_manager=field_manager,
        citation_service=citation_service,
        oa_citation_service=oa_citation_service,
    )
