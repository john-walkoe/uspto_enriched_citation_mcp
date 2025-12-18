"""
Security event logging with structured fields for audit trails and attack detection.

Provides dedicated security logging separate from application logs for:
- Authentication events
- Query validation failures
- Rate limiting
- Suspicious patterns
- API access patterns
"""

import logging
import json
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional
from enum import Enum


class SecurityEventType(Enum):
    """Security event types for categorization."""

    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    QUERY_VALIDATION_FAILURE = "query_validation_failure"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_PATTERN = "suspicious_pattern"
    API_ACCESS = "api_access"
    API_ERROR = "api_error"
    INJECTION_ATTEMPT = "injection_attempt"
    EXCESSIVE_WILDCARDS = "excessive_wildcards"
    INVALID_FIELD_ACCESS = "invalid_field_access"


class SecurityLogger:
    """
    Dedicated security event logger with structured fields.

    Logs security events separately from application logs for:
    - Audit compliance
    - Attack detection
    - Incident response
    - Forensic analysis
    """

    def __init__(self, name: str = "security", log_dir: Optional[str] = None):
        """
        Initialize security logger with file rotation.

        Args:
            name: Logger name (default: "security")
            log_dir: Directory for log files (default: auto-detect)
        """
        self.logger = logging.getLogger(f"uspto_ecitation.{name}")
        self.logger.setLevel(logging.INFO)

        # Prevent duplicate handlers
        if self.logger.handlers:
            return

        # Determine log directory
        if log_dir is None:
            # Check environment variable first
            log_dir = os.getenv("LOG_DIR")

        if log_dir is None:
            # Try /var/log for production, fall back to user directory
            if os.access("/var/log", os.W_OK):
                log_dir = "/var/log/uspto_mcp"
            else:
                log_dir = str(Path.home() / ".uspto_mcp" / "logs")

        # Convert to Path and create directory
        log_path = Path(log_dir)
        enable_file_logging = True
        try:
            log_path.mkdir(parents=True, exist_ok=True)
            # Set secure permissions on log directory (owner rwx, group rx)
            os.chmod(log_path, 0o750)
        except Exception as e:
            # If we can't create log directory, continue without file logging
            enable_file_logging = False
            print(f"Warning: Could not create security log directory {log_path}: {e}", file=__import__("sys").stderr)
            print("Continuing with console security logging only", file=__import__("sys").stderr)

        # Structured JSON format for security events
        formatter = logging.Formatter(
            "%(asctime)s - SECURITY - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Console handler for security events
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # Security event file (separate from application logs)
        if enable_file_logging:
            try:
                security_log_file = log_path / "security.log"
                security_handler = RotatingFileHandler(
                    security_log_file,
                    maxBytes=10 * 1024 * 1024,  # 10MB
                    backupCount=90,  # 90 days retention (approx 1 day per file)
                    encoding="utf-8",
                )
                security_handler.setLevel(logging.INFO)
                security_handler.setFormatter(formatter)
                self.logger.addHandler(security_handler)

                # Secure permissions (owner read/write only for security events)
                os.chmod(security_log_file, 0o600)

                self.logger.info(f"Security logging enabled: {security_log_file}")
                self.logger.info(f"Security log retention: 90 backup files (approx 90 days)")

            except Exception as e:
                self.logger.warning(f"Failed to setup security file logging: {e}")
                self.logger.warning("Continuing with console security logging only")

    def _log_event(
        self,
        event_type: SecurityEventType,
        message: str,
        level: int = logging.WARNING,
        **kwargs,
    ) -> None:
        """
        Log security event with structured fields.

        Automatically includes request ID if available for correlation.

        Args:
            event_type: Type of security event
            message: Human-readable event description
            level: Logging level (default: WARNING)
            **kwargs: Additional structured fields
        """
        event_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type.value,
            "message": message,
            **kwargs,
        }

        # Add request ID if available (for correlation)
        try:
            from .request_context import get_request_id, get_request_duration_ms

            request_id = get_request_id()
            if request_id:
                event_data["request_id"] = request_id
                duration_ms = get_request_duration_ms()
                if duration_ms is not None:
                    event_data["duration_ms"] = duration_ms
        except (ImportError, Exception):
            pass  # Request context not available

        # Log as structured JSON for parsing
        self.logger.log(level, json.dumps(event_data))

    def auth_success(self, method: str = "api_key", **kwargs) -> None:
        """Log successful authentication."""
        self._log_event(
            SecurityEventType.AUTH_SUCCESS,
            f"Authentication successful: {method}",
            level=logging.INFO,
            auth_method=method,
            **kwargs,
        )

    def auth_failure(
        self, method: str = "api_key", reason: str = "Invalid credentials", **kwargs
    ) -> None:
        """Log authentication failure."""
        self._log_event(
            SecurityEventType.AUTH_FAILURE,
            f"Authentication failed: {reason}",
            level=logging.WARNING,
            auth_method=method,
            reason=reason,
            **kwargs,
        )

    def query_validation_failure(
        self, query: str, reason: str, severity: str = "medium", **kwargs
    ) -> None:
        """
        Log query validation failure.

        Args:
            query: The query that failed validation (sanitized)
            reason: Why validation failed
            severity: Severity level (low, medium, high, critical)
            **kwargs: Additional context
        """
        # Sanitize query before logging (truncate if too long)
        sanitized_query = query[:200] if len(query) > 200 else query

        self._log_event(
            SecurityEventType.QUERY_VALIDATION_FAILURE,
            f"Query validation failed: {reason}",
            level=logging.WARNING if severity in ["low", "medium"] else logging.ERROR,
            query_preview=sanitized_query,
            reason=reason,
            severity=severity,
            **kwargs,
        )

    def rate_limit_exceeded(
        self, limit: int, window: str = "1m", endpoint: Optional[str] = None, **kwargs
    ) -> None:
        """
        Log rate limit exceeded event.

        Args:
            limit: Rate limit threshold
            window: Time window (e.g., "1m", "1h")
            endpoint: API endpoint affected
            **kwargs: Additional context
        """
        self._log_event(
            SecurityEventType.RATE_LIMIT_EXCEEDED,
            f"Rate limit exceeded: {limit} requests per {window}",
            level=logging.WARNING,
            limit=limit,
            window=window,
            endpoint=endpoint,
            **kwargs,
        )

    def suspicious_pattern(
        self, pattern_type: str, description: str, severity: str = "medium", **kwargs
    ) -> None:
        """
        Log suspicious pattern detection.

        Args:
            pattern_type: Type of suspicious pattern
            description: Description of the pattern
            severity: Severity level
            **kwargs: Additional context
        """
        self._log_event(
            SecurityEventType.SUSPICIOUS_PATTERN,
            f"Suspicious pattern detected: {pattern_type}",
            level=logging.WARNING if severity in ["low", "medium"] else logging.ERROR,
            pattern_type=pattern_type,
            description=description,
            severity=severity,
            **kwargs,
        )

    def api_access(
        self,
        endpoint: str,
        status_code: int,
        response_time_ms: Optional[float] = None,
        **kwargs,
    ) -> None:
        """
        Log API access for audit trail.

        Args:
            endpoint: API endpoint accessed
            status_code: HTTP status code
            response_time_ms: Response time in milliseconds
            **kwargs: Additional context
        """
        self._log_event(
            SecurityEventType.API_ACCESS,
            f"API access: {endpoint} - {status_code}",
            level=logging.INFO,
            endpoint=endpoint,
            status_code=status_code,
            response_time_ms=response_time_ms,
            **kwargs,
        )

    def api_error(
        self, endpoint: str, error_code: int, error_type: str, **kwargs
    ) -> None:
        """
        Log API error for monitoring.

        Args:
            endpoint: API endpoint
            error_code: HTTP error code
            error_type: Type of error
            **kwargs: Additional context
        """
        self._log_event(
            SecurityEventType.API_ERROR,
            f"API error: {endpoint} - {error_code} ({error_type})",
            level=logging.ERROR,
            endpoint=endpoint,
            error_code=error_code,
            error_type=error_type,
            **kwargs,
        )

    def injection_attempt(
        self, injection_type: str, input_field: str, pattern_detected: str, **kwargs
    ) -> None:
        """
        Log injection attempt.

        Args:
            injection_type: Type of injection (SQL, NoSQL, command, etc.)
            input_field: Field where injection was detected
            pattern_detected: Pattern that triggered detection
            **kwargs: Additional context
        """
        self._log_event(
            SecurityEventType.INJECTION_ATTEMPT,
            f"Injection attempt detected: {injection_type} in {input_field}",
            level=logging.ERROR,
            injection_type=injection_type,
            input_field=input_field,
            pattern_detected=pattern_detected,
            **kwargs,
        )

    def excessive_wildcards(
        self, query: str, wildcard_count: int, max_allowed: int = 10, **kwargs
    ) -> None:
        """
        Log excessive wildcard usage (DoS indicator).

        Args:
            query: Query with excessive wildcards (sanitized)
            wildcard_count: Number of wildcards detected
            max_allowed: Maximum allowed wildcards
            **kwargs: Additional context
        """
        sanitized_query = query[:200] if len(query) > 200 else query

        self._log_event(
            SecurityEventType.EXCESSIVE_WILDCARDS,
            f"Excessive wildcards detected: {wildcard_count} (max: {max_allowed})",
            level=logging.WARNING,
            query_preview=sanitized_query,
            wildcard_count=wildcard_count,
            max_allowed=max_allowed,
            **kwargs,
        )

    def invalid_field_access(
        self, field_name: str, attempted_operation: str = "query", **kwargs
    ) -> None:
        """
        Log attempt to access invalid field.

        Args:
            field_name: Invalid field name
            attempted_operation: Operation attempted
            **kwargs: Additional context
        """
        self._log_event(
            SecurityEventType.INVALID_FIELD_ACCESS,
            f"Invalid field access attempt: {field_name}",
            level=logging.WARNING,
            field_name=field_name,
            attempted_operation=attempted_operation,
            **kwargs,
        )


# Global security logger instance
_security_logger: Optional[SecurityLogger] = None


def get_security_logger() -> SecurityLogger:
    """
    Get global security logger instance (singleton).

    Returns:
        SecurityLogger instance
    """
    global _security_logger
    if _security_logger is None:
        _security_logger = SecurityLogger()
    return _security_logger
