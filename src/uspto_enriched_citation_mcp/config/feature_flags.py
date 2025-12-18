"""Feature flags for runtime feature toggling.

Provides a flexible system for enabling/disabling features without code changes.
Supports environment variables, configuration files, and programmatic overrides.
"""

import os
import logging
from typing import Dict, Optional, Any
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class FeatureFlag(str, Enum):
    """
    Available feature flags.

    Each flag can be toggled independently for gradual rollout, A/B testing,
    or emergency feature disabling.
    """

    # Caching Features
    ENABLE_FIELDS_CACHE = "enable_fields_cache"
    ENABLE_SEARCH_CACHE = "enable_search_cache"

    # Security Features
    ENABLE_RATE_LIMITING = "enable_rate_limiting"
    ENABLE_CIRCUIT_BREAKER = "enable_circuit_breaker"
    ENABLE_REQUEST_VALIDATION = "enable_request_validation"
    ENABLE_RESPONSE_VALIDATION = "enable_response_validation"

    # Monitoring Features
    ENABLE_METRICS = "enable_metrics"
    ENABLE_SECURITY_LOGGING = "enable_security_logging"
    ENABLE_DETAILED_LOGGING = "enable_detailed_logging"

    # Retry & Resilience
    ENABLE_RETRY_LOGIC = "enable_retry_logic"
    ENABLE_EXPONENTIAL_BACKOFF = "enable_exponential_backoff"

    # Experimental Features
    ENABLE_EXPERIMENTAL_FEATURES = "enable_experimental_features"
    ENABLE_BETA_FEATURES = "enable_beta_features"

    # Performance Optimizations
    ENABLE_CONNECTION_POOLING = "enable_connection_pooling"
    ENABLE_REQUEST_BATCHING = "enable_request_batching"

    # Development/Debug
    ENABLE_DEBUG_MODE = "enable_debug_mode"
    ENABLE_VERBOSE_ERRORS = "enable_verbose_errors"


