"""Database configuration with environment variable support."""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DatabaseConfig:
    """Configuration for database connection and behavior."""

    # Connection pool settings
    pool_size: int = field(default_factory=lambda: int(os.getenv("DB_POOL_SIZE", "5")))
    max_overflow: int = field(
        default_factory=lambda: int(os.getenv("DB_MAX_OVERFLOW", "10"))
    )
    pool_timeout: float = field(
        default_factory=lambda: float(os.getenv("DB_POOL_TIMEOUT", "30.0"))
    )
    pool_recycle: int = field(
        default_factory=lambda: int(os.getenv("DB_POOL_RECYCLE", "3600"))
    )

    # Query timeouts
    query_timeout: float = field(
        default_factory=lambda: float(os.getenv("DB_QUERY_TIMEOUT", "30.0"))
    )
    transaction_timeout: float = field(
        default_factory=lambda: float(os.getenv("DB_TRANSACTION_TIMEOUT", "60.0"))
    )

    # Health checks
    health_check_interval: int = field(
        default_factory=lambda: int(os.getenv("DB_HEALTH_CHECK_INTERVAL", "60"))
    )

    # Query caching
    enable_query_cache: bool = field(
        default_factory=lambda: os.getenv("DB_ENABLE_CACHE", "false").lower() == "true"
    )
    cache_ttl: int = field(
        default_factory=lambda: int(os.getenv("DB_CACHE_TTL", "300"))
    )
    cache_max_size: int = field(
        default_factory=lambda: int(os.getenv("DB_CACHE_MAX_SIZE", "1000"))
    )

    # Batch operations
    default_batch_size: int = field(
        default_factory=lambda: int(os.getenv("DB_BATCH_SIZE", "100"))
    )
    max_batch_size: int = field(
        default_factory=lambda: int(os.getenv("DB_MAX_BATCH_SIZE", "1000"))
    )

    # Backup settings
    backup_compression: bool = field(
        default_factory=lambda: os.getenv("DB_BACKUP_COMPRESS", "true").lower()
        == "true"
    )
    max_export_limit: int = field(
        default_factory=lambda: int(os.getenv("DB_MAX_EXPORT_LIMIT", "1000000"))
    )

    # Logging
    log_slow_queries: bool = field(
        default_factory=lambda: os.getenv("DB_LOG_SLOW_QUERIES", "true").lower()
        == "true"
    )
    slow_query_threshold: float = field(
        default_factory=lambda: float(os.getenv("DB_SLOW_QUERY_THRESHOLD", "1.0"))
    )

    def __post_init__(self):
        """Validate configuration values."""
        if self.pool_size < 1:
            raise ValueError("pool_size must be >= 1")
        if self.max_overflow < 0:
            raise ValueError("max_overflow must be >= 0")
        if self.pool_timeout <= 0:
            raise ValueError("pool_timeout must be > 0")
        if self.query_timeout <= 0:
            raise ValueError("query_timeout must be > 0")
        if self.default_batch_size < 1:
            raise ValueError("default_batch_size must be >= 1")
        if self.max_batch_size < self.default_batch_size:
            raise ValueError("max_batch_size must be >= default_batch_size")


# Singleton instance
_config: Optional[DatabaseConfig] = None


def get_config() -> DatabaseConfig:
    """Get or create database configuration singleton.

    Returns:
        DatabaseConfig: The database configuration instance.
    """
    global _config
    if _config is None:
        _config = DatabaseConfig()

    return _config


def reset_config() -> None:
    """Reset configuration (mainly for testing)."""
    global _config
    _config = None
