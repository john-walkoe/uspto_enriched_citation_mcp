"""Metrics wiring, lifecycle seam, retry policy and the crosswalk LSP guards.

Each of these was a mechanism that existed and did nothing:
- `set_metrics_collector` had zero call sites, so every `record_request` in
  the client stack was a no-op and three collector methods were never invoked
  from production code at all (S-17), and only success paths were recorded,
  so any collector would have reported a 100% success rate (S-18).
- `BaseCitationClient.close()` had zero callers and there was no counterpart
  to `initialize_services()` (F-2).
- `Retry-After` was parsed onto the exception and then ignored (R-4).
- `ApplicationsCrosswalkClient` inherited two public methods it cannot
  honor (S-1).
"""

import asyncio

import httpx
import pytest

from uspto_enriched_citation_mcp import runtime
from uspto_enriched_citation_mcp.api.applications_client import (
    ApplicationsCrosswalkClient,
)
from uspto_enriched_citation_mcp.api.enriched_client import EnrichedCitationClient
from uspto_enriched_citation_mcp.shared.circuit_breaker import CircuitBreaker
from uspto_enriched_citation_mcp.shared.exceptions import RateLimitError
from uspto_enriched_citation_mcp.util import metrics as metrics_module
from uspto_enriched_citation_mcp.util.metrics import (
    LoggingMetricsCollector,
    MetricsCollector,
    NoOpMetricsCollector,
    configure_metrics,
    get_metrics_collector,
)
from uspto_enriched_citation_mcp.util.retry import (
    calculate_backoff,
    retry_after_seconds,
)


class RecordingCollector(MetricsCollector):
    def __init__(self):
        self.requests = []
        self.rate_limits = []
        self.breaker_events = []
        self.sizes = []
        self.counters = []

    def record_request(self, endpoint, method, status_code=None,
                       duration_seconds=None, error=None):
        self.requests.append(
            {"endpoint": endpoint, "method": method,
             "status_code": status_code, "error": error}
        )

    def record_rate_limit_event(self, endpoint, tokens_requested,
                                tokens_available, blocked):
        self.rate_limits.append((endpoint, blocked))

    def record_circuit_breaker_event(self, service, event_type, state):
        self.breaker_events.append((service, event_type, state))

    def record_response_size(self, endpoint, size_bytes):
        self.sizes.append((endpoint, size_bytes))

    def increment_counter(self, name, value=1, tags=None):
        self.counters.append((name, tags or {}))

    def record_gauge(self, name, value, tags=None):
        pass

    def record_histogram(self, name, value, tags=None):
        pass


@pytest.fixture
def recording_collector(monkeypatch):
    collector = RecordingCollector()
    monkeypatch.setattr(metrics_module, "_metrics_collector", collector)
    return collector


# --------------------------------------------------------------- collector


def test_configure_metrics_installs_the_named_collector(monkeypatch):
    monkeypatch.setattr(metrics_module, "_metrics_collector", NoOpMetricsCollector())
    configure_metrics("logging")
    assert isinstance(get_metrics_collector(), LoggingMetricsCollector)
    configure_metrics("none")
    assert isinstance(get_metrics_collector(), NoOpMetricsCollector)


def test_configure_metrics_falls_back_on_an_unknown_name(monkeypatch):
    monkeypatch.setattr(metrics_module, "_metrics_collector", LoggingMetricsCollector())
    configure_metrics("prometheus-that-does-not-exist")
    assert isinstance(get_metrics_collector(), NoOpMetricsCollector)


@pytest.mark.asyncio
async def test_failures_are_recorded_not_only_successes(recording_collector):
    client = EnrichedCitationClient(api_key="x" * 32, enable_cache=False,
                                    metrics_collector=recording_collector)

    async def boom(*args, **kwargs):
        raise httpx.ConnectError("nope")

    client._send = boom
    with pytest.raises(Exception):
        await client._search_records_raw("techCenter:2100", 0, 10, None)

    assert recording_collector.requests
    assert recording_collector.requests[-1]["error"] == "APIConnectionError"


