"""Metrics collection interface for monitoring and observability.

Provides pluggable hooks for collecting operational metrics such as:
- Request counts and rates
- Response times and latencies
- Error rates and types
- Circuit breaker state changes
- Rate limit events
- Response sizes
"""

import time
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict
from enum import Enum

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics that can be collected."""

    COUNTER = "counter"  # Incrementing count (e.g., request count)
    GAUGE = "gauge"  # Point-in-time value (e.g., active connections)
    HISTOGRAM = "histogram"  # Distribution of values (e.g., response times)
    TIMER = "timer"  # Duration measurements


class MetricsCollector(ABC):
    """
    Abstract base class for metrics collection.

    Implement this interface to integrate with monitoring systems like:
    - Prometheus
    - StatsD
    - DataDog
    - CloudWatch
    - OpenTelemetry
    """

    @abstractmethod
    def record_request(
        self,
        endpoint: str,
        method: str,
        status_code: Optional[int] = None,
        duration_seconds: Optional[float] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Record API request metrics.

        Args:
            endpoint: API endpoint name (e.g., 'get_fields', 'search_records')
            method: HTTP method (GET, POST, etc.)
            status_code: HTTP status code (200, 404, etc.)
            duration_seconds: Request duration in seconds
            error: Error type if request failed
        """
        pass

    @abstractmethod
    def record_rate_limit_event(
        self, endpoint: str, tokens_requested: int, tokens_available: int, blocked: bool
    ) -> None:
        """
        Record rate limiting event.

        Args:
            endpoint: API endpoint being rate limited
            tokens_requested: Number of tokens requested
            tokens_available: Number of tokens available
            blocked: Whether request was blocked
        """
        pass

    @abstractmethod
    def record_circuit_breaker_event(
        self, service: str, event_type: str, state: str
    ) -> None:
        """
        Record circuit breaker state change.

        Args:
            service: Service name (e.g., 'uspto_api')
            event_type: Event type ('opened', 'closed', 'half_open', 'failure', 'success')
            state: Current circuit breaker state
        """
        pass

    @abstractmethod
    def record_response_size(self, endpoint: str, size_bytes: int) -> None:
        """
        Record response size metrics.

        Args:
            endpoint: API endpoint
            size_bytes: Response size in bytes
        """
        pass

    @abstractmethod
    def increment_counter(
        self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Increment a counter metric.

        Args:
            name: Counter name
            value: Amount to increment (default 1)
            tags: Optional tags/labels
        """
        pass

    @abstractmethod
    def record_gauge(
        self, name: str, value: float, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Record a gauge metric.

        Args:
            name: Gauge name
            value: Current value
            tags: Optional tags/labels
        """
        pass

    @abstractmethod
    def record_histogram(
        self, name: str, value: float, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Record a histogram value.

        Args:
            name: Histogram name
            value: Value to record
            tags: Optional tags/labels
        """
        pass


class NoOpMetricsCollector(MetricsCollector):
    """
    No-op implementation that does nothing.

    Used as default when no metrics collection is configured.
    """

    def record_request(
        self,
        endpoint: str,
        method: str,
        status_code: Optional[int] = None,
        duration_seconds: Optional[float] = None,
        error: Optional[str] = None,
    ) -> None:
        """No-op implementation."""
        pass

    def record_rate_limit_event(
        self, endpoint: str, tokens_requested: int, tokens_available: int, blocked: bool
    ) -> None:
        """No-op implementation."""
        pass

    def record_circuit_breaker_event(
        self, service: str, event_type: str, state: str
    ) -> None:
        """No-op implementation."""
        pass

    def record_response_size(self, endpoint: str, size_bytes: int) -> None:
        """No-op implementation."""
        pass

    def increment_counter(
        self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """No-op implementation."""
        pass

    def record_gauge(
        self, name: str, value: float, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """No-op implementation."""
        pass

    def record_histogram(
        self, name: str, value: float, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """No-op implementation."""
        pass


class LoggingMetricsCollector(MetricsCollector):
    """
    Simple metrics collector that logs metrics to standard logging.

    Useful for development and debugging. For production, implement
    a custom collector that integrates with your monitoring system.
    """

    def __init__(self, log_level: int = logging.INFO):
        self.log_level = log_level

    def record_request(
        self,
        endpoint: str,
        method: str,
        status_code: Optional[int] = None,
        duration_seconds: Optional[float] = None,
        error: Optional[str] = None,
    ) -> None:
        """Log request metrics."""
        if error:
            logger.log(
                self.log_level,
                f"API Request Failed: {method} {endpoint} - Error: {error}, Duration: {duration_seconds:.3f}s",
            )
        else:
            logger.log(
                self.log_level,
                f"API Request: {method} {endpoint} - Status: {status_code}, Duration: {duration_seconds:.3f}s",
            )

    def record_rate_limit_event(
        self, endpoint: str, tokens_requested: int, tokens_available: int, blocked: bool
    ) -> None:
        """Log rate limit event."""
        if blocked:
            logger.log(
                self.log_level,
                f"Rate Limit Exceeded: {endpoint} - Requested: {tokens_requested}, Available: {tokens_available}",
            )
        else:
            logger.debug(
                f"Rate Limit: {endpoint} - Tokens: {tokens_available} remaining"
            )

    def record_circuit_breaker_event(
        self, service: str, event_type: str, state: str
    ) -> None:
        """Log circuit breaker event."""
        logger.log(
            self.log_level,
            f"Circuit Breaker: {service} - Event: {event_type}, State: {state}",
        )

    def record_response_size(self, endpoint: str, size_bytes: int) -> None:
        """Log response size."""
        size_mb = size_bytes / (1024 * 1024)
        if size_mb > 1.0:
            logger.log(
                self.log_level,
                f"Response Size: {endpoint} - {size_mb:.2f} MB ({size_bytes:,} bytes)",
            )

    def increment_counter(
        self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Log counter increment."""
        tags_str = f" {tags}" if tags else ""
        logger.debug(f"Counter: {name} +{value}{tags_str}")

    def record_gauge(
        self, name: str, value: float, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Log gauge value."""
        tags_str = f" {tags}" if tags else ""
        logger.debug(f"Gauge: {name} = {value}{tags_str}")

    def record_histogram(
        self, name: str, value: float, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Log histogram value."""
        tags_str = f" {tags}" if tags else ""
        logger.debug(f"Histogram: {name} = {value}{tags_str}")


class MetricsTimer:
    """
    Context manager for timing operations.

    Usage:
        with MetricsTimer(metrics_collector, 'operation_name', endpoint='api/search'):
            # do work
            pass
    """

    def __init__(
        self,
        collector: MetricsCollector,
        name: str,
        tags: Optional[Dict[str, str]] = None,
    ):
        self.collector = collector
        self.name = name
        self.tags = tags or {}
        self.start_time: Optional[float] = None
        self.duration: Optional[float] = None

    def __enter__(self) -> "MetricsTimer":
        """Start timing."""
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Stop timing and record metric."""
        if self.start_time is not None:
            self.duration = time.time() - self.start_time
            self.collector.record_histogram(self.name, self.duration, tags=self.tags)

            # Also record success/failure
            if exc_type is not None:
                self.tags["success"] = "false"
                self.tags["error_type"] = exc_type.__name__
            else:
                self.tags["success"] = "true"

            self.collector.increment_counter(f"{self.name}.calls", tags=self.tags)


# Global metrics collector instance
_metrics_collector: MetricsCollector = NoOpMetricsCollector()


def set_metrics_collector(collector: MetricsCollector) -> None:
    """
    Set the global metrics collector.

    Args:
        collector: Metrics collector implementation
    """
    global _metrics_collector
    _metrics_collector = collector
    logger.info(f"Metrics collector set to: {collector.__class__.__name__}")


def get_metrics_collector() -> MetricsCollector:
    """
    Get the global metrics collector.

    Returns:
        Current metrics collector instance
    """
    return _metrics_collector
