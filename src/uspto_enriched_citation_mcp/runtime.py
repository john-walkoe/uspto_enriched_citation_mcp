"""Shared runtime service singletons (SD-1/SOLID-5 — lazy-init seam).

The five service globals (api_client, oa_client, field_manager,
citation_service, oa_citation_service) and initialize_services() live here so
tool modules depend on ONE stable module instead of the composition root.

Tool modules import this module itself (`from .. import runtime`) and access
services as `runtime.api_client`, `runtime.citation_service`, etc. — always a
fresh module-attribute lookup, never a name bound at import time — so a
reassignment inside initialize_services() is visible to every caller. Tests
patch these same attributes directly (`monkeypatch.setattr(runtime,
"citation_service", ...)`); patching a name re-exported from main.py would
only rebind main's copy and never reach the tool functions, which look the
service up on this module.
"""

import threading
from pathlib import Path

from .api.enriched_client import EnrichedCitationClient
from .api.oa_citations_client import OACitationsClient
from .config.field_manager import FieldManager
from .config.settings import get_settings
from .services.citation_service import CitationService
from .services.oa_citation_service import OACitationService

# Global variables for lazy initialization
api_client = None
oa_client = None
field_manager = None
citation_service = None
oa_citation_service = None
# Same double-checked lazy-init idiom as util/cache.py's _cache_init_lock. The
# tool functions call initialize_services() from async context, but init is
# cheap and synchronous, so a plain threading.Lock is correct here.
_services_init_lock = threading.Lock()


def initialize_services():
    """Initialize services with settings (thread-safe lazy initialization)."""
    global api_client, oa_client, field_manager, citation_service, oa_citation_service

    if api_client is not None:
        return

    with _services_init_lock:
        if api_client is not None:
            return

        settings = get_settings()

        client = EnrichedCitationClient(
            api_key=settings.uspto_ecitation_api_key,
            base_url=settings.uspto_base_url,
            rate_limit=settings.request_rate_limit,
            timeout=settings.api_timeout,
            enable_cache=settings.enable_cache,
            fields_cache_ttl=settings.fields_cache_ttl,
            search_cache_size=settings.search_cache_size,
        )

        oa_client = OACitationsClient(
            api_key=settings.uspto_ecitation_api_key,
            base_url=settings.uspto_base_url,
            rate_limit=settings.request_rate_limit,
            timeout=settings.api_timeout,
            enable_cache=settings.enable_cache,
            fields_cache_ttl=settings.fields_cache_ttl,
            search_cache_size=settings.search_cache_size,
        )

        # Load field manager from project root (consistent with other MCPs)
        config_path = Path(__file__).parent.parent.parent / "field_configs.yaml"
        field_manager = FieldManager(config_path)

        # Initialize service layers
        citation_service = CitationService(client, field_manager)
        oa_citation_service = OACitationService(oa_client)

        # Set the fast-path guard variable LAST so a concurrent caller that
        # passes the unlocked `api_client is not None` check never observes
        # partially initialized services.
        api_client = client
