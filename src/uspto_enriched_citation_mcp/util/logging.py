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
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Optional


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

    # Sensitive patterns to sanitize (same as error_utils)
    SENSITIVE_PATTERNS = [
        (r"[A-Za-z]:\\[^:\s]+", "[PATH_REDACTED]"),  # Windows paths
        (r"/[^\s:]+/[^\s:]+", "[PATH_REDACTED]"),  # Unix paths
        (r"[a-z0-9]{28,40}", "[KEY_REDACTED]"),  # API keys
        (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "[IP_REDACTED]"),  # IP addresses
        (r"https?://[^\s]+", "[URL_REDACTED]"),  # URLs
        (
            r'password["\']?\s*[:=]\s*["\']?[^\s"\']+',
            "password=[REDACTED]",
        ),  # Passwords
        (
            r'api[_-]?key["\']?\s*[:=]\s*["\']?[^\s"\']+',
            "api_key=[REDACTED]",
        ),  # API key assignments
    ]

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
    if enable_file_logging:
        try:
            log_path.mkdir(parents=True, exist_ok=True)
            # Set secure permissions on log directory (owner rwx, group rx)
            os.chmod(log_path, 0o750)
        except Exception as e:
            # If we can't create log directory, continue without file logging
            enable_file_logging = False
            print(f"Warning: Could not create log directory {log_path}: {e}", file=__import__("sys").stderr)
            print("Continuing with console logging only", file=__import__("sys").stderr)

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
