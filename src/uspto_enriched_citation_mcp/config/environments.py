"""Environment-based configuration profiles.

Provides pre-configured settings for different deployment environments:
- Development: Verbose logging, relaxed limits, all features enabled
- Staging: Production-like with additional monitoring
- Production: Optimized for performance and stability
"""

import os
import logging
from typing import Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class Environment(str, Enum):
    """Deployment environment types."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


@dataclass
class EnvironmentConfig:
    """Configuration profile for a specific environment."""

    # Environment metadata
    name: str
    description: str

    # Logging
    log_level: str = "INFO"
    enable_detailed_logging: bool = False
    enable_debug_mode: bool = False

    # Caching
    enable_cache: bool = True
    fields_cache_ttl: int = 3600
    search_cache_size: int = 100

    # Rate Limiting
    request_rate_limit: int = 100
    enable_rate_limiting: bool = True

    # Timeouts (seconds)
    api_timeout: float = 30.0
    connect_timeout: float = 10.0

    # Retry & Resilience
    enable_retry_logic: bool = True
    enable_circuit_breaker: bool = True
    enable_exponential_backoff: bool = True

    # Security
    enable_request_validation: bool = True
    enable_response_validation: bool = True
    enable_security_logging: bool = True

    # Monitoring
    enable_metrics: bool = True
    enable_verbose_errors: bool = False

    # Performance
    enable_connection_pooling: bool = True

    # Context Limits
    max_minimal_results: int = 100
    max_balanced_results: int = 20

    # Additional environment-specific settings
    extra_settings: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary format.

        Returns:
            Dict with all configuration values
        """
        config_dict = {
            "name": self.name,
            "description": self.description,
            "log_level": self.log_level,
            "enable_detailed_logging": self.enable_detailed_logging,
            "enable_debug_mode": self.enable_debug_mode,
            "enable_cache": self.enable_cache,
            "fields_cache_ttl": self.fields_cache_ttl,
            "search_cache_size": self.search_cache_size,
            "request_rate_limit": self.request_rate_limit,
            "enable_rate_limiting": self.enable_rate_limiting,
            "api_timeout": self.api_timeout,
            "connect_timeout": self.connect_timeout,
            "enable_retry_logic": self.enable_retry_logic,
            "enable_circuit_breaker": self.enable_circuit_breaker,
            "enable_exponential_backoff": self.enable_exponential_backoff,
            "enable_request_validation": self.enable_request_validation,
            "enable_response_validation": self.enable_response_validation,
            "enable_security_logging": self.enable_security_logging,
            "enable_metrics": self.enable_metrics,
            "enable_verbose_errors": self.enable_verbose_errors,
            "enable_connection_pooling": self.enable_connection_pooling,
            "max_minimal_results": self.max_minimal_results,
            "max_balanced_results": self.max_balanced_results,
        }
        config_dict.update(self.extra_settings)
        return config_dict


# Predefined environment configurations
DEVELOPMENT_CONFIG = EnvironmentConfig(
    name="development",
    description="Development environment with verbose logging and relaxed limits",
    log_level="DEBUG",
    enable_detailed_logging=True,
    enable_debug_mode=True,
    enable_cache=True,
    fields_cache_ttl=60,  # 1 minute (faster refresh for development)
    search_cache_size=50,  # Smaller cache
    request_rate_limit=200,  # Higher limit for development
    enable_rate_limiting=False,  # Disabled for easier testing
    api_timeout=60.0,  # Longer timeout for debugging
    connect_timeout=30.0,
    enable_retry_logic=True,
    enable_circuit_breaker=False,  # Disabled for easier debugging
    enable_exponential_backoff=True,
    enable_request_validation=True,
    enable_response_validation=True,
    enable_security_logging=True,
    enable_metrics=True,
    enable_verbose_errors=True,  # Show full error details
    enable_connection_pooling=True,
    max_minimal_results=200,  # Higher limits for testing
    max_balanced_results=50,
    extra_settings={
        "enable_experimental_features": True,
        "enable_beta_features": True,
    },
)

STAGING_CONFIG = EnvironmentConfig(
    name="staging",
    description="Staging environment with production-like settings and additional monitoring",
    log_level="INFO",
    enable_detailed_logging=True,  # Keep detailed logs for debugging
    enable_debug_mode=False,
    enable_cache=True,
    fields_cache_ttl=1800,  # 30 minutes
    search_cache_size=100,
    request_rate_limit=100,
    enable_rate_limiting=True,
    api_timeout=30.0,
    connect_timeout=10.0,
    enable_retry_logic=True,
    enable_circuit_breaker=True,
    enable_exponential_backoff=True,
    enable_request_validation=True,
    enable_response_validation=True,
    enable_security_logging=True,
    enable_metrics=True,
    enable_verbose_errors=True,  # Show errors in staging
    enable_connection_pooling=True,
    max_minimal_results=100,
    max_balanced_results=20,
    extra_settings={
        "enable_experimental_features": False,
        "enable_beta_features": True,  # Test beta features in staging
    },
)

