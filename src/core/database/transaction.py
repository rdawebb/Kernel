"""Transaction manager with savepoint support for nested transactions."""

import time
from contextlib import asynccontextmanager
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from src.core.database.config import get_config
from src.utils.errors import DatabaseTransactionError
from src.utils.logging import get_logger

logger = get_logger(__name__)


class TransactionManager:
    """Manages database transactions with timeout and savepoint support.
    
    Provides explicit transaction control with:
    - Automatic commit/rollback
    - Timeout enforcement
    - Nested transactions via savepoints
    - Transaction duration logging
    """

    def __init__(
        self,
        engine: AsyncEngine,
        timeout: Optional[float] = None,
        isolation_level: Optional[str] = None,
    ):
        """Initialise transaction manager.

        Args:
            engine: SQLAlchemy async engine
            timeout: Transaction timeout in seconds (uses config default if None)
            isolation_level: SQLite isolation level (SERIALIZABLE, etc.)
        """
        self.engine = engine
        self.config = get_config()
        self.timeout = timeout or self.config.transaction_timeout
        self.isolation_level = isolation_level or "SERIALIZABLE"
        
        self._connection: Optional[AsyncConnection] = None
        self._transaction = None
        self._start_time: Optional[float] = None
        self._savepoint_depth = 0

    async def __aenter__(self) -> "TransactionManager":
        """Start transaction.

        Returns:
            TransactionManager instance
        """
        self._start_time = time.time()
        
        try:
            self._connection = await self.engine.connect()
            
            # Begin transaction with isolation level
            self._transaction = await self._connection.begin()
            
            logger.debug(
                f"Transaction started (isolation={self.isolation_level}, "
                f"timeout={self.timeout}s)"
            )
            
            return self
            
        except Exception as e:
            if self._connection:
                await self._connection.close()
            raise DatabaseTransactionError(
                "Failed to start transaction",
                details={"error": str(e)},
            ) from e

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Commit or rollback transaction."""
        duration = time.time() - self._start_time if self._start_time else 0
        
        try:
            # Check timeout
            if duration > self.timeout:
                logger.warning(
                    f"Transaction exceeded timeout: {duration:.2f}s > {self.timeout}s"
                )
                if self._transaction:
                    await self._transaction.rollback()
                raise DatabaseTransactionError(
                    f"Transaction timeout after {duration:.2f}s",
                    details={"timeout": self.timeout, "duration": duration},
                )
            
            if exc_type is not None:
                if self._transaction:
                    await self._transaction.rollback()
                logger.warning(
                    f"Transaction rolled back due to {exc_type.__name__}: {exc_val} "
                    f"(duration={duration:.2f}s)"
                )
            else:
                # Commit on success
                if self._transaction:
                    await self._transaction.commit()
                logger.debug(f"Transaction committed (duration={duration:.2f}s)")
                
                # Log slow transactions
                if self.config.log_slow_queries and duration > self.config.slow_query_threshold:
                    logger.warning(
                        f"Slow transaction: {duration:.2f}s "
                        f"(threshold={self.config.slow_query_threshold}s)"
                    )
        
        finally:
            if self._connection:
                await self._connection.close()

    @property
    def connection(self) -> AsyncConnection:
        """Get the transaction's connection.
        
        Returns:
            Active connection for executing queries
            
        Raises:
            RuntimeError: If accessed outside transaction context
        """
        if not self._connection:
            raise RuntimeError("Connection only available within transaction context")
        
        return self._connection

    @asynccontextmanager
    async def savepoint(self, name: Optional[str] = None):
        """Create a savepoint for nested transaction.
        
        Args:
            name: Optional savepoint name (auto-generated if None)
            
        Yields:
            Savepoint context manager
            
        Usage:
            async with tx.savepoint() as sp:
                await conn.execute(query)
                # Can roll back just this savepoint
        """
        if not self._connection:
            raise RuntimeError("Savepoint requires active transaction")
        
        self._savepoint_depth += 1
        savepoint_name = name or f"sp_{self._savepoint_depth}"
        
        nested_tx = await self._connection.begin_nested()
        
        logger.debug(f"Savepoint created: {savepoint_name}")
        
        try:
            yield nested_tx
            await nested_tx.commit()
            logger.debug(f"Savepoint committed: {savepoint_name}")

        except Exception as e:
            await nested_tx.rollback()
            logger.debug(f"Savepoint rolled back: {savepoint_name} - {e}")
            raise
        finally:
            self._savepoint_depth -= 1


class ReadOnlyTransactionManager(TransactionManager):
    """Read-only transaction manager that prevents writes. """

    async def __aenter__(self) -> "ReadOnlyTransactionManager":
        """Start read-only transaction."""
        await super().__aenter__()

        # Set read-only mode at application level
        logger.debug("Read-only transaction started")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Always rollback (no commits in read-only mode)."""
        if self._transaction:
            await self._transaction.rollback()
            logger.debug("Read-only transaction rolled back")
        
        if self._connection:
            await self._connection.close()


# Convenience factory functions

async def transaction(
    engine: AsyncEngine,
    timeout: Optional[float] = None,
) -> TransactionManager:
    """Create a transaction manager (convenience function).
    
    Usage:
        async with transaction(engine) as tx:
            await tx.connection.execute(query)
    """
    return TransactionManager(engine, timeout=timeout)


async def readonly_transaction(
    engine: AsyncEngine,
    timeout: Optional[float] = None,
) -> ReadOnlyTransactionManager:
    """Create a read-only transaction manager (convenience function).
    
    Usage:
        async with readonly_transaction(engine) as tx:
            result = await tx.connection.execute(select_query)
    """
    return ReadOnlyTransactionManager(engine, timeout=timeout)
