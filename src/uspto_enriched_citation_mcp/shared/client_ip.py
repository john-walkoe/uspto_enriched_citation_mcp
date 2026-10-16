"""Resolve the caller's address behind an optional trusted reverse proxy.

CR-01 (review 2026-09-28): the OAuth-route limiters (auth/provider.py's
`_FixedWindowRateLimiter` / `_RateLimitedASGIApp` / `_callback_endpoint`) and
the inbound `/mcp` limiter's IP fallback (middleware.py) all keyed on the raw
ASGI peer address. Behind a reverse proxy that is ONE value for the whole
internet, so every limiter throttled all callers as if they were a single
client: behind, say, a Cloudflare tunnel -> reverse proxy -> this container,
the peer every request reaches this server with is the proxy's address. `X-Forwarded-For` must not be trusted from
an arbitrary caller — it is trivially spoofable — so proxy headers are read
only when the peer itself is an operator-declared proxy.

`TRUSTED_PROXY_IPS` (comma-separated IPs or CIDRs; the setting
server_bootstrap.py already reads for uvicorn's own `forwarded_allow_ips`,
reused here rather than adding a second variable) is empty by default, which
reproduces the previous behavior exactly: no header is consulted and the peer
address is used as-is. Typical value: the docker network the reverse proxy
sits on, e.g. `172.18.0.0/16`.

`CF-Connecting-IP` is preferred once the peer is trusted: Cloudflare sets it
at its edge and it survives unmodified through every hop in between, so
trusting the ONE immediate-peer CIDR is enough — no second CIDR is needed to
strip an intermediate hop (e.g. the cloudflared connector) off an
X-Forwarded-For chain. X-Forwarded-For's rightmost-untrusted hop is the
fallback for a self-hosted deployment behind a plain nginx/Traefik reverse
proxy that does not set CF-Connecting-IP.
"""

from __future__ import annotations

import ipaddress
import os
from typing import Any, List, Optional

_UNKNOWN = "unknown"


def trusted_proxy_networks() -> List[Any]:
    """Parse TRUSTED_PROXY_IPS into ip_network objects."""
    networks: List[Any] = []
    for entry in os.getenv("TRUSTED_PROXY_IPS", "").split(","):
        entry = entry.strip()
        if not entry:
            continue
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            # A malformed entry must not be treated as a match — narrowing
            # trust is safe, silently widening it to "accept everything"
            # is not.
            continue
    return networks


def _in_networks(address: str, networks: List[Any]) -> bool:
    if not networks:
        return False
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return False
    return any(parsed in network for network in networks)


def collapse_ipv6(address: str) -> str:
    """Collapse an IPv6 address to its /56 for rate-limit keying: a caller
    who owns a /56 (a common residential or cloud allocation) must not be
    able to rotate through it for a fresh bucket per address. IPv4 addresses
    and anything that fails to parse pass through unchanged."""
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return address
    if isinstance(parsed, ipaddress.IPv6Address):
        return str(ipaddress.ip_network(f"{parsed}/56", strict=False).network_address)
    return address


def resolve_client_ip(
    peer: Optional[str],
    forwarded_for: Optional[str] = None,
    cf_connecting_ip: Optional[str] = None,
) -> str:
    """The caller's address, honoring proxy headers only from a declared proxy.

    Args:
        peer: the raw ASGI peer address (`scope["client"][0]` /
            `request.client.host`).
        forwarded_for: the `X-Forwarded-For` header value, if any.
        cf_connecting_ip: the `CF-Connecting-IP` header value, if any.

    Returns the peer address unless the peer is a trusted proxy, in which
    case `CF-Connecting-IP` is used when present and parseable, else the
    RIGHTMOST `X-Forwarded-For` entry that is not itself a trusted proxy —
    the last hop the trusted chain actually observed, rather than the
    leftmost value, which the client controls. The result is collapsed to a
    /56 for IPv6.
    """
    peer = (peer or "").strip() or _UNKNOWN
    networks = trusted_proxy_networks()
    if not networks or not _in_networks(peer, networks):
        return collapse_ipv6(peer)
    cf_connecting_ip = (cf_connecting_ip or "").strip()
    if cf_connecting_ip:
        try:
            ipaddress.ip_address(cf_connecting_ip)
        except ValueError:
            pass
        else:
            return collapse_ipv6(cf_connecting_ip)
    if not forwarded_for:
        return collapse_ipv6(peer)
    candidates = [part.strip() for part in forwarded_for.split(",") if part.strip()]
    for candidate in reversed(candidates):
        if _in_networks(candidate, networks):
            continue
        try:
            ipaddress.ip_address(candidate)
        except ValueError:
            continue
        return collapse_ipv6(candidate)
    return collapse_ipv6(peer)


def client_ip_from_request(request: Any) -> str:
    """resolve_client_ip for a Starlette/FastAPI Request."""
    client = getattr(request, "client", None)
    peer = getattr(client, "host", None) if client is not None else None
    headers = getattr(request, "headers", None)
    forwarded = headers.get("x-forwarded-for") if headers is not None else None
    cf_connecting_ip = headers.get("cf-connecting-ip") if headers is not None else None
    return resolve_client_ip(peer, forwarded, cf_connecting_ip)


def client_ip_from_scope(scope: Any) -> str:
    """resolve_client_ip for a raw ASGI scope (InboundRateLimitMiddleware,
    auth/provider.py's _RateLimitedASGIApp — both wrap an ASGI app directly
    rather than going through a Starlette Request)."""
    client = scope.get("client")
    peer = client[0] if client else None
    headers = {name: value for name, value in scope.get("headers", [])}
    forwarded = headers.get(b"x-forwarded-for", b"").decode("latin-1") or None
    cf_connecting_ip = headers.get(b"cf-connecting-ip", b"").decode("latin-1") or None
    return resolve_client_ip(peer, forwarded, cf_connecting_ip)
