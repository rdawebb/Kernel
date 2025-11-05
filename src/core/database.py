"""Unified database access layer for email storage and retrieval."""

import aiosqlite
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.utils.error_handling import (
    DatabaseConnectionError,
    DatabaseError,
    EmailNotFoundError,
    InvalidTableError,
)
from src.utils.log_manager import async_log_call, get_logger
from src.utils.paths import DATABASE_PATH

logger = get_logger(__name__)


## Schema Definitions

@dataclass
class TableSchema:
    """Schema definition for a database table."""

    name: str
    additional_columns: List[str] = field(default_factory=list)

    BASE_COLUMNS = [
        "uid", "subject", "sender", "recipient", 
        "date", "time", "body", "attachments"
    ]

    COLUMN_DEFS = {
        "flagged": "flagged BOOLEAN DEFAULT 0",
        "deleted_at": "deleted_at TEXT",
        "sent_status": "sent_status TEXT DEFAULT 'pending'",
        "send_at": "send_at TEXT"
    }

    @property
    def all_columns(self) -> List[str]:
        """Return all columns including additional ones."""
        return self.BASE_COLUMNS + self.additional_columns
    
    def create_table_sql(self) -> str:
        """Generate SQL for creating the table."""
        base = """
            uid TEXT PRIMARY KEY,
            subject TEXT,
            sender TEXT,
            recipient TEXT,
            date TEXT,
            time TEXT,
            body TEXT,
            attachments TEXT DEFAULT ''
        """

        if self.additional_columns:
            additional = [self.COLUMN_DEFS[col] for col in self.additional_columns]
            base = base.rstrip() + ",\n" + ",\n".join(additional)

        return f"CREATE TABLE IF NOT EXISTS {self.name} ({base});"

    def create_indexes_sql(self) -> List[str]:
        """Generate SQL for creating indexes on table."""
        indexes = [
            f"CREATE INDEX IF NOT EXISTS idx_{self.name}_uid ON {self.name}(uid);",
            f"CREATE INDEX IF NOT EXISTS idx_{self.name}_date ON {self.name}(date DESC, time DESC);",
            f"CREATE INDEX IF NOT EXISTS idx_{self.name}_sender ON {self.name}(sender);",
        ]

        if "flagged" in self.additional_columns:
            indexes.append(f"CREATE INDEX IF NOT EXISTS idx_{self.name}_flagged ON {self.name}(flagged) WHERE flagged = 1;")

        return indexes


SCHEMAS = {
    "inbox": TableSchema("inbox", ["flagged"]),
    "sent": TableSchema("sent", ["sent_status", "send_at"]),
    "drafts": TableSchema("drafts"),
    "trash": TableSchema("trash", ["deleted_at"]),
}

FIELD_MAPPING = {
    "sender": ["sender", "from"],
    "recipient": ["recipient", "to"],
}

## Query Building

class QueryBuilder:
    """Helper class to build SQL queries dynamically."""

    @staticmethod
    def build_select_columns(schema: TableSchema, include_body: bool = True) -> str:
        """Build a comma-separated string of columns for SELECT queries."""
        columns = [
            "uid",
            "subject",
            "sender as 'from'",
            "recipient as 'to'",
            "date",
            "time",
        ]

        if include_body:
            columns.append("body")

        columns.append("attachments")

        return ", ".join(columns)
    
    @staticmethod
    def build_where_clause(
        conditions: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, List[Any]]:
        """Build WHERE clause and parameters from conditions."""
        if not conditions:
            return "1=1", []
        
        clauses = []
        params = []

        for cond_field, value in conditions.items():
            if value is None:
                clauses.append(f"{cond_field} IS NULL")
            elif isinstance(value, (list, tuple)):
                placeholders = ", ".join("?" for _ in value)
                clauses.append(f"{cond_field} IN ({placeholders})")
                params.extend(value)
            else:
                clauses.append(f"{cond_field} = ?")
                params.append(value)

        return " AND ".join(clauses), params
                
    @staticmethod
    def build_placeholders(count: int) -> str:
        """Build a string of placeholders for prepared statements."""
        return ", ".join("?" for _ in range(count))
        

