"""INTERNAL_AUTH_SECRET rotation overlap window for the x-api-key transport
gate (S-06: one INTERNAL_AUTH_SECRET across all four USPTO MCPs, create-only,
with no rotation path). Citations does not mint or verify inter-MCP service
tokens, so only the transport gate applies here.
"""

import pytest

from uspto_enriched_citation_mcp.middleware import (
    APIKeyAuthMiddleware,
    _matches_any_candidate,
)
from uspto_enriched_citation_mcp.shared_secure_storage import (
    split_secret_candidates,
)


def _scope(headers=None):
    return {
        "type": "http",
        "path": "/mcp",
        "method": "POST",
        "headers": headers or [],
        "client": ("10.0.0.1", 51234),
        "query_string": b"",
        "scheme": "https",
        "server": ("testserver", 443),
    }


class TestSplitSecretCandidates:
    def test_dedupes_strips_and_orders(self):
        assert split_secret_candidates("a, b ,a,,  ") == ["a", "b"]
        assert split_secret_candidates("solo") == ["solo"]
        assert split_secret_candidates(None) == []
        assert split_secret_candidates("") == []


class TestMatchesAnyCandidate:
    def test_a_single_value_still_round_trips(self):
        assert _matches_any_candidate("secret", ["secret"]) is True
        assert _matches_any_candidate("wrong", ["secret"]) is False

    def test_accepts_current_and_previous(self):
        candidates = ["current-value", "previous-value"]
        assert _matches_any_candidate("current-value", candidates) is True
        assert _matches_any_candidate("previous-value", candidates) is True

    def test_rejects_a_value_not_in_the_rotation_window(self):
        candidates = ["current-value", "previous-value"]
        assert _matches_any_candidate("some-other-value", candidates) is False
        assert _matches_any_candidate(None, candidates) is False
        assert _matches_any_candidate("", candidates) is False


@pytest.mark.asyncio
class TestMiddlewareRotationWindow:
    async def test_the_previous_value_authenticates_during_rollout(
        self, monkeypatch
    ):
        monkeypatch.setenv("INTERNAL_AUTH_SECRET", "new-secret,old-secret")
        monkeypatch.setattr(
            "uspto_enriched_citation_mcp.shared_secure_storage.get_internal_auth_secret",
            lambda: None,
        )

        reached = []

        async def _app(scope, receive, send):
            reached.append(True)

        sent = []

        async def _send(message):
            sent.append(message)

        await APIKeyAuthMiddleware(_app)(
            _scope(headers=[(b"x-api-key", b"old-secret")]), None, _send
        )

        assert reached == [True]
        assert sent == []

    async def test_the_current_value_authenticates_during_rollout(
        self, monkeypatch
    ):
        monkeypatch.setenv("INTERNAL_AUTH_SECRET", "new-secret,old-secret")
        monkeypatch.setattr(
            "uspto_enriched_citation_mcp.shared_secure_storage.get_internal_auth_secret",
            lambda: None,
        )

        reached = []

        async def _app(scope, receive, send):
            reached.append(True)

        await APIKeyAuthMiddleware(_app)(
            _scope(headers=[(b"x-api-key", b"new-secret")]), None, lambda m: None
        )

        assert reached == [True]

    async def test_a_value_outside_the_rotation_window_is_rejected(
        self, monkeypatch
    ):
        monkeypatch.setenv("INTERNAL_AUTH_SECRET", "new-secret,old-secret")
        monkeypatch.setattr(
            "uspto_enriched_citation_mcp.shared_secure_storage.get_internal_auth_secret",
            lambda: None,
        )

        async def _app(scope, receive, send):
            raise AssertionError("request must not reach the inner app")

        sent = []

        async def _send(message):
            sent.append(message)

        await APIKeyAuthMiddleware(_app)(
            _scope(headers=[(b"x-api-key", b"third-secret")]), None, _send
        )

        assert sent[0]["status"] == 401
