"""Server bootstrap: transport entry point (SD-1 split).

Owns the stdio/HTTP entry point (M1 fail-closed check, CORS build, middleware
stack, uvicorn.run). Imports the composition root lazily inside the function
— main.py imports this module for its `main()` back-compat re-export.
"""

import os
from typing import List, Optional

from .middleware import (
    APIKeyAuthMiddleware,
    InboundRateLimitMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)
from .runtime import initialize_services
from .config.settings import get_settings
from .util.logging import attach_uvicorn_sanitizer, get_logger

logger = get_logger(__name__)

_LOOPBACK_ORIGIN_RE = r"^http://(localhost|127\.0\.0\.1)(:[0-9]+)?$"


def build_cors_origins(cors_extra_origin: Optional[str]) -> List[str]:
    """Build the CORS allowlist.

    The two loopback development origins used to be present in every
    deployment; they are now gated on CITATIONS_DEV_CORS. An extra origin
    must be HTTPS unless it is loopback, matching the check
    build_auth_provider already applies to auth_base_url (S-24).
    """
    import re

    origins: List[str] = []
    if os.getenv("CITATIONS_DEV_CORS", "").lower() in ("1", "true", "yes"):
        origins = ["http://localhost:8080", "http://127.0.0.1:8080"]

    if not cors_extra_origin:
        return origins

    # SECURITY: Validate CORS origin to prevent injection of arbitrary origins
    if not re.match(r"^https?://[a-zA-Z0-9.\-]+(:[0-9]+)?$", cors_extra_origin):
        raise ValueError(
            f"CORS_EXTRA_ORIGIN must be a valid HTTP/HTTPS URL, got: {cors_extra_origin}"
        )
    if not (
        cors_extra_origin.startswith("https://")
        or re.match(_LOOPBACK_ORIGIN_RE, cors_extra_origin)
    ):
        raise ValueError(
            "CORS_EXTRA_ORIGIN must use https:// (loopback excepted). A "
            "plaintext origin lets a network attacker read tool responses. "
            "Got: " + cors_extra_origin
        )
    origins.append(cors_extra_origin)
    logger.info(f"CORS: added extra origin {cors_extra_origin}")
    return origins


