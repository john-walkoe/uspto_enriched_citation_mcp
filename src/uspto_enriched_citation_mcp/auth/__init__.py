"""Dual-IdP OAuth authorization server for the citations MCP (HTTP mode)."""
from .provider import (
    SCOPE_ADMIN,
    SCOPE_USER,
    CitationsAuthProvider,
    build_auth_provider,
)
from .store import McpUserStore

__all__ = [
    "SCOPE_ADMIN",
    "SCOPE_USER",
    "CitationsAuthProvider",
    "McpUserStore",
    "build_auth_provider",
]
