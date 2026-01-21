"""Database access layer - public API."""

from .base import create_engine, dispose_engine, metadata
from .config import DatabaseConfig, get_config, reset_config
from .engine_manager import EngineManager
from .models import ALL_TABLES, get_table, inbox, sent, drafts, trash
from .query import QueryBuilder
from .repositories.email import BatchResult, EmailRepository
from .services.backup import BackupService, BackupResult, ExportResult
from .services.search import (
    SearchService,
    SearchQuery,
    SearchFilter,
    SearchOperator,
    SearchQueryBuilder,
    SearchResult,
)
from .transaction import TransactionManager, transaction, readonly_transaction

__all__ = [
    "create_engine",
    "dispose_engine",
    "metadata",
    "EngineManager",
    "DatabaseConfig",
    "get_config",
    "reset_config",
    "ALL_TABLES",
    "get_table",
    "inbox",
    "sent",
    "drafts",
    "trash",
    "QueryBuilder",
    "BatchResult",
    "EmailRepository",
    "BackupService",
    "BackupResult",
    "ExportResult",
    "SearchService",
    "SearchQuery",
    "SearchFilter",
    "SearchOperator",
    "SearchQueryBuilder",
    "SearchResult",
    "TransactionManager",
    "transaction",
    "readonly_transaction",
]