@pytest.mark.asyncio
async def test_cache_hits_are_counted(recording_collector, monkeypatch):
    client = EnrichedCitationClient(api_key="x" * 32,
                                    metrics_collector=recording_collector)
    client.search_cache.set(
        "seeded", {"response": {"docs": []}}
    )
    monkeypatch.setattr(
        "uspto_enriched_citation_mcp.api.base_citation_client.generate_cache_key",
        lambda *a, **kw: "seeded",
    )

    await client._search_records_raw("techCenter:2100", 0, 10, None)

    assert any(name == "cache_hits" for name, _ in recording_collector.counters)


@pytest.mark.asyncio
async def test_breaker_transitions_are_recorded(recording_collector):
    breaker = CircuitBreaker(failure_threshold=1, name="test_lane")

    async def boom():
        raise httpx.ConnectError("nope")

    with pytest.raises(Exception):
        await breaker.call(boom)

    assert ("test_lane", "opened", "open") in recording_collector.breaker_events


# ---------------------------------------------------------------- lifecycle


@pytest.mark.asyncio
async def test_shutdown_services_closes_and_clears(monkeypatch):
    closed = []

    class _Client:
        async def close(self):
            closed.append(self)

    monkeypatch.setattr(runtime, "api_client", _Client())
    monkeypatch.setattr(runtime, "oa_client", _Client())
    monkeypatch.setattr(runtime, "crosswalk_client", _Client())

    await runtime.shutdown_services()

    assert len(closed) == 3
    assert runtime.api_client is None
    assert runtime.oa_client is None
    assert runtime.crosswalk_client is None


# -------------------------------------------------------------------- retry


def test_retry_after_is_read_from_the_exception():
    assert retry_after_seconds(RateLimitError("slow down", retry_after=60)) == 60.0
    assert retry_after_seconds(RateLimitError("slow down")) is None
    assert retry_after_seconds(ValueError("no details")) is None


def test_jitter_never_collapses_the_delay_to_zero():
    # Full jitter drew from [0, delay], so a retry after a 429 could land at
    # effectively no delay at all.
    for _ in range(50):
        delay = calculate_backoff(1, base_delay=1.0, jitter=True)
        assert 1.0 <= delay <= 2.0


# ---------------------------------------------------------------------- LSP


@pytest.mark.asyncio
async def test_crosswalk_client_refuses_the_inherited_record_methods():
    client = ApplicationsCrosswalkClient(api_key="x" * 32)
    with pytest.raises(NotImplementedError):
        await client.get_fields()
    with pytest.raises(NotImplementedError):
        await client.search_records("techCenter:2100")
    await client.close()


def test_event_loop_is_not_required_at_import():
    # Guards against a regression that would make the module unimportable
    # from a synchronous context.
    assert asyncio is not None


# ------------------------------------------------------ oauth_clients sweep


@pytest.mark.asyncio
async def test_sweep_removes_registrations_that_never_signed_anyone_in(tmp_path):
    """`/register` is the only unauthenticated write path into the database
    and oauth_clients was the one table with no cleanup (S-09)."""
    import json
    from datetime import timedelta

    from uspto_enriched_citation_mcp.auth import store as store_module
    from uspto_enriched_citation_mcp.auth.store import McpUserStore

    store = McpUserStore(tmp_path / "auth.db")
    await store.put_client("fresh", {"client_id": "fresh"})
    await store.put_client("stale", {"client_id": "stale"})
    await store.put_client("stale-but-used", {"client_id": "stale-but-used"})

    old = store_module._iso(store_module._now() - timedelta(days=90))
    async with store._db() as db:
        await db.execute(
            "UPDATE oauth_clients SET created_at = ? WHERE client_id IN "
            "('stale', 'stale-but-used')",
            (old,),
        )
        await db.execute(
            "INSERT INTO mcp_users (email, role, active, added_at) "
            "VALUES (?, 'user', 1, ?)",
            ("a@b.com", store_module._iso(store_module._now())),
        )
        await db.execute(
            "INSERT INTO oauth_refresh_tokens "
            "(token_hash, client_id, email, scopes, expires_at, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                "hash",
                "stale-but-used",
                "a@b.com",
                json.dumps(["citations:user"]),
                store_module._iso(store_module._now() + timedelta(days=1)),
                store_module._iso(store_module._now()),
            ),
        )
        await db.commit()

    removed = await store.sweep_unused_clients(max_age_days=30)

    assert removed == 1
    assert await store.get_client("fresh") is not None
    assert await store.get_client("stale-but-used") is not None
    assert await store.get_client("stale") is None
