"""Base database infrastructure with SQLAlchemy async engine."""

from pathlib import Path
from typing import Optional

from sqlalchemy import MetaData, event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool

from src.core.database.config import DatabaseConfig, get_config
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Shared metadata for all tables
metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)


def create_engine(
    db_path: Path,
    config: Optional[DatabaseConfig] = None,
    echo: bool = False,
) -> AsyncEngine:
    """Create async SQLAlchemy engine with connection pooling.

    Args:
        db_path: Path to SQLite database file
        config: Database configuration (uses singleton if None)
        echo: Enable SQL query logging (for debugging)

    Returns:
        Configured async engine
    """
    if config is None:
        config = get_config()

    db_path.parent.mkdir(parents=True, exist_ok=True)

    # SQLite async URL
    url = f"sqlite+aiosqlite:///{db_path}"

    engine = create_async_engine(
        url,
        echo=echo,
        poolclass=AsyncAdaptedQueuePool,
        pool_size=config.pool_size,
        max_overflow=config.max_overflow,
        pool_timeout=config.pool_timeout,
        pool_recycle=config.pool_recycle,
        pool_pre_ping=True,  # Verify connections before use
        connect_args={
            "timeout": config.query_timeout,
            "check_same_thread": False,  # Required for async
        },
    )

    # Register SQLite-specific pragmas
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        """Set SQLite pragmas for performance and safety."""
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA mmap_size=30000000000")
        cursor.execute("PRAGMA page_size=4096")
        cursor.close()

    logger.info(
        f"Database engine created: {db_path} "
        f"(pool_size={config.pool_size}, max_overflow={config.max_overflow})"
    )

    return engine


async def dispose_engine(engine: AsyncEngine) -> None:
    """Dispose of engine and close all connections.

    Args:
        engine: Engine to dispose
    """
    await engine.dispose()
    logger.info("Database engine disposed")
