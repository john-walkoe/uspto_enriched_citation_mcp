"""
Unit tests for USPTO Office Action Citations API v2 client.

Tests OACitationsClient with mocked httpx responses.

Run with: uv run pytest tests/test_oa_citations_client.py -v
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from uspto_enriched_citation_mcp.api.oa_citations_client import (
    OACitationsClient,
    OA_CITATIONS_MINIMAL_FIELDS,
)
from uspto_enriched_citation_mcp.shared.exceptions import (
    RateLimitError,
    APIConnectionError,
    APITimeoutError,
    APIResponseError,
    ValidationError,
)
from uspto_enriched_citation_mcp.shared.circuit_breaker import (
    CircuitBreakerError,
    CircuitState,
)


def make_mock_response(status_code=200, json_data=None, headers=None,
                       content=b"{}"):
    """Factory for httpx Response mocks that look like real httpx.Response."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data if json_data is not None else {}
    response.headers = headers or {}
    response.content = content
    return response


def reset_shared_circuit_breaker():
    """Reset the module-level uspta_api_breaker to CLOSED state."""
    from uspto_enriched_citation_mcp.api import oa_citations_client
    breaker = oa_citations_client.uspto_api_breaker
    breaker._state = CircuitState.CLOSED
    breaker._failure_count = 0
    breaker._success_count = 0
    breaker._last_failure_time = None


class TestOACitationsClientFields:
    """Tests for get_fields() method."""

    @pytest.fixture(autouse=True)
    def reset_breaker(self):
        reset_shared_circuit_breaker()

    @pytest.fixture
    def client(self):
        return OACitationsClient(
            api_key="test-key-32-chars-minimum-ok",
            base_url="https://api.uspto.gov",
            enable_cache=False,
        )

    @pytest.mark.asyncio
    async def test_oa_client_fields(self, client):
        """Test 1: get_fields() happy path returns parsed field list."""
        mock_fields_response = {
            "fields": [
                {"name": "patentApplicationNumber", "type": "string"},
                {"name": "groupArtUnitNumber", "type": "string"},
            ]
        }
        mock_response = make_mock_response(
            status_code=200,
            json_data=mock_fields_response,
            headers={"content-type": "application/json"},
        )

        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await client.get_fields()

        assert result == mock_fields_response
        assert "fields" in result
        mock_get.assert_called_once()
        url = mock_get.call_args[0][0]
        assert "/oa_citations/v2/fields" in url


class TestOACitationsClientSearch:
    """Tests for search_records() method."""

    @pytest.fixture(autouse=True)
    def reset_breaker(self):
        reset_shared_circuit_breaker()

    @pytest.fixture
    def client(self):
        return OACitationsClient(
            api_key="test-key-32-chars-minimum-ok",
            base_url="https://api.uspto.gov",
            enable_cache=False,
        )

    @pytest.mark.asyncio
    async def test_oa_client_search(self, client):
        """Test 2: search_records() happy path returns parsed docs."""
        mock_search_response = {
            "response": {
                "numFound": 1,
                "start": 0,
                "docs": [
                    {
                        "patentApplicationNumber": "17896175",
                        "groupArtUnitNumber": "2854",
                    }
                ],
            }
        }
        mock_response = make_mock_response(
            status_code=200,
            json_data=mock_search_response,
            headers={"content-type": "application/json"},
        )

        with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await client.search_records(
                criteria="techCenter:2100",
                rows=50,
                selected_fields=OA_CITATIONS_MINIMAL_FIELDS,
            )

        assert "response" in result
        assert "docs" in result["response"]
        assert len(result["response"]["docs"]) == 1
        mock_post.assert_called_once()
        url = mock_post.call_args[0][0]
        assert "/oa_citations/v2/records" in url


