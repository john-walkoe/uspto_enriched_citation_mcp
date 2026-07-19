"""
Regression tests for the Phase 4 resilience & error-handling remediation.

Covers (see audits/exception-flow-analysis.md E1-E7,
audits/error-handling-resilience.md 1.1/3.1, audits/code-duplication-detection.md #1):

- E4/E5: the circuit breaker only counts infrastructure failures (timeouts,
  connection errors, 5xx) — 4xx client errors and 429 backpressure propagate
  without opening the circuit for unrelated callers.
- E6: each USPTO API (Enriched Citations v3 / OA Citations v2) gets its own
  circuit breaker instance, so an outage in one can't block the other.
- E7: an open circuit fails fast on the very first attempt instead of
  burning the full retry budget against an already-open circuit.
- Dup#1/E2: the stale-cache fallback on transient per-request errors
  (previously only implemented in EnrichedCitationClient's shadow methods)
  now lives in BaseCitationClient, so OACitationsClient gets it too.
- 1.1: EnrichedCitationClient.get_citation_details routes unexpected errors
  through the same sanitized-message machinery as every other path.
- 3.1: CitationService.get_statistics surfaces queries_failed instead of
  silently reporting a full "success" when sub-queries failed.
- E1: an auth-store (SQLite) failure mid-OAuth-flow yields a clean error
  response instead of an unhandled traceback.
"""

