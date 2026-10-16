"""shared/client_ip.py: the caller's real address behind an optional trusted
reverse proxy (CR-01, review 2026-09-28).

Default (TRUSTED_PROXY_IPS unset) is byte-for-byte what every limiter did
before: no header is consulted and the raw ASGI peer is used as-is. Once a
trust CIDR is declared, CF-Connecting-IP is honored from that one trusted
peer without needing a second CIDR to strip an intermediate hop, and
X-Forwarded-For's rightmost non-proxy hop is the fallback.
"""

import pytest

from uspto_enriched_citation_mcp.shared.client_ip import resolve_client_ip


def test_the_peer_address_is_used_when_no_proxy_is_declared(monkeypatch):
    """Default behavior is byte-for-byte what it was: no header consulted."""
    monkeypatch.delenv("TRUSTED_PROXY_IPS", raising=False)

    assert resolve_client_ip("10.0.0.5", "203.0.113.9") == "10.0.0.5"


def test_a_spoofed_forwarded_header_is_ignored_from_an_untrusted_peer(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "172.18.0.0/16")

    assert resolve_client_ip("203.0.113.50", "1.2.3.4") == "203.0.113.50"


def test_a_trusted_proxy_reveals_the_real_client(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "172.18.0.0/16")

    assert resolve_client_ip("172.18.0.2", "203.0.113.9") == "203.0.113.9"


def test_the_rightmost_non_proxy_hop_wins(monkeypatch):
    """The leftmost entry is client-controlled; the rightmost non-proxy hop
    is the last address the trusted chain actually observed."""
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "172.18.0.0/16")

    resolved = resolve_client_ip(
        "172.18.0.2", "9.9.9.9, 203.0.113.9, 172.18.0.3"
    )

    assert resolved == "203.0.113.9"


@pytest.mark.parametrize("garbage", ["", "not-an-ip", ",,,"])
def test_a_garbage_forwarded_header_falls_back_to_the_peer(monkeypatch, garbage):
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "172.18.0.0/16")

    assert resolve_client_ip("172.18.0.2", garbage) == "172.18.0.2"


def test_a_malformed_trusted_proxy_entry_never_matches(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "not-a-cidr")

    assert resolve_client_ip("172.18.0.2", "203.0.113.9") == "172.18.0.2"


# --------------------------------------------------- CF-Connecting-IP (CR-01)


def test_cf_connecting_ip_is_honored_from_a_trusted_peer(monkeypatch):
    """A single trusted-proxy CIDR (the immediate peer) is enough for
    CF-Connecting-IP: it survives every intermediate hop unmodified, unlike
    X-Forwarded-For, which can need a second declared hop just to strip."""
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "172.18.0.0/16")

    resolved = resolve_client_ip(
        "172.18.0.4", "9.9.9.9, 172.18.0.1", "203.0.113.9"
    )

    assert resolved == "203.0.113.9"


def test_cf_connecting_ip_is_ignored_from_an_untrusted_peer(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "172.18.0.0/16")

    assert resolve_client_ip("203.0.113.50", None, "1.2.3.4") == "203.0.113.50"


def test_forwarded_for_is_still_the_fallback_when_cf_header_is_absent(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "172.18.0.0/16")

    resolved = resolve_client_ip("172.18.0.4", "203.0.113.9", None)

    assert resolved == "203.0.113.9"


def test_a_malformed_cf_connecting_ip_falls_back_to_forwarded_for(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "172.18.0.0/16")

    resolved = resolve_client_ip("172.18.0.4", "203.0.113.9", "not-an-ip")

    assert resolved == "203.0.113.9"


def test_ipv6_client_keys_collapse_to_their_slash_56(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "172.18.0.0/16")

    resolved = resolve_client_ip("172.18.0.4", None, "2001:db8:1234:5678::1")

    assert resolved == "2001:db8:1234:5600::"


def test_ipv6_peer_collapses_with_no_proxy_declared(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_IPS", raising=False)

    assert resolve_client_ip("2001:db8:1234:5678::1") == "2001:db8:1234:5600::"
