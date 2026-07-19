"""
Logging utilities for USPTO Enriched Citation MCP with security hardening.

Features:
- Sensitive data sanitization (API keys, paths, IPs, passwords)
- Log injection prevention (newlines, control characters)
- Automatic application to all log messages
- File-based logging with rotation and retention
- Secure file permissions
"""

import logging
import os
import re
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Optional, Tuple

# Sensitive patterns to sanitize — single source of truth shared by
# SanitizingFilter (log records) and shared/error_utils.py (error messages).
# ORDER MATTERS: the URL pattern must run before the Unix-path pattern,
# otherwise the path regex consumes "//host/path" first and URLs get
# mislabeled as [PATH_REDACTED].
SENSITIVE_PATTERNS = [
    (r"https?://[^\s]+", "[URL_REDACTED]"),  # URLs (before path patterns)
    (r"[A-Za-z]:\\[^:\s]+", "[PATH_REDACTED]"),  # Windows paths
    (r"/[^\s:]+/[^\s:]+", "[PATH_REDACTED]"),  # Unix paths
    (r"[a-z0-9]{28,40}", "[KEY_REDACTED]"),  # API keys
    (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "[IP_REDACTED]"),  # IP addresses
    (
        r'password["\']?\s*[:=]\s*["\']?[^\s"\']+',
        "password=[REDACTED]",
    ),  # Passwords
    (
        r'api[_-]?key["\']?\s*[:=]\s*["\']?[^\s"\']+',
        "api_key=[REDACTED]",
    ),  # API key assignments
    (
        r"\b(?=[A-Za-z0-9_\-]*[A-Za-z])(?=[A-Za-z0-9_\-]*[0-9])[A-Za-z0-9_\-]{40,}\b",
        "[TOKEN_REDACTED]",
    ),  # Long urlsafe-base64 tokens (secrets.token_urlsafe(32) is 43 chars)
]


def prepare_log_dir(log_dir: Optional[str] = None, label: str = "") -> Tuple[Path, bool]:
    """Resolve and create the log directory (shared with security_logger).

    Resolution order: explicit argument, LOG_DIR env var, /var/log/uspto_mcp
    if /var/log is writable, else ~/.uspto_mcp/logs. Creates the directory
    with secure permissions (0o750).

    Args:
        log_dir: Explicit directory (default: auto-detect)
        label: Prefix for warning messages (e.g. "security ")

    Returns:
        Tuple of (log_path, file_logging_ok) — file_logging_ok is False if
        the directory could not be created.
    """
    if log_dir is None:
        # Check environment variable first
        log_dir = os.getenv("LOG_DIR")

    if log_dir is None:
        # Try /var/log for production, fall back to user directory
        if os.access("/var/log", os.W_OK):
            log_dir = "/var/log/uspto_mcp"
        else:
            log_dir = str(Path.home() / ".uspto_mcp" / "logs")

    log_path = Path(log_dir)
    try:
        log_path.mkdir(parents=True, exist_ok=True)
        # Set secure permissions on log directory (owner rwx, group rx)
        os.chmod(log_path, 0o750)
    except Exception as e:
        # If we can't create the log directory, continue without file logging
        print(f"Warning: Could not create {label}log directory {log_path}: {e}", file=sys.stderr)
        print(f"Continuing with console {label}logging only", file=sys.stderr)
        return log_path, False

    return log_path, True


