"""
CWE-532: Logging tests — verify sanitization, metrics collector, and no bare getLogger.

This module tests the logging infrastructure added in commit 96a0b0c:
- get_logger() applies SanitizingFilter
- SanitizingFilter correctly redacts sensitive patterns
- LoggingMetricsCollector can be instantiated (regression test for e308c4e)
- No bare logging.getLogger() calls remain in src/ (CWE-532)
"""

import logging
import re
from pathlib import Path

import pytest

from uspto_enriched_citation_mcp.util.logging import (
    SanitizingFilter,
    get_logger,
)
from uspto_enriched_citation_mcp.util.metrics import LoggingMetricsCollector


class TestGetLoggerSanitizingFilter:
    """Tests for get_logger() applying SanitizingFilter."""

    def test_get_logger_returns_sanitizing_filter(self):
        """Verify get_logger() adds SanitizingFilter to logger.filters."""
        logger = get_logger("test")
        filter_classes = [type(f).__name__ for f in logger.filters]
        assert "SanitizingFilter" in filter_classes, (
            f"Expected SanitizingFilter in {filter_classes}"
        )

    def test_get_logger_idempotent(self):
        """Adding filter multiple times shouldn't duplicate it."""
        logger = get_logger("test-idempotent")
        # Count SanitizingFilter instances before
        before = sum(1 for f in logger.filters if isinstance(f, SanitizingFilter))
        get_logger("test-idempotent")  # call again
        after = sum(1 for f in logger.filters if isinstance(f, SanitizingFilter))
        assert before == after, "SanitizingFilter was duplicated on re-call"


class TestSanitizingFilter:
    """Tests for SanitizingFilter.redact() behavior."""

    def test_sanitizing_filter_redacts_api_keys(self):
        """32-char alphanumeric string should be redacted as [KEY_REDACTED]."""
        # 32-char alphanumeric = matches the API key pattern in SENSITIVE_PATTERNS
        api_key = "aBcDeFgHiJkLmNoPqRsTuVwXyZ123456"
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=api_key,
            args=(),
            exc_info=None,
        )
        sf = SanitizingFilter()
        sf.filter(record)
        assert "[KEY_REDACTED]" in record.msg, (
            f"Expected [KEY_REDACTED] in: {record.msg}"
        )
        assert api_key not in record.msg

    def test_sanitizing_filter_redacts_urls(self):
        """URLs should be redacted as [URL_REDACTED]."""
        url = "https://example.com/api?key=secret123"
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=url,
            args=(),
            exc_info=None,
        )
        sf = SanitizingFilter()
        sf.filter(record)
        assert "[URL_REDACTED]" in record.msg
        assert "example.com" not in record.msg

    def test_sanitizing_filter_prevents_log_injection(self):
        """Newlines and control chars should be escaped to prevent log injection."""
        injection = "normal message\nmalicious payload\r\nmore"
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=injection,
            args=(),
            exc_info=None,
        )
        sf = SanitizingFilter()
        sf.filter(record)
        assert "\n" not in record.msg
        assert "\r" not in record.msg
        assert "\\n" in record.msg or "malicious" not in record.msg


class TestLoggingMetricsCollector:
    """Regression test for LoggingMetricsCollector instantiation (e308c4e)."""

    def test_logging_metrics_collector_instantiation(self):
        """LoggingMetricsCollector should instantiate without error."""
        try:
            collector = LoggingMetricsCollector()
            assert collector is not None
        except AttributeError:
            pytest.fail("LoggingMetricsCollector not found — may have been removed in e308c4e")


class TestNoBareLoggingGetLogger:
    """CWE-532: Ensure no bare logging.getLogger() in src/ (except in util/logging.py)."""

    BARE_GETLOGGER_RE = re.compile(r"^\s*logging\.getLogger\s*\(")

    def test_no_bare_logging_getLogger_in_src(self):
        """grep src/ for bare logging.getLogger() — should find zero matches."""
        src_root = (
            Path(__file__).parent.parent / "src" / "uspto_enriched_citation_mcp"
        )
        violations = []
        for py_file in src_root.rglob("*.py"):
            # util/logging.py is the sanctioned source of get_logger
            if py_file.name == "logging.py" and "util" in py_file.parts:
                continue
            try:
                content = py_file.read_text(encoding="utf-8")
            except Exception:
                continue
            for lineno, line in enumerate(content.splitlines(), start=1):
                if self.BARE_GETLOGGER_RE.search(line):
                    violations.append(f"{py_file}:{lineno}: {line.strip()}")

        assert violations == [], (
            "Bare logging.getLogger() found in:\n" + "\n".join(violations)
        )


class TestContentMinimizationHardening:
    """Logging hardening (2026-07): traceback sanitization + token redaction."""

    def test_sanitizing_filter_scrubs_exception_tracebacks(self):
        """Handlers format exc_info AFTER filters run — the filter must
        pre-render and sanitize the traceback (httpx exception reprs embed
        full request URLs)."""
        import io

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.addFilter(SanitizingFilter())
        raw_logger = logging.getLogger("test-exc-hardening")
        raw_logger.setLevel(logging.DEBUG)
        raw_logger.handlers = [handler]
        raw_logger.propagate = False

        secret_url = "https://api.uspto.gov/api/v1/enriched?criteria=secret+client+matter"
        try:
            raise RuntimeError(f"boom {secret_url}")
        except RuntimeError:
            raw_logger.error("operation failed", exc_info=True)
        output = stream.getvalue()

        assert "operation failed" in output
        assert "RuntimeError" in output
        assert "secret+client+matter" not in output
        assert "api.uspto.gov" not in output

    def test_sanitizing_filter_redacts_urlsafe_tokens(self):
        """secrets.token_urlsafe(32)-style values (43 chars) must be redacted."""
        token = "x7Kj-2mQ_9fLp4Rt8vNc1Bw6Ys3Ze5Ah0Dg7Uk2Il_Q"
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=f"presented token: {token}",
            args=(),
            exc_info=None,
        )
        sf = SanitizingFilter()
        sf.filter(record)
        assert token not in record.msg
        assert "[TOKEN_REDACTED]" in record.msg or "[KEY_REDACTED]" in record.msg

    def test_noisy_library_loggers_suppressed(self):
        """setup_logging must cap httpx/httpcore/uvicorn.access at WARNING —
        they log full request URLs / access paths at INFO."""
        from uspto_enriched_citation_mcp.util.logging import setup_logging

        setup_logging()  # idempotent — returns the existing logger
        for noisy in ("httpx", "httpcore", "uvicorn.access"):
            assert logging.getLogger(noisy).level >= logging.WARNING, (
                f"{noisy} logger not suppressed"
            )