class FeatureFlags:
    """
    Feature flags manager with environment variable and file-based configuration.

    Supports:
    - Environment variables (highest priority)
    - Configuration file
    - Programmatic overrides
    - Default values
    """

    def __init__(self, config_file: Optional[Path] = None):
        """
        Initialize feature flags manager.

        Args:
            config_file: Optional path to feature flags configuration file
        """
        self._flags: Dict[str, bool] = {}
        self._defaults: Dict[str, bool] = self._get_default_flags()
        self._config_file = config_file

        # Load flags from various sources (precedence: env vars > config file > defaults)
        self._load_defaults()
        if config_file:
            self._load_from_file(config_file)
        self._load_from_env()

        logger.info(
            f"Feature flags initialized: {sum(self._flags.values())}/{len(self._flags)} enabled"
        )

    def _get_default_flags(self) -> Dict[str, bool]:
        """
        Get default flag values.

        Returns:
            Dict mapping flag names to default values
        """
        return {
            # Caching: Enabled by default (performance benefit)
            FeatureFlag.ENABLE_FIELDS_CACHE: True,
            FeatureFlag.ENABLE_SEARCH_CACHE: True,
            # Security: All enabled by default (safety first)
            FeatureFlag.ENABLE_RATE_LIMITING: True,
            FeatureFlag.ENABLE_CIRCUIT_BREAKER: True,
            FeatureFlag.ENABLE_REQUEST_VALIDATION: True,
            FeatureFlag.ENABLE_RESPONSE_VALIDATION: True,
            # Monitoring: Enabled by default (observability)
            FeatureFlag.ENABLE_METRICS: True,
            FeatureFlag.ENABLE_SECURITY_LOGGING: True,
            FeatureFlag.ENABLE_DETAILED_LOGGING: False,  # Disabled (verbose)
            # Retry & Resilience: Enabled by default (reliability)
            FeatureFlag.ENABLE_RETRY_LOGIC: True,
            FeatureFlag.ENABLE_EXPONENTIAL_BACKOFF: True,
            # Experimental: Disabled by default (stability)
            FeatureFlag.ENABLE_EXPERIMENTAL_FEATURES: False,
            FeatureFlag.ENABLE_BETA_FEATURES: False,
            # Performance: Selective defaults
            FeatureFlag.ENABLE_CONNECTION_POOLING: True,
            FeatureFlag.ENABLE_REQUEST_BATCHING: False,  # Not implemented yet
            # Development/Debug: Disabled by default (production-safe)
            FeatureFlag.ENABLE_DEBUG_MODE: False,
            FeatureFlag.ENABLE_VERBOSE_ERRORS: False,
        }

    def _load_defaults(self) -> None:
        """Load default flag values."""
        self._flags = self._defaults.copy()

    def _load_from_file(self, config_file: Path) -> None:
        """
        Load flags from configuration file.

        Args:
            config_file: Path to configuration file (JSON or simple key=value format)
        """
        if not config_file.exists():
            logger.debug(f"Feature flags config file not found: {config_file}")
            return

        try:
            with open(config_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    if "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().lower()

                        # Parse boolean value
                        bool_value = value in ("true", "1", "yes", "on", "enabled")

                        if key in [flag.value for flag in FeatureFlag]:
                            self._flags[key] = bool_value
                            logger.debug(f"Loaded flag from file: {key}={bool_value}")

            logger.info(f"Loaded feature flags from: {config_file}")

        except Exception as e:
            logger.warning(f"Failed to load feature flags from file: {e}")

    def _load_from_env(self) -> None:
        """Load flags from environment variables."""
        prefix = "FEATURE_FLAG_"

        for flag in FeatureFlag:
            env_var = f"{prefix}{flag.value.upper()}"
            env_value = os.getenv(env_var)

            if env_value is not None:
                bool_value = env_value.lower() in ("true", "1", "yes", "on", "enabled")
                self._flags[flag.value] = bool_value
                logger.debug(
                    f"Loaded flag from env: {flag.value}={bool_value} ({env_var})"
                )

    def is_enabled(self, flag: FeatureFlag) -> bool:
        """
        Check if feature flag is enabled.

        Args:
            flag: Feature flag to check

        Returns:
            True if enabled, False otherwise
        """
        return self._flags.get(flag.value, False)

    def is_disabled(self, flag: FeatureFlag) -> bool:
        """
        Check if feature flag is disabled.

        Args:
            flag: Feature flag to check

        Returns:
            True if disabled, False otherwise
        """
        return not self.is_enabled(flag)

    def enable(self, flag: FeatureFlag) -> None:
        """
        Enable a feature flag programmatically.

        Args:
            flag: Feature flag to enable
        """
        old_value = self._flags.get(flag.value, False)
        self._flags[flag.value] = True
        logger.info(f"Feature flag enabled: {flag.value} (was: {old_value})")

    def disable(self, flag: FeatureFlag) -> None:
        """
        Disable a feature flag programmatically.

        Args:
            flag: Feature flag to disable
        """
        old_value = self._flags.get(flag.value, True)
        self._flags[flag.value] = False
        logger.info(f"Feature flag disabled: {flag.value} (was: {old_value})")

    def set(self, flag: FeatureFlag, enabled: bool) -> None:
        """
        Set feature flag value programmatically.

        Args:
            flag: Feature flag to set
            enabled: True to enable, False to disable
        """
        if enabled:
            self.enable(flag)
        else:
            self.disable(flag)

    def get_all_flags(self) -> Dict[str, bool]:
        """
        Get all feature flags and their current values.

        Returns:
            Dict mapping flag names to boolean values
        """
        return self._flags.copy()

    def get_enabled_flags(self) -> list[str]:
        """
        Get list of enabled feature flags.

        Returns:
            List of enabled flag names
        """
        return [flag for flag, enabled in self._flags.items() if enabled]

    def get_disabled_flags(self) -> list[str]:
        """
        Get list of disabled feature flags.

        Returns:
            List of disabled flag names
        """
        return [flag for flag, enabled in self._flags.items() if not enabled]

    def reset_to_defaults(self) -> None:
        """Reset all flags to their default values."""
        self._flags = self._defaults.copy()
        logger.info("Feature flags reset to defaults")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get feature flag statistics.

        Returns:
            Dict with stats about feature flags
        """
        enabled_count = sum(1 for v in self._flags.values() if v)
        total_count = len(self._flags)

        return {
            "total_flags": total_count,
            "enabled_count": enabled_count,
            "disabled_count": total_count - enabled_count,
            "enabled_percentage": (
                round(enabled_count / total_count * 100, 2) if total_count > 0 else 0.0
            ),
            "flags": self._flags.copy(),
        }


# Global feature flags instance
_feature_flags: Optional[FeatureFlags] = None


def get_feature_flags(config_file: Optional[Path] = None) -> FeatureFlags:
    """
    Get or create the global feature flags instance.

    Args:
        config_file: Optional path to configuration file (only used on first call)

    Returns:
        FeatureFlags instance
    """
    global _feature_flags
    if _feature_flags is None:
        _feature_flags = FeatureFlags(config_file=config_file)
    return _feature_flags


def is_feature_enabled(flag: FeatureFlag) -> bool:
    """
    Check if a feature flag is enabled (convenience function).

    Args:
        flag: Feature flag to check

    Returns:
        True if enabled, False otherwise
    """
    flags = get_feature_flags()
    return flags.is_enabled(flag)


def require_feature(flag: FeatureFlag):
    """
    Decorator to require a feature flag to be enabled.

    Usage:
        @require_feature(FeatureFlag.ENABLE_BETA_FEATURES)
        def my_beta_function():
            pass
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            if not is_feature_enabled(flag):
                raise RuntimeError(f"Feature '{flag.value}' is disabled")
            return func(*args, **kwargs)

        return wrapper

    return decorator