class SanitizingFilter(logging.Filter):
    """
    Logging filter that sanitizes sensitive data and prevents log injection.

    Removes:
    - API keys (28-40 character alphanumeric strings)
    - File paths (Windows and Unix)
    - IP addresses
    - URLs
    - Passwords
    - Control characters and newlines (log injection)
    """

    SENSITIVE_PATTERNS = SENSITIVE_PATTERNS  # module-level shared constant

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter and sanitize log record.

        Args:
            record: Log record to filter

        Returns:
            True (always allow the record, but sanitized)
        """
        # Sanitize the message
        if hasattr(record, "msg") and record.msg:
            message = str(record.msg)

            # Remove sensitive patterns
            for pattern, replacement in self.SENSITIVE_PATTERNS:
                message = re.sub(pattern, replacement, message, flags=re.IGNORECASE)

            # Prevent log injection by escaping control characters
            message = self._prevent_log_injection(message)

            # Update the record
            record.msg = message

        # Sanitize args if present
        if hasattr(record, "args") and record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: self._sanitize_value(v) for k, v in record.args.items()
                }
            elif isinstance(record.args, (list, tuple)):
                record.args = tuple(self._sanitize_value(arg) for arg in record.args)

        # Handlers format exc_info AFTER filters run, so pre-render and
        # sanitize the traceback here (httpx exception reprs embed full
        # request URLs) and stop the handler re-formatting it.
        if record.exc_info and record.exc_info[0] is not None:
            if not record.exc_text:
                record.exc_text = "".join(
                    traceback.format_exception(*record.exc_info)
                )
            record.exc_info = None
        if record.exc_text:
            record.exc_text = self._sanitize_value(record.exc_text)

        return True

    def _prevent_log_injection(self, message: str) -> str:
        """
        Prevent log injection by escaping newlines and control characters.

        Args:
            message: Message to sanitize

        Returns:
            Sanitized message with escaped control characters
        """
        # Replace newlines with escaped version
        message = message.replace("\n", "\\n").replace("\r", "\\r")

        # Replace other control characters
        message = re.sub(
            r"[\x00-\x1f\x7f]", lambda m: f"\\x{ord(m.group(0)):02x}", message
        )

        return message

    def _sanitize_value(self, value: Any) -> Any:
        """
        Sanitize a single value (for log args).

        Args:
            value: Value to sanitize

        Returns:
            Sanitized value
        """
        if isinstance(value, str):
            for pattern, replacement in self.SENSITIVE_PATTERNS:
                value = re.sub(pattern, replacement, value, flags=re.IGNORECASE)
            value = self._prevent_log_injection(value)
        return value


def setup_logging(
    level: str = "INFO",
    log_dir: Optional[str] = None,
    enable_file_logging: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 10,
) -> logging.Logger:
    """
    Setup logging configuration with security hardening and file rotation.

    Adds:
    - Sensitive data sanitization filter
    - Log injection prevention
    - Structured format
    - File-based logging with rotation
    - Secure file permissions

    Args:
        level: Log level (default: INFO)
        log_dir: Directory for log files (default: auto-detect)
        enable_file_logging: Enable file logging (default: True)
        max_bytes: Max log file size before rotation (default: 10MB)
        backup_count: Number of backup files to keep (default: 10)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("uspto_ecitation")

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    # Determine and create log directory (shared helper with security_logger)
    if enable_file_logging:
        log_path, enable_file_logging = prepare_log_dir(log_dir)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, level.upper()))
    console_handler.addFilter(SanitizingFilter())
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handlers (if enabled)
    if enable_file_logging:
        try:
            # Application log file (INFO and above)
            app_log_file = log_path / "application.log"
            app_handler = RotatingFileHandler(
                app_log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            app_handler.setLevel(logging.INFO)
            app_handler.addFilter(SanitizingFilter())
            app_handler.setFormatter(formatter)
            logger.addHandler(app_handler)

            # Set secure permissions (owner rw, group r)
            os.chmod(app_log_file, 0o640)

            # Error log file (WARNING and above)
            error_log_file = log_path / "error.log"
            error_handler = RotatingFileHandler(
                error_log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            error_handler.setLevel(logging.WARNING)
            error_handler.addFilter(SanitizingFilter())
            error_handler.setFormatter(formatter)
            logger.addHandler(error_handler)

            # Set secure permissions (owner rw, group r)
            os.chmod(error_log_file, 0o640)

            logger.info(f"File logging enabled: {log_path}")
            logger.info(f"Log rotation: {max_bytes:,} bytes, {backup_count} backups")

        except Exception as e:
            logger.warning(f"Failed to setup file logging: {e}")
            logger.warning("Continuing with console logging only")

    logger.setLevel(getattr(logging, level.upper()))

    # Suppress noisy libraries — httpx/httpcore log full request URLs at
    # INFO, and uvicorn access lines include request paths and client IPs
    for noisy in ("httpx", "httpcore", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get logger instance with sanitization filter.

    Args:
        name: Logger name (default: main logger)

    Returns:
        Logger instance with sanitizing filter applied
    """
    if name:
        logger = logging.getLogger(f"uspto_ecitation.{name}")
    else:
        logger = logging.getLogger("uspto_ecitation")

    # Ensure sanitizing filter is applied
    if not any(isinstance(f, SanitizingFilter) for f in logger.filters):
        logger.addFilter(SanitizingFilter())

    return logger