class TestOACitationsClientErrors:
    """Tests for error handling in OACitationsClient."""

    @pytest.fixture(autouse=True)
    def reset_breaker(self):
        reset_shared_circuit_breaker()

    @pytest.fixture
    def client(self):
        return OACitationsClient(
            api_key="test-key-32-chars-minimum-ok",
            base_url="https://api.uspto.gov",
            enable_cache=False,
        )

    @pytest.mark.asyncio
    async def test_oa_client_timeout(self, client, no_backoff):
        """Test 3: httpx TimeoutException raises APITimeoutError.

        The side effect goes on `_send`, the documented single choke point,
        not on `response.json()`: a real timeout is raised by the send, and
        setting it on the parse kept passing even if the send moved out of
        the try (Q-4). Mocking `_send` also keeps the test independent of the
        fact that `_send` happens to use `self.client.get` (Q-3).
        """
        import httpx

        with patch.object(
            client, "_send", new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timed out"),
        ):
            with pytest.raises(APITimeoutError):
                await client.get_fields()

    @pytest.mark.asyncio
    async def test_oa_client_connect_error(self, client, no_backoff):
        """Test 4: httpx ConnectError raises APIConnectionError."""
        import httpx

        with patch.object(
            client, "_send", new_callable=AsyncMock,
            side_effect=httpx.ConnectError("connection refused"),
        ):
            with pytest.raises(APIConnectionError):
                await client.get_fields()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "status_code,expected_exception",
        [
            (429, RateLimitError),
            (500, APIResponseError),
        ],
    )
    async def test_oa_client_http_error(
        self, client, no_backoff, status_code, expected_exception
    ):
        """Test 5: HTTP errors raise appropriate exceptions (parametrized)."""
        mock_response = make_mock_response(
            status_code=status_code,
            json_data={"error": f"HTTP {status_code}"},
            headers={"content-type": "application/json"},
            content=b'{"error":"error"}',
        )

        with patch.object(client, "_send", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_response
            with pytest.raises(expected_exception):
                await client.get_fields()

    @pytest.mark.asyncio
    async def test_oa_client_empty_criteria(self, client):
        """Test 7: Empty criteria raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            await client.search_records(criteria="   ", rows=50)
        assert exc_info.value.status_code == 400
        assert "criteria" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_oa_client_rows_limit(self, client):
        """Test 8: rows > 1000 raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            await client.search_records(criteria="techCenter:2100", rows=1001)
        assert exc_info.value.status_code == 400
        assert "rows" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_oa_client_invalid_content_type(self, client):
        """Test 9: Wrong Content-Type raises APIResponseError."""
        mock_response = make_mock_response(
            status_code=200,
            json_data={},
            headers={"content-type": "text/html"},
            content=b"<html>Not JSON</html>",
        )

        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            with pytest.raises(APIResponseError) as exc_info:
                await client.get_fields()
        assert "Content-Type" in str(exc_info.value.message) or "Unexpected" in str(
            exc_info.value.message
        )

    @pytest.mark.asyncio
    async def test_oa_client_content_length_exceeded(self, client):
        """Test 10: Content-Length too large raises APIResponseError."""
        mock_response = make_mock_response(
            status_code=200,
            json_data={},
            headers={
                "content-type": "application/json",
                "content-length": str(60 * 1024 * 1024),  # 60 MB > 50 MB limit
            },
            content=b"x" * 100,
        )

        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            with pytest.raises(APIResponseError) as exc_info:
                await client.get_fields()
        assert "too large" in str(exc_info.value.message).lower() or "Response" in str(
            exc_info.value.message
        )


class TestOACitationsClientCircuitBreaker:
    """Tests for circuit breaker integration with stale cache fallback.

    Each test resets the circuit breaker and global caches explicitly rather
    than relying on autouse fixtures, which can run before named fixtures
    depending on execution order.
    """

    @pytest.fixture
    def fresh_client(self):
        """Create a client with freshly-reset global caches and circuit breaker."""
        from uspto_enriched_citation_mcp.api import oa_citations_client
        from uspto_enriched_citation_mcp.util import cache as cache_mod

        # Reset circuit breaker and global cache singletons BEFORE creating client
        breaker = oa_citations_client.uspto_api_breaker
        breaker._state = CircuitState.CLOSED
        breaker._failure_count = 0
        breaker._success_count = 0
        breaker._last_failure_time = None
        cache_mod._fields_cache = None
        cache_mod._search_cache = None

        return OACitationsClient(
            api_key="test-key-32-chars-minimum-ok",
            base_url="https://api.uspto.gov",
            enable_cache=True,
            fields_cache_ttl=3600,
            search_cache_size=100,
        )

    @pytest.mark.asyncio
    async def test_oa_client_circuit_breaker_open_fields_stale_cache(
        self, fresh_client
    ):
        """Test 6: Circuit breaker open → uses stale cache with _cache_status."""
        from uspto_enriched_citation_mcp.util.cache import generate_cache_key

        cache_key = generate_cache_key("oa_fields", "https://api.uspto.gov")
        stale_data = {"fields": [{"name": "stale_field"}]}
        fresh_client.fields_cache.set(cache_key, stale_data)

        with patch.object(
            fresh_client,
            "_get_fields_impl",
            side_effect=CircuitBreakerError("Circuit breaker is OPEN"),
        ):
            result = await fresh_client.get_fields()

        assert result["_cache_status"]["source"] == "stale_cache"
        assert result["_cache_status"]["circuit_breaker"] == "open"
        assert result["fields"] == stale_data["fields"]

    @pytest.mark.asyncio
    async def test_oa_client_circuit_breaker_open_search_no_cache(
        self, fresh_client
    ):
        """Test 6b: Circuit breaker open + no cache → raises CircuitBreakerError."""
        fresh_client.search_cache.clear()

        with patch.object(
            fresh_client.client,
            "post",
            side_effect=CircuitBreakerError("Circuit breaker is OPEN"),
        ):
            with pytest.raises(CircuitBreakerError):
                await fresh_client.search_records(
                    criteria="techCenter:2100", rows=50
                )


class TestOACitationsClientValidation:
    """Tests for input validation."""

    @pytest.fixture(autouse=True)
    def reset_breaker(self):
        reset_shared_circuit_breaker()

    @pytest.fixture
    def client(self):
        return OACitationsClient(
            api_key="test-key-32-chars-minimum-ok",
            base_url="https://api.uspto.gov",
            enable_cache=False,
        )

    @pytest.mark.asyncio
    async def test_search_empty_criteria_whitespace(self, client):
        """Empty criteria (whitespace-only) raises ValidationError."""
        with pytest.raises(ValidationError):
            await client.search_records(criteria="  \n\t  ", rows=50)

    @pytest.mark.asyncio
    async def test_search_negative_start(self, client):
        """Negative start index is accepted by client (API would reject it)."""
        mock_response = make_mock_response(
            status_code=200,
            json_data={"response": {"numFound": 0, "docs": []}},
            headers={"content-type": "application/json"},
        )

        with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await client.search_records(
                criteria="techCenter:2100", start=-1, rows=50
            )
            assert "response" in result

    @pytest.mark.asyncio
    async def test_search_zero_rows(self, client):
        """Zero rows is accepted by client (API would reject it)."""
        mock_response = make_mock_response(
            status_code=200,
            json_data={"response": {"numFound": 0, "docs": []}},
            headers={"content-type": "application/json"},
        )

        with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await client.search_records(criteria="techCenter:2100", rows=0)
            assert "response" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
