"""Database connection management."""

import asyncio
import aiosqlite
from pathlib import Path
from typing import Any, Dict, Optional

from src.utils.errors import DatabaseConnectionError
from src.utils.logging import async_log_call, get_logger

logger = get_logger(__name__)

class ConnectionManager:
    """Manages database connection lifecycle and health."""

    DEFAULT_TIMEOUT = 30.0  # seconds
    HEALTH_CHECK_TIMEOUT = 5.0  # seconds
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  # seconds
    MAX_EXPORT_LIMIT = 1_000_000  # maximum records to export
    HEALTH_CHECK_INTERVAL = 60  # seconds between health checks

    def __init__(self, db_path: Path) -> None:
        """Initialize connection manager with database path."""
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()
        self._last_health_check: Optional[float] = None
        self._is_healthy = True

    async def _get_connection(self, retry: bool = True) -> aiosqlite.Connection:
        """Get or create a database connection."""
        async with self._lock:
            if self._connection is None:
                if retry:
                    await self._connect_with_retry()
                else:
                    await self._connect()

            try:
                await asyncio.wait_for(
                    self._connection.execute("SELECT 1;"),
                    timeout=self.DEFAULT_TIMEOUT
                )
            
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning(f"Connection lost: {e}, reconnecting...")
                await self._reconnect()

        return self._connection
    
    async def _connect_with_retry(self) -> None:
        """Attempt to connect with exponential backoff."""
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                await self._connect()
                logger.info(f"Database connected (attempt {attempt + 1})")
                return
            
            except Exception as e:
                last_error = e
                logger.warning(f"Database connection attempt {attempt + 1} failed: {e}")

                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))

        raise DatabaseConnectionError(
            f"Failed to connect to database after {self.MAX_RETRIES} attempts",
            details={"last_error": str(last_error)}
        ) from last_error
            
    async def _connect(self) -> None:
        """Establish a new database connection."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            self._connection = await aiosqlite.connect(
                str(self.db_path),
                timeout=self.DEFAULT_TIMEOUT
            )

            # Mark aiosqlite's worker thread as daemon so it doesn't block exit
            import threading
            for thread in threading.enumerate():
                if thread.name.startswith('aiosqlite'):
                    thread.daemon = True
                    logger.debug(f"Marked aiosqlite thread {thread.name} as daemon")

            await self._connection.execute("PRAGMA foreign_keys = ON;")
            await self._connection.execute("PRAGMA journal_mode = WAL;")
            await self._connection.execute(
                f"PRAGMA busy_timeout = {int(self.DEFAULT_TIMEOUT * 1000)};"
            )

            self._connection.row_factory = aiosqlite.Row
            logger.debug(f"Database connected: {self.db_path}")

        except asyncio.TimeoutError as e:
            raise DatabaseConnectionError(
                "Database connection timed out",
                details={"db_path": str(self.db_path), "timeout": self.DEFAULT_TIMEOUT}
            ) from e

        except Exception as e:
            raise DatabaseConnectionError(
                "Failed to connect to database",
                details={"db_path": str(self.db_path), "error": str(e)}
            ) from e
        
    async def _reconnect(self) -> None:
        """Reconnect to the database."""
        if self._connection:
            try:
                await self._connection.close()
            
            except Exception as e:
                logger.debug(f"Error closing old database connection: {e}")

            finally:
                self._connection = None

        await self._connect_with_retry()

    async def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            try:
                # Close the connection first
                await self._connection.close()
                logger.debug("Database connection closed")
            except Exception as e:
                logger.debug(f"Error closing connection: {e}")
            finally:
                self._connection = None

    @async_log_call
    async def health_check(self, quick: bool = False) -> bool:
        """Perform database health check, quick for connection only"""
        try:
            conn = await asyncio.wait_for(
                self._get_connection(),
                timeout=self.HEALTH_CHECK_TIMEOUT
            )

            if quick:
                return conn is not None
            
            async with conn.execute("SELECT 1;") as cursor:
                result = await cursor.fetchone()
                healthy = result is not None

            self._is_healthy = healthy
            self._last_health_check = asyncio.get_event_loop().time()

            if healthy:
                logger.debug("Database health check: OK")
            else:
                logger.warning("Database health check: FAILED")

            return healthy
        
        except asyncio.TimeoutError:
            self._is_healthy = False
            logger.error("Database health check timed out")
            return False
        
    async def is_healthy(self) -> bool:
        """Check if the database is healthy, performing health check if needed."""
        current_time = asyncio.get_event_loop().time()

        if (self._last_health_check and
            current_time - self._last_health_check < self.HEALTH_CHECK_INTERVAL):
            return self._is_healthy
        
        return await self.health_check(quick=True)

    @async_log_call
    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get database connection statistics."""
        try:
            conn = await self.connection_manager._get_connection()

            stats = {
                "connected": conn is not None,
                "healthy": await self.is_healthy(),
                "database_path": str(self.db_path),
                "database_size": self.db_path.stat().st_size if self.db_path.exists() else 0,
                "last_health_check": self.connection_manager._last_health_check,
            }

            if conn:
                async with conn.execute("PRAGMA page_count;") as cursor:
                    page_count = (await cursor.fetchone())[0]

                async with conn.execute("PRAGMA page_size;") as cursor:
                    page_size = (await cursor.fetchone())[0]

                async with conn.execute("PRAGMA journal_mode;") as cursor:
                    journal_mode = (await cursor.fetchone())[0]

                stats.update({
                    "page_count": page_count,
                    "page_size": page_size,
                    "journal_mode": journal_mode,
                    "estimated_size": page_count * page_size,
                })

            return stats
        
        except Exception as e:
            logger.error(f"Failed to get connection stats: {e}")
            return {
                "connected": False,
                "healthy": False,
                "error": str(e)
            }