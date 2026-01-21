"""Engine manager wrapping SQLAlchemy connection pool."""

import asyncio
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from src.core.database.base import create_engine, dispose_engine
from src.core.database.config import DatabaseConfig, get_config
from src.utils.errors import DatabaseConnectionError
from src.utils.logging import get_logger

logger = get_logger(__name__)


class EngineManager:
    """Manages SQLAlchemy async engine lifecycle and health."""

    def __init__(
        self,
        db_path: Path,
        config: Optional[DatabaseConfig] = None,
        echo: Optional[bool] = None,
    ) -> None:
        """initialise engine manager.

        Args:
            db_path: Path to SQLite database file
            config: Database configuration (uses singleton if None)
            echo: Enable SQL logging (auto-detects dev/prod if None)
        """
        self.db_path = db_path
        self.config = config or get_config()

        # Auto-detect echo based on environment if not specified
        if echo is None:
            echo = os.getenv("ENV", "production").lower() in ("dev", "development")

        self._engine: Optional[AsyncEngine] = None
        self._lock = asyncio.Lock()
        self._last_health_check: Optional[float] = None
        self._is_healthy = True

    async def get_engine(self) -> AsyncEngine:
        """Get or create the async engine.

        Returns:
            AsyncEngine instance with connection pooling

        Raises:
            DatabaseConnectionError: If engine creation fails
        """
        async with self._lock:
            if self._engine is None:
                try:
                    self._engine = create_engine(
                        self.db_path,
                        config=self.config,
                        echo=self.config.log_slow_queries,
                    )
                    logger.info(f"Engine initialised: {self.db_path}")
                except Exception as e:
                    raise DatabaseConnectionError(
                        "Failed to create database engine",
                        details={"db_path": str(self.db_path), "error": str(e)},
                    ) from e

        return self._engine

    async def get_connection(self) -> AsyncConnection:
        """Get a connection from the pool.

        Returns:
            AsyncConnection from the pool

        Usage:
            async with manager.get_connection() as conn:
                result = await conn.execute(query)
        """
        engine = await self.get_engine()
        return await engine.connect()

    async def close(self) -> None:
        """Dispose of engine and close all pooled connections."""
        if self._engine:
            try:
                await dispose_engine(self._engine)
                self._engine = None
                logger.info("Engine disposed")
            except Exception as e:
                logger.error(f"Error disposing engine: {e}")

    async def health_check(self, quick: bool = False) -> bool:
        """Perform database health check.

        Args:
            quick: If True, only checks if engine exists (fast)

        Returns:
            True if healthy, False otherwise
        """
        try:
            engine = await self.get_engine()

            if quick:
                self._is_healthy = engine is not None
                return self._is_healthy

            # Full health check: execute simple query
            async with engine.connect() as conn:
                from sqlalchemy import text

                result = await conn.execute(text("SELECT 1"))
                row = result.fetchone()
                healthy = row is not None and row[0] == 1

            self._is_healthy = healthy
            self._last_health_check = time.time()

            if healthy:
                logger.debug("Database health check: OK")
            else:
                logger.warning("Database health check: FAILED")

            return healthy

        except Exception as e:
            self._is_healthy = False
            logger.error(f"Database health check failed: {e}")
            return False

    async def is_healthy(self, force_refresh: bool = False) -> bool:
        """Check if database is healthy (cached).

        Returns:
            True if healthy, False otherwise
        """
        async with self._lock:
            if not force_refresh and self._last_health_check:
                current_time = time.time()

                if (
                    current_time - self._last_health_check
                    < self.config.health_check_interval
                ):
                    return self._is_healthy

            return await self.health_check(quick=True)

    async def get_pool_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics.

        Returns:
            Dictionary with pool metrics
        """
        try:
            engine = await self.get_engine()
            pool = engine.pool

            stats = {
                "database_path": str(self.db_path),
                "pool_size": self.config.pool_size,
                "max_overflow": self.config.max_overflow,
                "pool_timeout": self.config.pool_timeout,
                "healthy": await self.is_healthy(),
                "last_health_check": self._last_health_check,
            }

            # SQLAlchemy pool stats (if available)
            if hasattr(pool, "size"):
                stats["current_pool_size"] = pool.size
            if hasattr(pool, "checkedin"):
                stats["checked_in"] = pool.checkedin
            if hasattr(pool, "overflow"):
                stats["overflow_connections"] = pool.overflow
            if hasattr(pool, "checkedout"):
                stats["checked_out"] = pool.checkedout

            # Database file stats
            if self.db_path.exists():
                stats["database_size_bytes"] = self.db_path.stat().st_size
                stats["database_size_mb"] = round(
                    stats["database_size_bytes"] / 1024 / 1024, 2
                )

            return stats

        except Exception as e:
            logger.error(f"Failed to get pool stats: {e}")
            return {
                "error": str(e),
                "healthy": False,
            }

    # Context manager support
    async def __aenter__(self):
        """Context manager entry."""
        await self.get_engine()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Context manager exit."""
        try:
            await self.close()
        except Exception as e:
            if exc_type is None:
                raise
            logger.error(f"Error closing engine: {e}")
        return False
