"""Tests for DB performance module (metrics and health checks)."""

import asyncio
import time
from pathlib import Path
import pytest
import tempfile

from src.core.database import (
    EngineManager,
    EmailRepository,
    create_engine,
    metadata,
)
from src.core.database.performance.metrics import (
    MetricsCollector,
    Timer,
    get_metrics_collector,
    reset_metrics_collector,
)
from src.core.database.performance.health import (
    HealthChecker,
    HealthMonitor,
    HealthStatus,
)
from src.core.models.email import Email, EmailAddress, EmailId, FolderName
from datetime import datetime


@pytest.fixture
async def test_db():
    """Create temporary test database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    
    # Create engine and tables
    engine = create_engine(db_path, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    
    yield db_path
    
    # Cleanup
    await engine.dispose()
    db_path.unlink(missing_ok=True)


@pytest.fixture
def metrics_collector():
    """Create fresh metrics collector."""
    reset_metrics_collector()
    collector = MetricsCollector()
    yield collector
    collector.reset()


# ========================================================================
# Metrics Tests
# ========================================================================

def test_counter_increment(metrics_collector):
    """Test counter metric increments."""
    metrics_collector.increment("test_counter", 1.0)
    metrics_collector.increment("test_counter", 2.0)
    metrics_collector.increment("test_counter", 3.0)
    
    assert metrics_collector.get_counter("test_counter") == 6.0


def test_counter_with_labels(metrics_collector):
    """Test counter with labels."""
    metrics_collector.increment("requests", 1.0, {"method": "GET"})
    metrics_collector.increment("requests", 1.0, {"method": "POST"})
    metrics_collector.increment("requests", 1.0, {"method": "GET"})
    
    assert metrics_collector.get_counter("requests", {"method": "GET"}) == 2.0
    assert metrics_collector.get_counter("requests", {"method": "POST"}) == 1.0


def test_gauge_set(metrics_collector):
    """Test gauge metric."""
    metrics_collector.set_gauge("temperature", 72.5)
    assert metrics_collector.get_gauge("temperature") == 72.5
    
    metrics_collector.set_gauge("temperature", 75.0)
    assert metrics_collector.get_gauge("temperature") == 75.0


def test_histogram_observe(metrics_collector):
    """Test histogram observations."""
    for value in [1.0, 2.0, 3.0, 4.0, 5.0]:
        metrics_collector.observe("response_time", value)
    
    stats = metrics_collector.get_histogram_stats("response_time")
    
    assert stats.count == 5
    assert stats.min == 1.0
    assert stats.max == 5.0
    assert stats.avg == 3.0


def test_timer_record(metrics_collector):
    """Test timer metric."""
    metrics_collector.record_time("request_duration", 0.1)
    metrics_collector.record_time("request_duration", 0.2)
    metrics_collector.record_time("request_duration", 0.3)
    
    stats = metrics_collector.get_timer_stats("request_duration")
    
    assert stats.count == 3
    assert stats.min == 0.1
    assert stats.max == 0.3


def test_timer_context_manager(metrics_collector):
    """Test Timer context manager."""
    with Timer("operation", operation="test"):
        time.sleep(0.01)  # Simulate work
    
    stats = metrics_collector.get_timer_stats("operation")
    
    assert stats.count == 1
    assert stats.avg >= 0.01


def test_percentiles(metrics_collector):
    """Test percentile calculations."""
    # Add 100 values from 1 to 100
    for i in range(1, 101):
        metrics_collector.observe("values", float(i))
    
    stats = metrics_collector.get_histogram_stats("values")
    
    assert stats.p50 == pytest.approx(50, abs=5)
    assert stats.p95 == pytest.approx(95, abs=5)
    assert stats.p99 == pytest.approx(99, abs=5)


def test_get_all_metrics(metrics_collector):
    """Test getting all metrics snapshot."""
    metrics_collector.increment("counter1", 10.0)
    metrics_collector.set_gauge("gauge1", 42.0)
    metrics_collector.observe("hist1", 1.5)
    metrics_collector.record_time("timer1", 0.5)
    
    all_metrics = metrics_collector.get_all_metrics()
    
    assert "counters" in all_metrics
    assert "gauges" in all_metrics
    assert "histograms" in all_metrics
    assert "timers" in all_metrics
    assert "timestamp" in all_metrics


# ========================================================================
# Health Check Tests
# ========================================================================

@pytest.mark.asyncio
async def test_connectivity_check(test_db):
    """Test database connectivity check."""
    engine_mgr = EngineManager(test_db)
    repo = EmailRepository(engine_mgr)
    checker = HealthChecker(engine_mgr, repo)
    
    result = await checker.check_connectivity()
    
    assert result.name == "connectivity"
    assert result.status == HealthStatus.HEALTHY
    assert result.duration_ms > 0
    
    await engine_mgr.close()


@pytest.mark.asyncio
async def test_pool_health_check(test_db):
    """Test connection pool health check."""
    engine_mgr = EngineManager(test_db)
    repo = EmailRepository(engine_mgr)
    checker = HealthChecker(engine_mgr, repo)
    
    result = await checker.check_pool_health()
    
    assert result.name == "pool_health"
    assert result.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)
    assert "checked_out" in result.details
    assert "pool_size" in result.details
    
    await engine_mgr.close()


@pytest.mark.asyncio
async def test_query_performance_check(test_db):
    """Test query performance check."""
    engine_mgr = EngineManager(test_db)
    repo = EmailRepository(engine_mgr)
    checker = HealthChecker(engine_mgr, repo)
    
    result = await checker.check_query_performance()
    
    assert result.name == "query_performance"
    assert result.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)
    assert "query_time_ms" in result.details
    
    await engine_mgr.close()


@pytest.mark.asyncio
async def test_disk_space_check(test_db):
    """Test disk space check."""
    engine_mgr = EngineManager(test_db)
    repo = EmailRepository(engine_mgr)
    checker = HealthChecker(engine_mgr, repo)
    
    result = await checker.check_disk_space()
    
    assert result.name == "disk_space"
    # Should be healthy on dev machine
    assert result.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)
    assert "free_gb" in result.details
    assert "db_size_mb" in result.details
    
    await engine_mgr.close()


@pytest.mark.asyncio
async def test_tables_check(test_db):
    """Test table integrity check."""
    engine_mgr = EngineManager(test_db)
    repo = EmailRepository(engine_mgr)
    checker = HealthChecker(engine_mgr, repo)
    
    result = await checker.check_tables()
    
    assert result.name == "tables"
    assert result.status == HealthStatus.HEALTHY
    assert "table_counts" in result.details
    assert "total_rows" in result.details
    
    await engine_mgr.close()


@pytest.mark.asyncio
async def test_check_all(test_db):
    """Test running all health checks."""
    engine_mgr = EngineManager(test_db)
    repo = EmailRepository(engine_mgr)
    checker = HealthChecker(engine_mgr, repo)
    
    health = await checker.check_all()
    
    assert health.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNHEALTHY)
    assert len(health.checks) >= 5
    assert health.timestamp is not None
    
    # All checks should have run
    check_names = {c.name for c in health.checks}
    assert "connectivity" in check_names
    assert "pool_health" in check_names
    assert "query_performance" in check_names
    
    await engine_mgr.close()


@pytest.mark.asyncio
async def test_health_monitor(test_db):
    """Test health monitor."""
    engine_mgr = EngineManager(test_db)
    repo = EmailRepository(engine_mgr)
    monitor = HealthMonitor(engine_mgr, repo, interval=1)
    
    # Start monitor
    await monitor.start()
    
    # Wait for at least one check
    await asyncio.sleep(1.5)
    
    # Get last health
    health = monitor.last_health
    assert health is not None
    assert len(health.checks) > 0
    
    # Stop monitor
    await monitor.stop()
    
    await engine_mgr.close()


@pytest.mark.asyncio
async def test_check_specific(test_db):
    """Test running specific health check."""
    engine_mgr = EngineManager(test_db)
    repo = EmailRepository(engine_mgr)
    checker = HealthChecker(engine_mgr, repo)
    
    # Check connectivity only
    result = await checker.check_specific("connectivity")
    
    assert result.name == "connectivity"
    assert result.status == HealthStatus.HEALTHY
    
    # Invalid check name should raise
    with pytest.raises(ValueError):
        await checker.check_specific("invalid_check")
    
    await engine_mgr.close()


@pytest.mark.asyncio
async def test_failed_checks_property():
    """Test SystemHealth.failed_checks property."""
    from src.core.database.performance.health import SystemHealth, HealthCheckResult
    
    checks = [
        HealthCheckResult(
            name="check1",
            status=HealthStatus.HEALTHY,
            message="OK",
            duration_ms=10.0,
        ),
        HealthCheckResult(
            name="check2",
            status=HealthStatus.UNHEALTHY,
            message="Failed",
            duration_ms=20.0,
        ),
        HealthCheckResult(
            name="check3",
            status=HealthStatus.DEGRADED,
            message="Slow",
            duration_ms=30.0,
        ),
    ]
    
    health = SystemHealth(
        status=HealthStatus.DEGRADED,
        checks=checks,
    )
    
    failed = health.failed_checks
    assert len(failed) == 2
    assert failed[0].name == "check2"
    assert failed[1].name == "check3"