## Connection Manager

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
            await self._connection.close()
            self._connection = None
            logger.debug("Database connection closed")

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


## Database Access Layer

class Database:
    """Async database access layer for email storage and retrieval."""

    MAX_EXPORT_LIMIT = 1_000_000
    DEFAULT_BATCH_SIZE = 100

    def __init__(self, config_manager=None, db_path: Optional[Path] = None) -> None:
        """Initialize database with config manager."""
        self.config_manager = config_manager
        self.db_path = db_path or self._resolve_db_path(config_manager)
        self.connection_manager = ConnectionManager(self.db_path)
        self.initialized = False


    ## Path Management

    def _resolve_db_path(self, config_manager) -> Path:
        """Resolve the database file path from config manager."""
        if config_manager:
            import os
            raw_path = config_manager.database.database_path
            return Path(os.path.expanduser(raw_path))
        else:
            return DATABASE_PATH
        
    def get_db_path(self) -> Path:
        """Get the database file path."""
        return self.db_path

    def get_backup_path(self) -> Path:
        """Get the database backup file path."""
        if self.config_manager:
            backup_path = self.config_manager.database.backup_path
            if backup_path:
                return Path(backup_path)
            
        return self.get_db_path().parent / "kernel_backup.db"


    ## Helper Methods

    async def _ensure_initialized(self) -> None:
        """Ensure the database is initialized."""
        if not self.initialized:
            await self._initialize()

    async def _get_validated_schema(self, table: str) -> TableSchema:
        """Get validated schema and ensure initialization."""
        await self._ensure_initialized()
        return self._get_schema(table)

    async def _execute_query(self, query: str, params: Tuple = (), 
                             fetch_one: bool = False, fetch_all: bool = False, 
                             commit: bool = False) -> Optional[List[Dict]]:
        """Execute a query with error handling and result fetching."""
        conn = await self.connection_manager._get_connection()

        if commit:
            await conn.execute(query, params)
            await conn.commit()
            return None
        
        async with conn.execute(query, params) as cursor:
            if fetch_one:
                row = await cursor.fetchone()
                return dict(row) if row else None
            elif fetch_all:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

            return None

    async def _execute_many(self, query: str, param_list: List[Tuple], 
                            commit: bool = True) -> None:
        """Execute a query multiple times with different parameters."""
        conn = await self.connection_manager._get_connection()

        await conn.executemany(query, param_list)
        if commit:
            await conn.commit()


    ## Initialization

    async def _initialize(self) -> None:
        """Create all necessary tables and indexes in the database."""
        if self.initialized:
            return

        try:
            conn = await self.connection_manager._get_connection()

            for schema in SCHEMAS.values():
                await conn.execute(schema.create_table_sql())

                for index_sql in schema.create_indexes_sql():
                    await conn.execute(index_sql)

            await conn.commit()

            self.initialized = True
            logger.info("Database initialised successfully")
        
        except Exception as e:
            logger.error(f"Failed to initialise database: {e}")
            raise DatabaseConnectionError("Failed to initialise database") from e


    ## Validation & Schema Helpers

    def _get_schema(self, table: str) -> TableSchema:
        """Get and validate the schema for a given table."""
        if table not in SCHEMAS:
            raise InvalidTableError(
                f"Invalid table name: {table}",
                details={"table": table, "valid_tables": list(SCHEMAS.keys())}
            )

        return SCHEMAS[table]
    
    def _get_email_field(self, email: Dict[str, Any], field: str) -> Any:
        """Get an email field with fallback options."""
        if field in FIELD_MAPPING:
            for key in FIELD_MAPPING[field]:
                if key in email:
                    return email[key]
            return ""

        return email.get(field, "")

    def _extract_email_values(self, email: Dict[str, Any], schema: TableSchema) -> List[Any]:
        """Extract email values in the correct column order for a schema."""
        values = []
        for column in schema.all_columns:
            if column == "attachments":
                att = email.get("attachments", "")
                values.append(",".join(att) if isinstance(att, (list, tuple)) else att)
            else:
                values.append(self._get_email_field(email, column))
        
        return values
    

    ## Generic Batch Processing

    async def _process_in_batches(
        self,
        items: List[Any],
        batch_size: int,
        process_func: Callable,
        operation_name: str
    ) -> int:
        """Process items in batches using the provided processing function."""
        if not items:
            return 0
        
        processed_count = 0
        total = len(items)

        for i in range(0, total, batch_size):
            batch = items[i:i + batch_size]
            try:
                count = await process_func(batch)
                processed_count += count

                if total > batch_size and (i + batch_size) % (batch_size * 5) == 0:
                    logger.info(f"{operation_name}: Processed {processed_count}/{total} items")

            except Exception as e:
                logger.error(f"{operation_name} error at index {i}: {e}")
                continue
        
        logger.info(f"{operation_name} complete: {processed_count}/{total} items processed")
        return processed_count


    ## CRUD Operations

    @async_log_call
    async def save_email(self, table: str, email: Dict[str, Any]) -> None:
        """Save an email to the specified table (INSERT or REPLACE)."""
        schema = await self._get_validated_schema(table)
        values = self._extract_email_values(email, schema)

        placeholders = QueryBuilder.build_placeholders(len(schema.all_columns))
        query = f"INSERT OR REPLACE INTO {table} ({', '.join(schema.all_columns)}) VALUES ({placeholders})"

        try:
            await self._execute_query(query, tuple(values), fetch_all=False, commit=True)
            logger.debug(f"Saved email {email.get('uid')} to {table}")

        except Exception as e:
            raise DatabaseError(
                f"Failed to save email to {table}",
                details={"uid": email.get("uid"), "error": str(e)}
            ) from e

    @async_log_call
    async def save_emails_batch(self, table: str, emails: List[Dict[str, Any]],
                                batch_size: int = DEFAULT_BATCH_SIZE) -> int:
        """Save multiple emails to the specified table in batches."""
        if not emails:
            return 0

        schema = await self._get_validated_schema(table)

        async def save_batch(batch: List[Dict[str, Any]]) -> int:
            """Helper to save a batch of emails."""
            all_values = [
                tuple(self._extract_email_values(email, schema)) for email in batch
            ]

            placeholders = QueryBuilder.build_placeholders(len(schema.all_columns))
            query = f"INSERT OR REPLACE INTO {table} ({', '.join(schema.all_columns)}) VALUES ({placeholders})"

            await self._execute_query(query, all_values)
            return len(batch)

        return await self._process_in_batches(
            emails, batch_size, save_batch, f"Saving emails to {table}"
        )

    @async_log_call
    async def get_email(self, table: str, uid: str, 
                        include_body: bool = True) -> Optional[Dict]:
        """Retrieve an email by UID from the specified table."""
        schema = await self._get_validated_schema(table)
        columns = QueryBuilder.build_select_columns(schema, include_body)

        query = f"SELECT {columns} FROM {table} WHERE uid = ?"

        try:
            return await self._execute_query(
                query, (str(uid),), fetch_one=True
            )

        except Exception as e:
            raise DatabaseError(
                f"Failed to retrieve email from {table}",
                details={"uid": uid, "error": str(e)}
            ) from e

    @async_log_call
    async def get_emails(self, table: str, limit: int = 50, 
                         offset: int = 0, include_body: bool = False,
                         filters: Optional[Dict[str, Any]] = None) -> List[Dict]:
        """Retrieve multiple emails with optional filters."""
        schema = await self._get_validated_schema(table)
        columns = QueryBuilder.build_select_columns(schema, include_body)

        where_clause, params = QueryBuilder.build_where_clause(filters)
        params.extend([limit, offset])

        query = f"""
            SELECT {columns}
            FROM {table}
            WHERE {where_clause}
            ORDER BY date DESC, time DESC
            LIMIT ? OFFSET ?
        """

        try:
            return await self._execute_query(query, tuple(params))

        except Exception as e:
            raise DatabaseError(
                f"Failed to retrieve emails from {table}",
                details={"error": str(e)}
            ) from e

    @async_log_call
    async def get_emails_by_uids(self, table: str, uids: List[str],
                                 include_body: bool = True,
                                 batch_size: int = DEFAULT_BATCH_SIZE) -> List[Dict]:
        """Retrieve multiple emails by UIDs from the specified table in batches."""
        if not uids:
            return []

        schema = await self._get_validated_schema(table)
        columns = QueryBuilder.build_select_columns(schema, include_body)
        all_emails = []

        async def fetch_batch(batch_uids: List[str]) -> int:
            """Helper to fetch a batch of emails by UIDs."""
            placeholders = QueryBuilder.build_placeholders(len(batch_uids))
            query = f"SELECT {columns} FROM {table} WHERE uid IN ({placeholders})"

            rows = await self._execute_query(query, tuple(batch_uids))
            all_emails.extend(rows)
            return len(batch_uids)
        
        await self._process_in_batches(
            uids, batch_size, fetch_batch, f"Fetching emails from {table}"
        )

        return all_emails

    @async_log_call
    async def delete_email(self, table: str, uid: str) -> None:
        """Delete an email by UID from the specified table."""
        await self._get_validated_schema(table)

        query = f"DELETE FROM {table} WHERE uid = ?"

        try:
            await self._execute_query(query, (str(uid),), fetch_all=False, commit=True)
            logger.debug(f"Deleted email {uid} from {table}")

        except Exception as e:
            raise DatabaseError(
                f"Failed to delete email from {table}",
                details={"uid": uid, "error": str(e)}
            ) from e
        
    @async_log_call
    async def delete_emails_batch(self, table: str, uids: List[str],
                                  batch_size: int = DEFAULT_BATCH_SIZE) -> int:
        """Delete a batch of emails by UID from the specified table."""
        if not uids:
            return 0
        
        await self._get_validated_schema(table)

        async def delete_batch(batch_uids: List[str]) -> int:
            """Helper to delete a batch of emails by UIDs."""
            placeholders = QueryBuilder.build_placeholders(len(batch_uids))
            query = f"DELETE FROM {table} WHERE uid IN ({placeholders})"

            await self._execute_query(query, tuple(batch_uids), fetch_all=False, commit=True)
            return len(batch_uids)
        
        return await self._process_in_batches(
            uids, batch_size, delete_batch, f"Deleting emails from {table}"
        )

    @async_log_call
    async def email_exists(self, table: str, uid: str) -> bool:
        """Check if an email exists in the specified table by UID."""
        await self._get_validated_schema(table)

        query = f"SELECT 1 FROM {table} WHERE uid = ? LIMIT 1"

        try:
            result = await self._execute_query(query, (str(uid),), fetch_one=True)
            return result is not None
            
        except Exception as e:
            raise DatabaseError(
                f"Failed to check email existence in {table}",
                details={"uid": uid, "error": str(e)}
            ) from e
    
    @async_log_call
    async def move_email(self, source_table: str, dest_table: str, 
                         uid: str, **extra_fields) -> None:
        """Move an email from source table to destination table by UID."""
        email = await self.get_email(source_table, uid, include_body=True)
        if not email:
            raise EmailNotFoundError(
                f"Email with UID {uid} not found in {source_table}",
                details={"uid": uid, "table": source_table}
            )

        email.update(extra_fields)
        await self.save_email(dest_table, email)
        await self.delete_email(source_table, uid)
        logger.info(f"Moved email {uid} from {source_table} to {dest_table}")

    @async_log_call
    async def move_emails_batch(self, source_table: str, dest_table: str,
                                   uids: List[str], batch_size: int = 50,
                                   **extra_fields) -> int:
        """Move multiple emails from source table to destination table by UIDs."""
        if not uids:
            return 0
        
        dest_schema = await self._get_validated_schema(dest_table)

        async def move_batch(batch_uids: List[str]) -> int:
            """Helper to move a batch of emails by UIDs."""
            placeholders = QueryBuilder.build_placeholders(len(batch_uids))
            query = f"SELECT * FROM {source_table} WHERE uid IN ({placeholders})"

            emails = await self._execute_query(query, tuple(batch_uids))

            for email in emails:
                email.update(extra_fields)
            
            all_values = [tuple(self._extract_email_values(email, dest_schema)) for email in emails]
            insert_placeholders = QueryBuilder.build_placeholders(len(dest_schema.all_columns))
            insert_query = f"INSERT OR REPLACE INTO {dest_table} ({', '.join(dest_schema.all_columns)}) VALUES ({insert_placeholders})"
            await self._execute_query(insert_query, all_values)

            delete_query = f"DELETE FROM {source_table} WHERE uid IN ({placeholders})"
            await self._execute_query(delete_query, tuple(batch_uids), fetch_all=False, commit=True)

            return len(emails)
        
        return await self._process_in_batches(
            uids, batch_size, move_batch, f"Moving emails from {source_table} to {dest_table}"
        )

    @async_log_call
    async def update_field(self, table: str, uid: str, field: str, value: Any) -> None:
        """Update a specific field of an email by UID in the specified table."""
        schema = await self._get_validated_schema(table)
        
        if field not in schema.all_columns:
            raise InvalidTableError(
                f"Invalid field for {table} table: {field}",
                details={"field": field, "table": table, "allowed_fields": schema.all_columns}
            )
        
        query = f"UPDATE {table} SET {field} = ? WHERE uid = ?"

        try:
            await self._execute_query(query, (value, str(uid)), fetch_all=False, commit=True)
            logger.debug(f"Updated field {field} of email {uid} in {table}")

        except Exception as e:
            raise DatabaseError(
                f"Failed to update field {field} in {table}",
                details={"uid": uid, "field": field, "error": str(e)}
            ) from e
        
    @async_log_call
    async def update_fields_batch(self, table: str, updates: List[Dict[str, Any]],
                                  batch_size: int = 100) -> int:
        """Update multiple fields of emails in the specified table in batches."""
        if not updates:
            return 0

        schema = await self._get_validated_schema(table)

        for update in updates:
            if update["field"] not in schema.all_columns:
                raise InvalidTableError(
                    f"Invalid field: {update['field']}",
                    details={"field": update["field"], "table": table}
                )

        updates_by_field = {}
        for update in updates:
            field = update["field"]
            if field not in updates_by_field:
                updates_by_field[field] = []

            updates_by_field[field].append((update["value"], str(update["uid"])))

        total_updated = 0
        for field, values in updates_by_field.items():
            query = f"UPDATE {table} SET {field} = ? WHERE uid = ?"
            await self._execute_many(query, values)
            total_updated += len(values)

        logger.info(f"Batch update complete: {total_updated} updates in {table}")
        return total_updated


    ## Search Operations

    @async_log_call
    async def search(self, table: str, keyword: str, limit: int = 50,
                     fields: Optional[List[str]] = None) -> List[Dict]:
        """Search emails in the specified table by keyword."""
        schema = await self._get_validated_schema(table)
        columns = QueryBuilder.build_select_columns(schema, include_body=False)

        if fields is None:
            fields = ["subject", "sender", "recipient", "body"]

        where_clauses = [f"{field} LIKE ?" for field in fields]
        where_sql = " OR ".join(where_clauses)
        params = [f"%{keyword}%" for _ in fields] + [limit]

        query = f"""
            SELECT {columns}
            FROM {table}
            WHERE {where_sql}
            ORDER BY date DESC, time DESC
            LIMIT ?
        """

        try:
            return await self._execute_query(query, tuple(params))
            
        except Exception as e:
            raise DatabaseError(
                f"Failed to search emails in {table}",
                details={"keyword": keyword, "error": str(e)}
            ) from e

    @async_log_call
    async def search_all_tables(self, keyword: str, limit: int = 50) -> List[Dict]:
        """Search emails across all tables by keyword."""
        await self._ensure_initialized()

        union_parts = []
        params = []

        for table_name, schema in SCHEMAS.items():
            columns = QueryBuilder.build_select_columns(schema, include_body=False)
            where_clauses = [
                "subject LIKE ?",
                "sender LIKE ?",
                "recipient LIKE ?",
                "body LIKE ?"
            ]
            where_sql = " OR ".join(where_clauses)

            union_parts.append(f"""
                SELECT {columns}, '{table_name}' AS source_table
                FROM {table_name}
                WHERE {where_sql}
            """)

            params.extend([f"%{keyword}%"] * 4)

        query = " UNION ALL ".join(union_parts) + " ORDER BY date DESC, time DESC LIMIT ?"
        params.append(limit)

        try:
            return await self._execute_query(query, tuple(params))

        except Exception as e:
            raise DatabaseError(
                "Failed to search emails across all tables",
                details={"keyword": keyword, "error": str(e)}
            ) from e

    @async_log_call
    async def search_with_attachments(self, table: str = "inbox", limit: int = 50) -> List[Dict]:
        """Search emails with attachments in the specified table."""
        schema = await self._get_validated_schema(table)
        columns = QueryBuilder.build_select_columns(schema, include_body=False)

        query = f"""
            SELECT {columns}
            FROM {table}
            WHERE attachments IS NOT NULL AND attachments != ''
            ORDER BY date DESC, time DESC
            LIMIT ?
        """

        try:
            return await self._execute_query(query, (limit,))

        except Exception as e:
            raise DatabaseError(
                f"Failed to search emails with attachments in {table}",
                details={"error": str(e)}
            ) from e


    ## Utility Operations

    @async_log_call
    async def get_highest_uid(self) -> Optional[int]:
        """Get the highest UID from the inbox table."""
        await self._ensure_initialized()

        query = "SELECT MAX(CAST(uid AS INTEGER)) AS max_uid FROM inbox"

        try:
            result = await self._execute_query(query, (), fetch_one=True)
            return int(result["max_uid"]) if result and result["max_uid"] is not None else None
        
        except Exception as e:
            logger.error(f"Failed to get highest UID: {e}")
            return None

    @async_log_call
    async def get_email_count(self, table: str) -> int:
        """Get the total number of emails in the specified table."""
        await self._get_validated_schema(table)

        query = f"SELECT COUNT(*) AS count FROM {table}"

        try:
            result = await self._execute_query(query, (), fetch_one=True)
            return result["count"] if result else 0
            
        except Exception as e:
            raise DatabaseError(
                f"Failed to get email count from {table}",
                details={"error": str(e)}
            ) from e
    

    ## Backup & Export Operations

    async def backup(self, backup_path: Optional[Path] = None) -> Path:
        """Create a backup of the database."""
        from datetime import datetime
        import shutil

        try:
            if backup_path is None:
                backup_dir = self.get_backup_path().parent
                backup_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = backup_dir / f"kernel_backup_{timestamp}.db"
            else:
                backup_path = Path(backup_path)
                backup_path.parent.mkdir(parents=True, exist_ok=True)

            await self.connection_manager.close()

            shutil.copy2(self.get_db_path(), backup_path)

            logger.info(f"Database backed up to: {backup_path}")
            return backup_path
        
        except Exception as e:
            raise DatabaseError(
                "Failed to backup database",
                details={"error": str(e)}
            ) from e
        
        finally:
            try:
                await self.connection_manager._get_connection()
            except Exception as e:
                logger.error(f"Failed to reconnect after backup: {e}")

    async def export_to_csv(self, export_dir: Path, 
                            tables: Optional[List[str]] = None) -> List[Path]:
        """Export specified tables to CSV files."""
        await self._ensure_initialized()

        try:
            export_dir = Path(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)

            if tables is None:
                tables = list(SCHEMAS.keys())

            exported_files = []

            for table in tables:
                if table not in SCHEMAS:
                    logger.warning(f"Skipping invalid table for export: {table}")
                    continue

                emails = await self.get_emails(table, limit=self.MAX_EXPORT_LIMIT, include_body=True)

                if not emails:
                    logger.info(f"No emails to export in table: {table}")
                    continue
                
                csv_path = export_dir / f"{table}.csv"

                await self._write_csv(csv_path, emails)
                exported_files.append(csv_path)
                logger.info(f"Exported {len(emails)} emails from {table} to {csv_path}")

            return exported_files
        
        except Exception as e:
            raise DatabaseError(
                "Failed to export database to CSV",
                details={"error": str(e)}
            ) from e
        
    async def _write_csv(self, csv_path: Path, emails: List[Dict]) -> None:
        """Write emails to a CSV file."""
        import asyncio
        import csv

        def write():
            with open(csv_path, mode="w", newline="", encoding="utf-8") as csvfile:
                if emails:
                    writer = csv.DictWriter(csvfile, fieldnames=emails[0].keys())
                    writer.writeheader()
                    writer.writerows(emails)
        
        await asyncio.to_thread(write)

    async def delete_database(self) -> None:
        """Delete the entire database file."""
        try:
            await self.connection_manager.close()

            db_path = self.get_db_path()
            if db_path.exists():
                db_path.unlink()
                logger.warning(f"Database file deleted: {db_path}")

        except Exception as e:
            raise DatabaseError(
                "Failed to delete database",
                details={"error": str(e)}
            ) from e


    ## Health Check & Monitoring

    async def health_check(self, quick: bool = False) -> bool:
        """Perform a health check on the database."""
        return await self.connection_manager.health_check(quick)
    
    async def is_healthy(self) -> bool:
        """Check if the database is healthy."""
        return await self.connection_manager.is_healthy()

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
    
    ## Context Management

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_initialized()

        return self
    
    async def __aexit__(self, exc_type, exc_value, traceback):
        """Async context manager exit."""
        await self.connection_manager.close()

    @asynccontextmanager
    async def transaction(self):
        """Transaction context manager for atomic operations."""
        await self._ensure_initialized()
        conn = await self.connection_manager._get_connection()

        try:
            await conn.execute("BEGIN;")
            yield conn
            await conn.commit()

        except Exception:
            await conn.rollback()
            raise


## Singleton Instance

_db_instance = None

def get_database(config_manager=None, db_path: Optional[Path] = None) -> Database:
    """Get or create singleton database instance."""
    global _db_instance

    if _db_instance is None:
        if config_manager is None:
            from src.utils.config_manager import ConfigManager
            config_manager = ConfigManager()

        _db_instance = Database(config_manager, db_path)
        logger.debug("Database singleton instance created")

    elif config_manager is not None or db_path is not None:
        _db_instance = Database(config_manager, db_path)
        logger.debug("Database singleton instance reconfigured")

    return _db_instance

def reset_database() -> None:
    """Reset the singleton database instance (for testing/reconfiguration)."""
    global _db_instance

    if _db_instance:
        ## Caller must handle closing existing connections
        _db_instance = None
        logger.debug("Database singleton instance reset")
                