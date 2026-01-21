"""Metrics collection and monitoring for database operations."""

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Deque, Dict, List, Optional, Any, Callable
from threading import Lock

from src.utils.logging import get_logger

logger = get_logger(__name__)


class MetricType(Enum):
    """Types of metrics collected."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class MetricPoint:
    """Single metric data point."""

    timestamp: float
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class MetricStats:
    """Statistical summary of metric values."""

    count: int
    sum: float
    min: float
    max: float
    avg: float
    p50: float
    p95: float
    p99: float

    @classmethod
    def from_values(cls, values: List[float]) -> "MetricStats":
        """Calculate statistics from list of values."""
        if not values:
            return cls(
                count=0,
                sum=0.0,
                min=0.0,
                max=0.0,
                avg=0.0,
                p50=0.0,
                p95=0.0,
                p99=0.0,
            )

        sorted_vals = sorted(values)
        count = len(sorted_vals)

        return cls(
            count=count,
            sum=sum(sorted_vals),
            min=sorted_vals[0],
            max=sorted_vals[-1],
            avg=sum(sorted_vals) / count,
            p50=sorted_vals[int(count * 0.50)],
            p95=sorted_vals[int(count * 0.95)] if count > 1 else sorted_vals[0],
            p99=sorted_vals[int(count * 0.99)] if count > 1 else sorted_vals[0],
        )


class MetricsCollector:
    """Collects and aggregates database metrics.

    Thread-safe metrics collection with:
    - Counter metrics (increments only)
    - Gauge metrics (current value)
    - Histogram metrics (distribution)
    - Timer metrics (duration tracking)
    - Automatic retention and aggregation
    """

    def __init__(self, retention_seconds: int = 3600) -> None:
        """Initialise metrics collector.

        Args:
            retention_seconds: How long to retain metric history
        """
        self._retention = retention_seconds
        self._lock = Lock()

        # Storage for different metric types
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, Deque[MetricPoint]] = defaultdict(
            lambda: deque(maxlen=10000)
        )
        self._timers: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=10000))

        # Labels for metrics
        self._labels: Dict[str, Dict[str, str]] = {}

    def increment(
        self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Increment a counter metric.

        Args:
            name: Metric name
            value: Amount to increment
            labels: Optional metric labels
        """
        with self._lock:
            key = self._make_key(name, labels)
            self._counters[key] += value

            if labels:
                self._labels[key] = labels

    def set_gauge(
        self, name: str, value: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Set a gauge metric to specific value.

        Args:
            name: Metric name
            value: Current value
            labels: Optional metric labels
        """
        with self._lock:
            key = self._make_key(name, labels)
            self._gauges[key] = value

            if labels:
                self._labels[key] = labels

    def observe(
        self, name: str, value: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Observe a value for histogram metric.

        Args:
            name: Metric name
            value: Observed value
            labels: Optional metric labels
        """
        with self._lock:
            key = self._make_key(name, labels)
            point = MetricPoint(
                timestamp=time.time(),
                value=value,
                labels=labels or {},
            )
            self._histograms[key].append(point)

            if labels:
                self._labels[key] = labels

    def record_time(
        self, name: str, duration: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Record duration for timer metric.

        Args:
            name: Metric name
            duration: Duration in seconds
            labels: Optional metric labels
        """
        with self._lock:
            key = self._make_key(name, labels)
            self._timers[key].append(duration)

            if labels:
                self._labels[key] = labels

    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Get current counter value."""
        with self._lock:
            key = self._make_key(name, labels)
            return self._counters.get(key, 0.0)

    def get_gauge(
        self, name: str, labels: Optional[Dict[str, str]] = None
    ) -> Optional[float]:
        """Get current gauge value."""
        with self._lock:
            key = self._make_key(name, labels)
            return self._gauges.get(key)

    def get_histogram_stats(
        self, name: str, labels: Optional[Dict[str, str]] = None
    ) -> Optional[MetricStats]:
        """Get statistics for histogram metric."""
        with self._lock:
            key = self._make_key(name, labels)
            points = self._histograms.get(key)

            if not points:
                return None

            # Filter to retention window
            cutoff = time.time() - self._retention
            values = [p.value for p in points if p.timestamp > cutoff]

            return MetricStats.from_values(values)

    def get_timer_stats(
        self, name: str, labels: Optional[Dict[str, str]] = None
    ) -> Optional[MetricStats]:
        """Get statistics for timer metric."""
        with self._lock:
            key = self._make_key(name, labels)
            values = list(self._timers.get(key, []))

            if not values:
                return None

            return MetricStats.from_values(values)

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get snapshot of all metrics."""
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {
                    name: self.get_histogram_stats(name)
                    for name in self._histograms.keys()
                },
                "timers": {
                    name: self.get_timer_stats(name) for name in self._timers.keys()
                },
                "timestamp": datetime.now().isoformat(),
            }

    def reset(self) -> None:
        """Reset all metrics (useful for testing)."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._timers.clear()
            self._labels.clear()

    def _make_key(self, name: str, labels: Optional[Dict[str, str]]) -> str:
        """Create unique key from name and labels."""
        if not labels:
            return name

        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def cleanup_old_data(self) -> None:
        """Remove old metric data points beyond retention period."""
        with self._lock:
            cutoff = time.time() - self._retention

            # Clean up histograms
            for key, points in self._histograms.items():
                while points and points[0].timestamp < cutoff:
                    points.popleft()


# Global singleton
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create global metrics collector."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def reset_metrics_collector() -> None:
    """Reset global metrics collector (for testing)."""
    global _metrics_collector
    _metrics_collector = None


# Convenience functions


def increment_counter(name: str, value: float = 1.0, **labels) -> None:
    """Increment a counter metric."""
    get_metrics_collector().increment(name, value, labels or None)


def set_gauge(name: str, value: float, **labels) -> None:
    """Set a gauge metric."""
    get_metrics_collector().set_gauge(name, value, labels or None)


def observe_value(name: str, value: float, **labels) -> None:
    """Observe a histogram value."""
    get_metrics_collector().observe(name, value, labels or None)


def record_duration(name: str, duration: float, **labels) -> None:
    """Record a timer duration."""
    get_metrics_collector().record_time(name, duration, labels or None)


# Context manager for timing operations


class Timer:
    """Context manager for timing operations.

    Usage:
        with Timer("query_execution", operation="select"):
            await conn.execute(query)
    """

    def __init__(self, metric_name: str, **labels) -> None:
        """Initialise timer.

        Args:
            metric_name: Name of timer metric
            **labels: Optional metric labels
        """
        self.metric_name = metric_name
        self.labels = labels
        self.start_time = None

    def __enter__(self) -> "Timer":
        """Start timing."""
        self.start_time = time.time()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Stop timing and record duration."""
        if self.start_time is not None:
            duration = time.time() - self.start_time
            record_duration(self.metric_name, duration, **self.labels)


# Decorator for automatic timing


def timed(metric_name: Optional[str] = None, **labels) -> Callable:
    """Decorator to automatically time function execution.

    Usage:
        @timed("repository_save", operation="insert")
        async def save(self, email):
            ...
    """

    def decorator(func) -> Callable:
        local_metric_name = (
            metric_name
            if metric_name is not None
            else f"{func.__module__}.{func.__name__}"
        )

        if asyncio.iscoroutinefunction(func):

            async def async_wrapper(*args, **kwargs):
                with Timer(local_metric_name, **labels):
                    return await func(*args, **kwargs)

            return async_wrapper
        else:

            def sync_wrapper(*args, **kwargs):
                with Timer(local_metric_name, **labels):
                    return func(*args, **kwargs)

            return sync_wrapper

    return decorator


import asyncio  # Import at end to avoid circular dependency
