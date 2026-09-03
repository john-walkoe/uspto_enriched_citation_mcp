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

from .api.applications_client import ApplicationsCrosswalkClient
from .api.enriched_client import EnrichedCitationClient
from .api.oa_citations_client import OACitationsClient
from .config.field_manager import FieldManager
from .config.settings import get_settings
from .services.citation_service import CitationService
from .services.oa_citation_service import OACitationService
from .util.cache import LRUCache, TTLCache
from .util.metrics import configure_metrics
from .util.rate_limiter import RateLimitConfig, RateLimiter

# Global variables for lazy initialization
api_client = None
oa_client = None
crosswalk_client = None
field_manager = None
citation_service = None
oa_citation_service = None
# Same double-checked lazy-init idiom as util/cache.py's _cache_init_lock. The
# tool functions call initialize_services() from async context, but init is
# cheap and synchronous, so a plain threading.Lock is correct here.
_services_init_lock = threading.Lock()


def initialize_services():
    """Initialize services with settings (thread-safe lazy initialization)."""
    global api_client, oa_client, crosswalk_client
    global field_manager, citation_service, oa_citation_service

    if api_client is not None:
        return

    with _services_init_lock:
        if api_client is not None:
            return

        settings = get_settings()
        configure_metrics(settings.metrics_collector)

        def build(client_cls):
            """Construct one lane with its OWN caches and rate limiter.

            BaseCitationClient has always accepted these four collaborators
            and production passed none of them, so all three lanes shared one
            100-entry LRU and one token bucket: a burst of crosswalk lookups
            evicted citation results, and one hot lane starved the others
            (F-3 / S-3 / D-2). The per-lane sizing arguments only ever
            configured the first singleton constructed, so they read as
            per-client configuration and were not.
            """
            return client_cls(
                api_key=settings.uspto_ecitation_api_key,
                base_url=settings.uspto_base_url,
                rate_limit=settings.request_rate_limit,
                timeout=settings.api_timeout,
                connect_timeout=settings.connect_timeout,
                enable_cache=settings.enable_cache,
                rate_limiter=RateLimiter(
                    RateLimitConfig(requests_per_minute=settings.request_rate_limit)
                ),
                fields_cache=TTLCache(
                    default_ttl_seconds=settings.fields_cache_ttl, max_size=10
                ),
                search_cache=LRUCache(max_size=settings.search_cache_size),
            )

        client = build(EnrichedCitationClient)
        oa_client = build(OACitationsClient)
        # Granted patent number -> application serial. Same host, same key,
        # same metered client stack as the two citation clients above.
        crosswalk_client = build(ApplicationsCrosswalkClient)

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


async def shutdown_services() -> None:
    """Close the httpx pools opened by initialize_services().

    BaseCitationClient.close() existed with zero callers and there was no
    lifecycle counterpart to initialize_services(), so on SIGTERM the three
    connection pools were torn down by process exit rather than closed (F-2).
    """
    global api_client, oa_client, crosswalk_client
    global field_manager, citation_service, oa_citation_service

    for client in (api_client, oa_client, crosswalk_client):
        if client is not None:
            try:
                await client.close()
            except Exception:  # pragma: no cover - shutdown must not raise
                pass

    api_client = oa_client = crosswalk_client = None
    field_manager = citation_service = oa_citation_service = None
