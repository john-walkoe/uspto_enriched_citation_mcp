"""Settings management for USPTO Enriched Citation MCP."""

import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator

# Import configuration defaults (single source of truth)
from .constants import (
    DEFAULT_BASE_URL,
    DEFAULT_MCP_SERVER_PORT,
    DEFAULT_HTTP_PORT,
    DEFAULT_RATE_LIMIT_RPM,
    DEFAULT_API_TIMEOUT,
    DEFAULT_CONNECT_TIMEOUT,
    ENABLE_CACHE_DEFAULT,
    FIELDS_CACHE_TTL_SECONDS,
    SEARCH_CACHE_SIZE,
    MAX_MINIMAL_SEARCH_ROWS,
    DEFAULT_BALANCED_SEARCH_ROWS,
    MAX_ROWS_PER_REQUEST,
    DEFAULT_FIELD_CONFIG_PATH,
    DEFAULT_LOG_LEVEL,
    DEFAULT_REQUEST_ID_HEADER,
    MIN_API_KEY_LENGTH,
    MAX_API_KEY_LENGTH,
)


class Settings(BaseSettings):
    """Application settings with secure API key management."""

    model_config = SettingsConfigDict(env_file_encoding="utf-8")

    # USPTO API Configuration
    uspto_ecitation_api_key: str = Field(..., validation_alias="USPTO_API_KEY")
    uspto_base_url: str = Field(
        default=DEFAULT_BASE_URL,
        validation_alias="USPTO_BASE_URL",
    )

    # MCP Configuration
    mcp_server_port: int = Field(
        default=DEFAULT_MCP_SERVER_PORT,
        validation_alias="MCP_SERVER_PORT"
    )

    # Rate Limiting
    request_rate_limit: int = Field(
        default=DEFAULT_RATE_LIMIT_RPM,
        validation_alias="ECITATION_RATE_LIMIT"
    )

    # Timeouts (seconds)
    api_timeout: float = Field(
        default=DEFAULT_API_TIMEOUT,
        validation_alias="API_TIMEOUT"
    )
    connect_timeout: float = Field(
        default=DEFAULT_CONNECT_TIMEOUT,
        validation_alias="CONNECT_TIMEOUT"
    )

    # Caching Configuration
    enable_cache: bool = Field(
        default=ENABLE_CACHE_DEFAULT,
        validation_alias="ENABLE_CACHE"
    )
    fields_cache_ttl: int = Field(
        default=FIELDS_CACHE_TTL_SECONDS,
        validation_alias="FIELDS_CACHE_TTL"
    )
    search_cache_size: int = Field(
        default=SEARCH_CACHE_SIZE,
        validation_alias="SEARCH_CACHE_SIZE"
    )

    # Context Optimization
    max_minimal_results: int = Field(
        default=MAX_MINIMAL_SEARCH_ROWS,
        validation_alias="MAX_MINIMAL_RESULTS"
    )
    max_balanced_results: int = Field(
        default=DEFAULT_BALANCED_SEARCH_ROWS,
        validation_alias="MAX_BALANCED_RESULTS"
    )
    max_total_results: int = Field(
        default=MAX_ROWS_PER_REQUEST,
        validation_alias="MAX_TOTAL_RESULTS"
    )

    # Field Configuration
    field_config_path: str = Field(
        default=DEFAULT_FIELD_CONFIG_PATH,
        validation_alias="FIELD_CONFIG_PATH"
    )

    # HTTP Transport (for MCP Apps / reverse proxy)
    http_port: int = Field(
        default=DEFAULT_HTTP_PORT,
        validation_alias="FASTMCP_PORT"
    )
    http_host: str = Field(
        default="0.0.0.0",
        validation_alias="FASTMCP_HOST"
    )
    cors_extra_origin: Optional[str] = Field(
        default=None,
        validation_alias="CORS_EXTRA_ORIGIN"
    )

    # Logging & Security
    log_level: str = Field(
        default=DEFAULT_LOG_LEVEL,
        validation_alias="LOG_LEVEL"
    )
    request_id_header: str = Field(
        default=DEFAULT_REQUEST_ID_HEADER,
        validation_alias="REQUEST_ID_HEADER"
    )

    # OAuth sign-in (dual IdP: Google + Entra ID) — HTTP mode only.
    # Mirrors edgar_mcp's EDGAR_AUTH_* block; see auth/provider.py.
    auth_mode: str = Field(
        default="none",  # "none" (today's behavior) | "oauth"
        validation_alias="CITATIONS_AUTH_MODE",
    )
    auth_base_url: str = Field(
        default="",  # public https origin, e.g. https://mcp.example.com
        validation_alias="CITATIONS_AUTH_BASE_URL",
    )
    auth_jwt_secret: str = Field(
        default="",  # >=32 random chars; rotating invalidates all sessions
        validation_alias="CITATIONS_AUTH_JWT_SECRET",
    )
    auth_google_client_id: str = Field(
        default="", validation_alias="CITATIONS_AUTH_GOOGLE_CLIENT_ID"
    )
    auth_google_client_secret: str = Field(
        default="", validation_alias="CITATIONS_AUTH_GOOGLE_CLIENT_SECRET"
    )
    auth_ms_client_id: str = Field(
        default="", validation_alias="CITATIONS_AUTH_MS_CLIENT_ID"
    )
    auth_ms_client_secret: str = Field(
        default="", validation_alias="CITATIONS_AUTH_MS_CLIENT_SECRET"
    )
    auth_ms_tenant: str = Field(
        default="common",  # "common" | "organizations" | tenant GUID
        validation_alias="CITATIONS_AUTH_MS_TENANT",
    )
    auth_internal_token: str = Field(
        default="",  # static bearer for headless clients (internal gateways)
        validation_alias="CITATIONS_AUTH_INTERNAL_TOKEN",
    )
    auth_register_url: str = Field(
        default="",  # "Request access" link on the Not-registered page
        validation_alias="CITATIONS_AUTH_REGISTER_URL",
    )
    auth_access_ttl: int = Field(
        default=3600, validation_alias="CITATIONS_AUTH_ACCESS_TTL"
    )
    auth_refresh_ttl: int = Field(
        default=2592000,  # 30 d idle timeout; rotation keeps active users signed in
        validation_alias="CITATIONS_AUTH_REFRESH_TTL",
    )
    auth_db_path: str = Field(
        default="data/mcp_auth.db",  # SQLite: users + OAuth AS state
        validation_alias="CITATIONS_AUTH_DB_PATH",
    )

    @field_validator("uspto_ecitation_api_key", mode="after")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Validate USPTO API key format."""
        if not v:
            raise ValueError("USPTO API key is required")

        # Use constants for validation (single source of truth)
        if len(v) < MIN_API_KEY_LENGTH or len(v) > MAX_API_KEY_LENGTH:
            raise ValueError(
                f"Invalid USPTO API key length (expected {MIN_API_KEY_LENGTH}-{MAX_API_KEY_LENGTH} characters)"
            )

        return v

    @classmethod
    def load_from_env(cls):
        """Load settings from environment variables or unified secure storage."""
        # Try to get API key from unified secure storage first (Windows only)
        api_key = None
        try:
            from ..shared_secure_storage import get_uspto_api_key

            api_key = get_uspto_api_key()
        except Exception:
            # Secure storage not available or failed - will fall back to env var
            pass

        # If we got a key from secure storage, set it in environment
        # so Pydantic can pick it up
        if api_key:
            os.environ["USPTO_API_KEY"] = api_key

        return cls()


# Global settings instance - lazy loading
settings = None


def get_settings() -> Settings:
    """Get settings instance, creating it if needed."""
    global settings
    if settings is None:
        settings = Settings.load_from_env()
    return settings
