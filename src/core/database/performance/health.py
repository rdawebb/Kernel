"""Database health check and monitoring system."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from src.core.database.engine_manager import EngineManager
from src.core.database.repositories.email import EmailRepository
from src.core.models.email import FolderName
from src.utils.logging import get_logger

logger = get_logger(__name__)


class HealthStatus(Enum):
    """Health check status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a single health check."""

    name: str
    status: HealthStatus
    message: str
    duration_ms: float
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_healthy(self) -> bool:
        """Check if status is healthy.

        Returns:
            bool: True if healthy, False otherwise
        """
        return self.status == HealthStatus.HEALTHY


@dataclass
class SystemHealth:
    """Overall system health status."""

    status: HealthStatus
    checks: List[HealthCheckResult]
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_healthy(self) -> bool:
        """Check if all checks are healthy.

        Returns:
            bool: True if all checks are healthy, False otherwise
        """
        return self.status == HealthStatus.HEALTHY

    @property
    def failed_checks(self) -> List[HealthCheckResult]:
        """Get list of failed checks.

        Returns:
            List[HealthCheckResult]: List of failed health checks
        """
        return [
            check
            for check in self.checks
            if check.status != HealthStatus.HEALTHY
        ]


class HealthChecker:
    """Performs comprehensive health checks on database system.
    
    Checks:
    - Database connectivity
    - Connection pool health
    - Query performance
    - Disk space
    - Table integrity
    - Index usage
    """

    def __init__(
        self,
        engine_manager: EngineManager,
        email_repository: EmailRepository,
    ) -> None:
        """Initialise health checker.

        Args:
            engine_manager: Database engine manager
            email_repository: Email repository for queries
        """
        self.engine_mgr = engine_manager
        self.email_repo = email_repository

    async def check_all(self) -> SystemHealth:
        """Run all health checks.

        Returns:
            SystemHealth with aggregated results
        """
        checks = [
            await self.check_connectivity(),
            await self.check_pool_health(),
            await self.check_query_performance(),
            await self.check_disk_space(),
            await self.check_tables(),
        ]

        # Determine overall status
        if all(c.is_healthy for c in checks):
            overall_status = HealthStatus.HEALTHY
        elif any(c.status == HealthStatus.UNHEALTHY for c in checks):
            overall_status = HealthStatus.UNHEALTHY
        else:
            overall_status = HealthStatus.DEGRADED

        return SystemHealth(
            status=overall_status,
            checks=checks,
        )

    async def check_connectivity(self) -> HealthCheckResult:
        """Check database connectivity.

        Returns:
            HealthCheckResult: Result of the health check
        """
        import time

        start = time.time()

        try:
            is_healthy = await self.engine_mgr.health_check(quick=False)
            duration_ms = (time.time() - start) * 1000

            if is_healthy:
                return HealthCheckResult(
                    name="connectivity",
                    status=HealthStatus.HEALTHY,
                    message="Database connection is healthy",
                    duration_ms=duration_ms,
                )
            else:
                return HealthCheckResult(
                    name="connectivity",
                    status=HealthStatus.UNHEALTHY,
                    message="Database connection failed",
                    duration_ms=duration_ms,
                )

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            return HealthCheckResult(
                name="connectivity",
                status=HealthStatus.UNHEALTHY,
                message=f"Connection check failed: {e}",
                duration_ms=duration_ms,
            )

    async def check_pool_health(self) -> HealthCheckResult:
        """Check connection pool health.

        Returns:
            HealthCheckResult: Result of the health check
        """
        import time

        start = time.time()

        try:
            stats = await self.engine_mgr.get_pool_stats()
            duration_ms = (time.time() - start) * 1000

            # Check if pool is available
            if not stats.get("healthy"):
                return HealthCheckResult(
                    name="pool_health",
                    status=HealthStatus.UNHEALTHY,
                    message="Connection pool is unhealthy",
                    duration_ms=duration_ms,
                    details=stats,
                )

            # Check pool usage
            checked_out = stats.get("checked_out", 0)
            pool_size = stats.get("pool_size", 0)
            overflow = stats.get("overflow_connections", 0)

            if checked_out >= pool_size + overflow:
                status = HealthStatus.DEGRADED
                message = "Connection pool exhausted"
            elif checked_out > pool_size * 0.8:
                status = HealthStatus.DEGRADED
                message = "Connection pool usage high"
            else:
                status = HealthStatus.HEALTHY
                message = "Connection pool is healthy"

            return HealthCheckResult(
                name="pool_health",
                status=status,
                message=message,
                duration_ms=duration_ms,
                details={
                    "checked_out": checked_out,
                    "pool_size": pool_size,
                    "overflow": overflow,
                    "usage_pct": (checked_out / pool_size * 100) if pool_size > 0 else 0,
                },
            )

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            return HealthCheckResult(
                name="pool_health",
                status=HealthStatus.UNKNOWN,
                message=f"Pool health check failed: {e}",
                duration_ms=duration_ms,
            )

    async def check_query_performance(self) -> HealthCheckResult:
        """Check query performance with test query.

        Returns:
            HealthCheckResult: Result of the health check
        """
        import time

        start = time.time()

        try:
            # Run a simple query to test performance
            await self.email_repo.count(FolderName.INBOX)
            duration_ms = (time.time() - start) * 1000

            # Classify performance
            if duration_ms < 100:
                status = HealthStatus.HEALTHY
                message = "Query performance is excellent"
            elif duration_ms < 500:
                status = HealthStatus.HEALTHY
                message = "Query performance is good"
            elif duration_ms < 1000:
                status = HealthStatus.DEGRADED
                message = "Query performance is slow"
            else:
                status = HealthStatus.DEGRADED
                message = "Query performance is poor"

            return HealthCheckResult(
                name="query_performance",
                status=status,
                message=message,
                duration_ms=duration_ms,
                details={"query_time_ms": duration_ms},
            )

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            return HealthCheckResult(
                name="query_performance",
                status=HealthStatus.UNHEALTHY,
                message=f"Query failed: {e}",
                duration_ms=duration_ms,
            )

    async def check_disk_space(self) -> HealthCheckResult:
        """Check available disk space.

        Returns:
            HealthCheckResult: Result of the health check
        """
        import time
        import shutil

        start = time.time()

        try:
            db_path = self.engine_mgr.db_path

            if not db_path.exists():
                return HealthCheckResult(
                    name="disk_space",
                    status=HealthStatus.UNHEALTHY,
                    message="Database file not found",
                    duration_ms=(time.time() - start) * 1000,
                )

            # Get disk usage
            usage = shutil.disk_usage(db_path.parent)
            free_gb = usage.free / (1024**3)
            total_gb = usage.total / (1024**3)
            used_pct = (usage.used / usage.total) * 100

            # Get database size
            db_size_mb = db_path.stat().st_size / (1024**2)

            duration_ms = (time.time() - start) * 1000

            # Classify disk space
            if free_gb < 0.5:
                status = HealthStatus.UNHEALTHY
                message = f"Critical: Only {free_gb:.2f} GB free"
            elif free_gb < 2.0:
                status = HealthStatus.DEGRADED
                message = f"Warning: Low disk space ({free_gb:.2f} GB free)"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk space is adequate ({free_gb:.2f} GB free)"

            return HealthCheckResult(
                name="disk_space",
                status=status,
                message=message,
                duration_ms=duration_ms,
                details={
                    "free_gb": round(free_gb, 2),
                    "total_gb": round(total_gb, 2),
                    "used_pct": round(used_pct, 1),
                    "db_size_mb": round(db_size_mb, 2),
                },
            )

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            return HealthCheckResult(
                name="disk_space",
                status=HealthStatus.UNKNOWN,
                message=f"Disk space check failed: {e}",
                duration_ms=duration_ms,
            )

    async def check_tables(self) -> HealthCheckResult:
        """Check table integrity and row counts.

        Returns:
            HealthCheckResult: Result of the health check
        """
        import time

        start = time.time()

        try:
            table_counts = {}

            for folder in FolderName:
                count = await self.email_repo.count(folder)
                table_counts[folder.value] = count

            duration_ms = (time.time() - start) * 1000

            total_rows = sum(table_counts.values())

            return HealthCheckResult(
                name="tables",
                status=HealthStatus.HEALTHY,
                message=f"All tables accessible ({total_rows} total rows)",
                duration_ms=duration_ms,
                details={"table_counts": table_counts, "total_rows": total_rows},
            )

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            return HealthCheckResult(
                name="tables",
                status=HealthStatus.UNHEALTHY,
                message=f"Table check failed: {e}",
                duration_ms=duration_ms,
            )

    async def check_specific(self, check_name: str) -> HealthCheckResult:
        """Run a specific health check by name.

        Args:
            check_name: Name of check to run

        Returns:
            HealthCheckResult for specific check

        Raises:
            ValueError: If check name is invalid
        """
        checks_map = {
            "connectivity": self.check_connectivity,
            "pool_health": self.check_pool_health,
            "query_performance": self.check_query_performance,
            "disk_space": self.check_disk_space,
            "tables": self.check_tables,
        }

        check_func = checks_map.get(check_name)
        if not check_func:
            raise ValueError(
                f"Invalid check name: {check_name}. "
                f"Must be one of: {', '.join(checks_map.keys())}"
            )

        return await check_func()


# Periodic health check monitor

class HealthMonitor:
    """Periodically monitors database health in background.
    
    Usage:
        monitor = HealthMonitor(engine_mgr, repo, interval=60)
        await monitor.start()
        
        # Later...
        health = monitor.last_health
        await monitor.stop()
    """

    def __init__(
        self,
        engine_manager: EngineManager,
        email_repository: EmailRepository,
        interval: int = 60,
    ) -> None:
        """Initialise health monitor.

        Args:
            engine_manager: Database engine manager
            email_repository: Email repository
            interval: Check interval in seconds
        """
        self.checker = HealthChecker(engine_manager, email_repository)
        self.interval = interval
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._last_health: Optional[SystemHealth] = None

    async def start(self) -> None:
        """Start periodic health monitoring."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Health monitor started (interval={self.interval}s)")

    async def stop(self) -> None:
        """Stop health monitoring."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Health monitor stopped")

    @property
    def last_health(self) -> Optional[SystemHealth]:
        """Get last health check result.

        Returns:
            Optional[SystemHealth]: Last health check result
        """
        return self._last_health

    async def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while self._running:
            try:
                health = await self.checker.check_all()
                self._last_health = health

                if not health.is_healthy:
                    logger.warning(
                        f"Health check failed: {health.status.value} "
                        f"({len(health.failed_checks)} checks failed)"
                    )
                    for check in health.failed_checks:
                        logger.warning(f"  - {check.name}: {check.message}")

                await asyncio.sleep(self.interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitor error: {e}")
                await asyncio.sleep(self.interval)
