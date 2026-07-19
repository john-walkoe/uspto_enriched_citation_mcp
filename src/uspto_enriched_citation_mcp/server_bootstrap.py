"""Server bootstrap: transport entry point (SD-1 split).

Owns the stdio/HTTP entry point (M1 fail-closed check, CORS build, middleware
stack, uvicorn.run). Imports the composition root lazily inside the function
— main.py imports this module for its `main()` back-compat re-export.
"""

import os

from .middleware import (
    APIKeyAuthMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)
from .runtime import initialize_services
from .config.settings import get_settings
from .util.logging import get_logger

logger = get_logger(__name__)


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

        # Build CORS origins list
        origins = ["http://localhost:8080", "http://127.0.0.1:8080"]
        if settings.cors_extra_origin:
            # SECURITY: Validate CORS origin to prevent injection of arbitrary origins
            import re
            if not re.match(r"^https?://[a-zA-Z0-9.\-]+(:[0-9]+)?$", settings.cors_extra_origin):
                raise ValueError(
                    f"CORS_EXTRA_ORIGIN must be a valid HTTP/HTTPS URL, got: {settings.cors_extra_origin}"
                )
            origins.append(settings.cors_extra_origin)
            logger.info(f"CORS: added extra origin {settings.cors_extra_origin}")

        from starlette.middleware.cors import CORSMiddleware
        import uvicorn
        # Middleware stack (outermost first): SecurityHeaders → APIKeyAuth → SizeLimit → CORS → mcp app
        # Security headers wrap everything so they appear on 401 responses too.
        # SizeLimit (M3) caps tool-call JSON bodies before they reach FastMCP.
        inner = RequestSizeLimitMiddleware(
            CORSMiddleware(
                mcp.http_app(),
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
            app = SecurityHeadersMiddleware(inner)
        else:
            app = SecurityHeadersMiddleware(APIKeyAuthMiddleware(inner))
        logger.info(f"Starting HTTP transport on {host}:{port}")
        # access_log off: access lines include request paths and client IPs,
        # and uvicorn's access logger bypasses our sanitizing handlers
        uvicorn.run(app, host=host, port=port, access_log=False)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    run_server()