PRODUCTION_CONFIG = EnvironmentConfig(
    name="production",
    description="Production environment optimized for performance and stability",
    log_level="INFO",
    enable_detailed_logging=False,  # Minimal logging overhead
    enable_debug_mode=False,
    enable_cache=True,
    fields_cache_ttl=3600,  # 1 hour
    search_cache_size=100,
    request_rate_limit=100,
    enable_rate_limiting=True,
    api_timeout=30.0,
    connect_timeout=10.0,
    enable_retry_logic=True,
    enable_circuit_breaker=True,
    enable_exponential_backoff=True,
    enable_request_validation=True,
    enable_response_validation=True,
    enable_security_logging=True,
    enable_metrics=True,
    enable_verbose_errors=False,  # Hide internal errors from users
    enable_connection_pooling=True,
    max_minimal_results=100,
    max_balanced_results=20,
    extra_settings={
        "enable_experimental_features": False,
        "enable_beta_features": False,
    },
)

TESTING_CONFIG = EnvironmentConfig(
    name="testing",
    description="Testing environment for automated test suites",
    log_level="WARNING",  # Reduce noise in tests
    enable_detailed_logging=False,
    enable_debug_mode=False,
    enable_cache=False,  # Disable caching for deterministic tests
    fields_cache_ttl=0,
    search_cache_size=0,
    request_rate_limit=1000,  # Very high limit for tests
    enable_rate_limiting=False,  # Disabled for tests
    api_timeout=5.0,  # Short timeout (tests should be fast)
    connect_timeout=2.0,
    enable_retry_logic=False,  # Disabled for predictable test behavior
    enable_circuit_breaker=False,  # Disabled for tests
    enable_exponential_backoff=False,
    enable_request_validation=True,
    enable_response_validation=True,
    enable_security_logging=False,  # Reduce test noise
    enable_metrics=False,  # Disabled for tests
    enable_verbose_errors=True,  # Show full errors in test failures
    enable_connection_pooling=False,  # Simplify test setup
    max_minimal_results=50,
    max_balanced_results=10,
    extra_settings={
        "enable_experimental_features": False,
        "enable_beta_features": False,
    },
)


# Environment registry
ENVIRONMENTS: Dict[str, EnvironmentConfig] = {
    Environment.DEVELOPMENT: DEVELOPMENT_CONFIG,
    Environment.STAGING: STAGING_CONFIG,
    Environment.PRODUCTION: PRODUCTION_CONFIG,
    Environment.TESTING: TESTING_CONFIG,
}


def get_environment() -> Environment:
    """
    Detect current environment from environment variable.

    Returns:
        Current environment (defaults to PRODUCTION if not set)
    """
    env_name = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "production")).lower()

    # Map common variations
    env_mapping = {
        "dev": Environment.DEVELOPMENT,
        "develop": Environment.DEVELOPMENT,
        "development": Environment.DEVELOPMENT,
        "stage": Environment.STAGING,
        "staging": Environment.STAGING,
        "prod": Environment.PRODUCTION,
        "production": Environment.PRODUCTION,
        "test": Environment.TESTING,
        "testing": Environment.TESTING,
    }

    detected_env = env_mapping.get(env_name, Environment.PRODUCTION)
    logger.info(
        f"Detected environment: {detected_env.value} (from env var: {env_name})"
    )

    return detected_env


def get_environment_config(env: Optional[Environment] = None) -> EnvironmentConfig:
    """
    Get configuration for specified environment.

    Args:
        env: Environment to get config for (auto-detects if None)

    Returns:
        EnvironmentConfig for the specified environment
    """
    if env is None:
        env = get_environment()

    config = ENVIRONMENTS.get(env)
    if config is None:
        logger.warning(f"Unknown environment: {env}, using production config")
        config = PRODUCTION_CONFIG

    return config


def apply_environment_config(env: Optional[Environment] = None) -> Dict[str, Any]:
    """
    Apply environment configuration and return as dictionary.

    This can be used to update settings based on the detected environment.

    Args:
        env: Environment to apply (auto-detects if None)

    Returns:
        Dict with environment configuration
    """
    config = get_environment_config(env)
    logger.info(f"Applying configuration for environment: {config.name}")
    logger.debug(f"Configuration: {config.description}")

    return config.to_dict()


def get_all_environments() -> Dict[str, EnvironmentConfig]:
    """
    Get all available environment configurations.

    Returns:
        Dict mapping environment names to configs
    """
    return ENVIRONMENTS.copy()
