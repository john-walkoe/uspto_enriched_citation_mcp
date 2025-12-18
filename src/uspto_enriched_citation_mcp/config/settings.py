"""Settings management for USPTO Enriched Citation MCP."""

import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator

# Import configuration defaults (single source of truth)
from .constants import (
    DEFAULT_BASE_URL,
    DEFAULT_MCP_SERVER_PORT,
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

    # Feature Flags
    feature_flags_path: Optional[str] = Field(
        default=None,
        validation_alias="FEATURE_FLAGS_PATH"
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