import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from uspto_enriched_citation_mcp.api.enriched_client import EnrichedCitationClient
from uspto_enriched_citation_mcp.api.oa_citations_client import OACitationsClient
from uspto_enriched_citation_mcp.shared.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitState,
    get_circuit_breaker,
    is_counted_failure,
    reset_circuit_breakers,
)
from uspto_enriched_citation_mcp.shared.exceptions import (
    APIConnectionError,
    APIResponseError,
    APITimeoutError,
    APIUnavailableError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from uspto_enriched_citation_mcp.util.cache import LRUCache, TTLCache, generate_cache_key


def make_mock_response(status_code=200, json_data=None, headers=None, content=b"{}"):
    """Factory for httpx Response mocks (matches tests/test_oa_citations_client.py)."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data if json_data is not None else {}
    response.headers = headers or {}
    response.content = content
    return response


# --------------------------------------------------------------------- E4/E5


class TestIsCountedFailure:
    """4xx and 429 must not count; infra failures (5xx/timeout/connect) must."""

    def test_4xx_client_errors_not_counted(self):
        assert is_counted_failure(ValidationError("bad query")) is False
        assert is_counted_failure(AuthenticationError()) is False
        assert is_counted_failure(AuthorizationError()) is False
        assert is_counted_failure(NotFoundError()) is False

    def test_429_rate_limit_not_counted(self):
        # 429 is expected backpressure — heavy legitimate use must not open
        # the circuit (preserves the pre-rework RateLimitError carve-out).
        assert is_counted_failure(RateLimitError()) is False

    def test_5xx_domain_errors_counted(self):
        assert is_counted_failure(APIConnectionError()) is True
        assert is_counted_failure(APITimeoutError()) is True
        assert is_counted_failure(APIUnavailableError()) is True
        assert is_counted_failure(APIResponseError()) is True

    def test_raw_timeout_and_connection_errors_counted(self):
        assert is_counted_failure(httpx.TimeoutException("t")) is True
        assert is_counted_failure(httpx.ConnectError("c")) is True
        assert is_counted_failure(ConnectionError("x")) is True
        assert is_counted_failure(TimeoutError("x")) is True


class TestCircuitBreakerClassification:
    """CircuitBreaker.call must apply the same 4xx-vs-infra classification."""

    @pytest.mark.asyncio
    async def test_repeated_4xx_does_not_open_circuit(self):
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=60.0)

        async def bad_query():
            raise ValidationError("bad query")

        # Well past the failure threshold — a bad-input caller must not be
        # able to open the circuit for everyone else.
        for _ in range(5):
            with pytest.raises(ValidationError):
                await breaker.call(bad_query)

        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_repeated_5xx_opens_circuit(self):
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=60.0)

        async def upstream_down():
            raise APIConnectionError("down")

        for _ in range(2):
            with pytest.raises(APIConnectionError):
                await breaker.call(upstream_down)

        assert breaker.state == CircuitState.OPEN
        assert breaker.failure_count == 2

    @pytest.mark.asyncio
    async def test_repeated_429_does_not_open_circuit(self):
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=60.0)

        async def rate_limited():
            raise RateLimitError()

        for _ in range(5):
            with pytest.raises(RateLimitError):
                await breaker.call(rate_limited)

        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0


# ------------------------------------------------------------------------ E6


class TestPerApiBreakerIsolation:
    """Each API gets its own breaker; a failure streak in one must not
    affect the other (no shared-fate bulkhead violation)."""

    def test_registry_returns_distinct_memoized_instances(self):
        reset_circuit_breakers()
        try:
            enriched = get_circuit_breaker("enriched")
            oa = get_circuit_breaker("oa")
            assert enriched is not oa
            assert get_circuit_breaker("enriched") is enriched
            assert get_circuit_breaker("oa") is oa
        finally:
            reset_circuit_breakers()

    def test_clients_resolve_to_separate_named_breakers(self):
        reset_circuit_breakers()
        try:
            enriched_client = EnrichedCitationClient(api_key="x" * 32, enable_cache=False)
            oa_client = OACitationsClient(api_key="x" * 32, enable_cache=False)

            assert enriched_client._circuit_breaker is not oa_client._circuit_breaker
            assert enriched_client._circuit_breaker is get_circuit_breaker("enriched")
            assert oa_client._circuit_breaker is get_circuit_breaker("oa")
        finally:
            reset_circuit_breakers()

    @pytest.mark.asyncio
    async def test_opening_one_breaker_does_not_open_the_other(self):
        reset_circuit_breakers()
        try:
            enriched_breaker = get_circuit_breaker(
                "enriched", failure_threshold=1, recovery_timeout=9999.0
            )
            oa_breaker = get_circuit_breaker("oa", failure_threshold=1, recovery_timeout=9999.0)

            async def boom():
                raise APIConnectionError("enriched API is down")

            with pytest.raises(APIConnectionError):
                await enriched_breaker.call(boom)

            assert enriched_breaker.state == CircuitState.OPEN
            # OA's breaker is a distinct instance — must be completely unaffected.
            assert oa_breaker.state == CircuitState.CLOSED

            async def ok():
                return "fine"

            assert await oa_breaker.call(ok) == "fine"
        finally:
            reset_circuit_breakers()


# ------------------------------------------------------------------------ E7


class TestOpenBreakerFailsFast:
    @pytest.mark.asyncio
    async def test_open_circuit_fails_fast_without_exhausting_retries(self):
        # Force OPEN directly — no need to organically trigger a failure.
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=9999.0)
        breaker._state = CircuitState.OPEN
        breaker._last_failure_time = time.time()

        breaker_calls = 0
        original_call = breaker.call

        async def counting_call(func, *args, **kwargs):
            nonlocal breaker_calls
            breaker_calls += 1
            return await original_call(func, *args, **kwargs)

        breaker.call = counting_call

        client = EnrichedCitationClient(
            api_key="x" * 32, enable_cache=False, circuit_breaker=breaker
        )

        http_calls = 0

        async def counting_get(*args, **kwargs):
            nonlocal http_calls
            http_calls += 1
            raise AssertionError("HTTP layer must not be reached when circuit is open")

        with patch.object(client.client, "get", side_effect=counting_get):
            with pytest.raises(CircuitBreakerError):
                await client.get_fields()

        # retry_async must not retry a CircuitBreakerError — only the single,
        # immediate breaker check happens, and the raw HTTP call is never
        # attempted (fail fast, no wasted attempts against an open circuit).
        assert breaker_calls == 1
        assert http_calls == 0


# --------------------------------------------------------------- Dup#1 / E2


class TestStaleCacheFallbackBothClients:
    """Both clients must inherit identical stale-cache fallback behaviour
    from BaseCitationClient for transient (non-breaker-open) errors — this
    was previously only implemented in EnrichedCitationClient's now-deleted
    shadow methods, silently missing for OACitationsClient."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("client_cls", [EnrichedCitationClient, OACitationsClient])
    async def test_transient_connect_error_falls_back_to_stale_fields_cache(
        self, client_cls
    ):
        # Same technique as the existing
        # test_oa_client_circuit_breaker_open_fields_stale_cache: patch the
        # retry+breaker-wrapped _get_fields_impl directly so the fallback
        # logic in get_fields() is exercised in isolation, independent of
        # cache population/expiry timing.
        fields_cache = TTLCache(default_ttl_seconds=3600, max_size=10)
        client = client_cls(
            api_key="x" * 32,
            base_url="https://api.uspto.gov",
            enable_cache=True,
            fields_cache=fields_cache,
            search_cache=LRUCache(max_size=10),
        )
        cache_key = generate_cache_key(f"{client._CACHE_KEY_PREFIX}_fields", client.base_url)
        stale_data = {"fields": [{"name": "stale_field"}]}
        fields_cache.set(cache_key, stale_data)

        with patch.object(
            client, "_get_fields_impl",
            side_effect=APIConnectionError("Failed to connect to USPTO API"),
        ):
            result = await client.get_fields()

        assert result["fields"] == stale_data["fields"]
        assert result["_cache_status"]["source"] == "stale_cache"
        assert result["_cache_status"]["error_type"] == "APIConnectionError"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("client_cls", [EnrichedCitationClient, OACitationsClient])
    async def test_transient_timeout_falls_back_to_cached_search_results(
        self, client_cls
    ):
        """Same isolation technique as the fields test above: patch
        _search_records_impl directly so search_records()'s merged
        `except (APITimeoutError, APIConnectionError)` fallback is exercised
        deterministically, independent of the exact-cache-key short-circuit
        that would otherwise make a pre-populated entry return before any
        network attempt could occur."""
        search_cache = LRUCache(max_size=10)
        client = client_cls(
            api_key="x" * 32,
            base_url="https://api.uspto.gov",
            enable_cache=True,
            fields_cache=TTLCache(default_ttl_seconds=3600, max_size=10),
            search_cache=search_cache,
        )
        cache_key = generate_cache_key(
            f"{client._CACHE_KEY_PREFIX}_search", "techCenter:2100", 0, 50,
            selected_fields=None,
        )
        cached_result = {"response": {"numFound": 1, "docs": [{"id": "cached-doc"}]}}
        search_cache.set(cache_key, dict(cached_result))

        with patch.object(
            client, "_search_records_impl",
            side_effect=APITimeoutError("Search request timed out"),
        ):
            result = await client.search_records(criteria="techCenter:2100", rows=50)

        assert result["response"]["docs"] == [{"id": "cached-doc"}]
        assert result["_cache_status"]["source"] == "cache"
        assert result["_cache_status"]["error_type"] == "APITimeoutError"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("client_cls", [EnrichedCitationClient, OACitationsClient])
    async def test_transient_timeout_without_cached_entry_propagates_cleanly(
        self, client_cls
    ):
        """No cached entry to fall back to — both clients propagate the
        same clean domain exception through the identical inherited code
        path (no divergence between clients, the Dup#1 regression this
        guards against)."""
        client = client_cls(
            api_key="x" * 32,
            base_url="https://api.uspto.gov",
            enable_cache=True,
            fields_cache=TTLCache(default_ttl_seconds=3600, max_size=10),
            search_cache=LRUCache(max_size=10),
        )

        with patch.object(
            client, "_search_records_impl",
            side_effect=APITimeoutError("Search request timed out"),
        ):
            with pytest.raises(APITimeoutError):
                await client.search_records(criteria="techCenter:2100", rows=50)


# ------------------------------------------------------------------------ 1.1


class TestGetCitationDetailsSanitization:
    @pytest.mark.asyncio
    async def test_unexpected_error_is_routed_through_sanitized_envelope(self):
        client = EnrichedCitationClient(api_key="x" * 32, enable_cache=False)

        async def boom(*args, **kwargs):
            raise RuntimeError("Traceback at /home/john/secret/config.py line 42")

        with patch.object(client, "search_records", side_effect=boom):
            result = await client.get_citation_details("12345")

        assert result["status"] == "error"
        assert result["citation_id"] == "12345"
        # get_safe_error_message maps RuntimeError to a fixed friendly
        # message — the raw exception text (and any embedded path) must not
        # reach the caller.
        assert "secret" not in result["error"]
        assert "/home/john" not in result["error"]
        assert result["error"] == "Operation failed. Please try again."


# ------------------------------------------------------------------------ 3.1


class TestGetStatisticsQueriesFailed:
    @pytest.mark.asyncio
    async def test_partial_failure_surfaces_queries_failed(self, monkeypatch):
        from uspto_enriched_citation_mcp.services.citation_service import CitationService
        from uspto_enriched_citation_mcp.util import rate_limiter as rl

        rl.reset_rate_limiter()
        limiter = rl.get_rate_limiter(rl.RateLimitConfig(requests_per_minute=60))

        async def allow(endpoint="default", tokens=1):
            return True

        monkeypatch.setattr(limiter, "acquire", allow)

        class _FlakyClient:
            async def search_citations(self, criteria, rows=0, **kwargs):
                if "citationCategoryCode:X" in criteria or (
                    "examinerCitedReferenceIndicator:true" in criteria
                ):
                    raise APIConnectionError("upstream hiccup")
                return {"response": {"numFound": 3}}

        service = CitationService(_FlakyClient(), field_manager=None)
        result = await service.get_statistics(criteria="techCenter:2100")

        assert result["status"] == "success"
        assert result["queries_failed"] == 2
        assert result["total_citations"] == 3
        # Failed sub-queries degrade to zero rather than crashing the call.
        assert result["breakdowns"]["Citation Category"]["X — Novel (§102)"] == 0
        assert result["examiner_cited_count"] == 0

        rl.reset_rate_limiter()

    @pytest.mark.asyncio
    async def test_no_queries_failed_key_when_all_succeed(self, monkeypatch):
        from uspto_enriched_citation_mcp.services.citation_service import CitationService
        from uspto_enriched_citation_mcp.util import rate_limiter as rl

        rl.reset_rate_limiter()
        limiter = rl.get_rate_limiter(rl.RateLimitConfig(requests_per_minute=60))

        async def allow(endpoint="default", tokens=1):
            return True

        monkeypatch.setattr(limiter, "acquire", allow)

        class _HealthyClient:
            async def search_citations(self, criteria, rows=0, **kwargs):
                return {"response": {"numFound": 5}}

        service = CitationService(_HealthyClient(), field_manager=None)
        result = await service.get_statistics(criteria="techCenter:2100")

        assert result["status"] == "success"
        assert "queries_failed" not in result

        rl.reset_rate_limiter()


# ------------------------------------------------------------------------- E1


class TestAuthStoreFailureCleanError:
    """A SQLite/aiosqlite failure mid-OAuth-flow must yield a clean error
    response, never an unhandled traceback (see auth/provider.py)."""

    @pytest.mark.asyncio
    async def test_store_failure_mid_callback_yields_clean_error_page(self, monkeypatch):
        from tests.test_auth_provider import make_provider, run_callback

        provider, store = make_provider()
        store.users["jane@firm.com"] = {
            "email": "jane@firm.com", "role": "user", "active": True,
            "display_name": None, "last_login_idp": None,
        }

        async def boom(email):
            raise RuntimeError("database is locked")

        monkeypatch.setattr(store, "get_user", boom)

        resp = await run_callback(
            provider, monkeypatch,
            {"email": "jane@firm.com", "email_verified": True, "name": "Jane"},
        )

        assert resp.status_code == 503
        body = resp.body
        if isinstance(body, (bytes, bytearray)):
            body = body.decode()
        assert "RuntimeError" not in body
        assert "database is locked" not in body

    @pytest.mark.asyncio
    async def test_get_client_store_failure_returns_none_not_raises(self, monkeypatch):
        from tests.test_auth_provider import make_provider

        provider, store = make_provider()

        async def boom(client_id):
            raise RuntimeError("database is locked")

        monkeypatch.setattr(store, "get_client", boom)

        result = await provider.get_client("some-client")
        assert result is None

    @pytest.mark.asyncio
    async def test_load_authorization_code_store_failure_returns_none(self, monkeypatch):
        from tests.test_auth_provider import make_provider, make_client

        provider, store = make_provider()

        async def boom(code):
            raise RuntimeError("database is locked")

        monkeypatch.setattr(store, "take_code", boom)

        result = await provider.load_authorization_code(make_client(), "some-code")
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