def run_server():
    """Synchronous entry point for console scripts.

    Transport is controlled by environment variables:
      FASTMCP_TRANSPORT=http   → HTTP mode (required for MCP Apps)
      FASTMCP_HOST=0.0.0.0     → bind address (HTTP mode only)
      FASTMCP_PORT=8000         → port (HTTP mode only)
      CORS_EXTRA_ORIGIN=https://  → additional CORS origin for reverse proxy

    Default: stdio (Claude Desktop / Claude Code compatible)
    """
    from . import main as _main  # composition root (lazy: avoids circular import)

    mcp = _main.mcp
    _AUTH_PROVIDER = _main._AUTH_PROVIDER

    logger.info("Starting USPTO Enriched Citation MCP server...")

    transport = os.getenv("FASTMCP_TRANSPORT", "stdio")

    if transport == "http":
        # SECURITY (M1): fail closed instead of fail open, checked before any
        # other startup work. Plain-HTTP mode (CITATIONS_AUTH_MODE != oauth)
        # relies entirely on APIKeyAuthMiddleware for authentication; if
        # INTERNAL_AUTH_SECRET never resolves (no DPAPI entry, no env var),
        # that middleware lets every request through unauthenticated. Refuse
        # to start rather than serve an open deployment. OAuth mode is
        # exempt: the MCP surface is bearer-protected by FastMCP instead, and
        # the x-api-key guard is intentionally not wired there.
        if _AUTH_PROVIDER is None:
            from .shared_secure_storage import get_internal_auth_secret as _get_secret_startup

            _auth_secret_check = _get_secret_startup() or os.environ.get(
                "INTERNAL_AUTH_SECRET"
            )
            if not _auth_secret_check:
                logger.error(
                    "INTERNAL_AUTH_SECRET is required for HTTP transport mode "
                    "(CITATIONS_AUTH_MODE=none). Set it as an environment "
                    "variable or store it via the key management system, or "
                    "set CITATIONS_AUTH_MODE=oauth. Refusing to start an "
                    "unauthenticated HTTP server."
                )
                raise SystemExit(1)

    initialize_services()
    logger.info("Progressive disclosure enabled - use minimal searches first")

    if transport == "http":
        settings = get_settings()

        # SECURITY: Reject non-HTTPS base URLs — API key is sent as X-API-KEY header
        if settings.uspto_base_url.startswith("http://"):
            logger.error(
                "HTTP USPTO_BASE_URL rejected in FASTMCP_TRANSPORT=http mode: "
                "API key would be transmitted without TLS encryption. "
                "Set USPTO_BASE_URL to https://api.uspto.gov or use FASTMCP_TRANSPORT=stdio."
            )
            raise ValueError(
                "FASTMCP_TRANSPORT=http requires USPTO_BASE_URL to use HTTPS. "
                "Got: " + settings.uspto_base_url
            )

        host = settings.http_host
        port = settings.http_port

        origins = build_cors_origins(settings.cors_extra_origin)

        from starlette.middleware.cors import CORSMiddleware
        import uvicorn
        # Middleware stack (outermost first): SecurityHeaders → APIKeyAuth →
        # InboundRateLimit → SizeLimit → CORS → mcp app.
        # Security headers wrap everything so they appear on 401 responses too.
        # SizeLimit (M3) caps tool-call JSON bodies before they reach FastMCP.
        # InboundRateLimit meters requests per identity: the only RateLimiter
        # in the process paced OUTBOUND USPTO calls, so nothing metered what
        # came in, while main.py's health route claimed otherwise.
        inner = RequestSizeLimitMiddleware(
            CORSMiddleware(
                mcp.http_app(stateless_http=settings.fastmcp_stateless_http),
                allow_origins=origins,
                allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
                # X-API-KEY removed from allow_headers — auth is enforced via
                # APIKeyAuthMiddleware, not CORS; reduces browser key exposure
                allow_headers=["Content-Type", "Accept", "Mcp-Session-Id"],
                expose_headers=["Mcp-Session-Id"],
            )
        )
        if _AUTH_PROVIDER is not None:
            # OAuth mode: FastMCP's bearer middleware guards /mcp, and the
            # OAuth routes (/authorize, /token, /register, /auth/*,
            # /.well-known/*) must be reachable without a shared secret for
            # the flow to work at all. The legacy x-api-key guard is
            # therefore disabled — headless clients present
            # CITATIONS_AUTH_INTERNAL_TOKEN as a bearer instead.
            logger.warning(
                "CITATIONS_AUTH_MODE=oauth: x-api-key guard disabled; the MCP "
                "surface is protected by bearer tokens."
            )
            app = SecurityHeadersMiddleware(InboundRateLimitMiddleware(inner))
        else:
            app = SecurityHeadersMiddleware(
                APIKeyAuthMiddleware(InboundRateLimitMiddleware(inner))
            )
        logger.info(f"Starting HTTP transport on {host}:{port}")
        # uvicorn logs unhandled ASGI tracebacks on its own handler, which
        # never sees SanitizingFilter — the one class of record the redaction
        # policy exists for (E-4). Attached before uvicorn.run installs the
        # handlers, and again from the app's startup hook.
        attach_uvicorn_sanitizer()
        # access_log off: access lines include request paths and client IPs,
        # and uvicorn's access logger bypasses our sanitizing handlers.
        #
        # proxy_headers with forwarded_allow_ips pinned to the reverse proxy:
        # without it uvicorn's default only trusts 127.0.0.1, never matches
        # the container-network proxy peer, and every request appears to come
        # from one address — which collapses the OAuth rate limiter to a
        # single shared bucket for the whole internet (S-08). Never "*": an
        # unpinned allow list makes X-Forwarded-For attacker-controlled.
        trusted_proxies = os.getenv("TRUSTED_PROXY_IPS", "127.0.0.1")
        if trusted_proxies.strip() == "*":
            raise ValueError(
                "TRUSTED_PROXY_IPS='*' would let any client spoof its address "
                "through X-Forwarded-For and bypass the rate limiter. Name the "
                "proxy's address instead."
            )
        try:
            uvicorn.run(
                app,
                host=host,
                port=port,
                access_log=False,
                proxy_headers=True,
                forwarded_allow_ips=trusted_proxies,
            )
        finally:
            _close_services()
    else:
        try:
            mcp.run(transport="stdio")
        finally:
            _close_services()


def _close_services() -> None:
    """Close the three httpx pools on the way out.

    initialize_services() had no counterpart, so on SIGTERM up to 30 sockets
    were torn down by process exit rather than closed (F-2). uvicorn.run and
    mcp.run both block until the server stops, so this runs once, after.
    """
    import asyncio

    from .runtime import shutdown_services

    try:
        asyncio.run(shutdown_services())
    except Exception:  # pragma: no cover - shutdown must not mask the exit
        logger.warning("Service shutdown did not complete cleanly")


if __name__ == "__main__":
    run_server()
