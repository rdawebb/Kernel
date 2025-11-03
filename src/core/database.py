"""Unified database access layer for email storage and retrieval."""

import aiosqlite
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    
    @property
    def select_columns(self) -> str:
        """Columns for SELECT statements."""

        cols = [
            "uid",
            "subject",
            "sender as 'from'",
            "recipient as 'to'",
            "date",
            "time",
            "attachments"
        ]

        cols.extend(self.additional_columns)

        return ", ".join(cols)
    
    @property
    def insert_columns(self) -> str:
        """Columns for INSERT statements."""

        return ", ".join(self.all_columns)
    
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
            f"CREATE INDEX IF NOT EXISTS idx_{self.name}_uid ON {self.name} (uid);",
            f"CREATE INDEX IF NOT EXISTS idx_{self.name}_date ON {self.name} (date DESC, time DESC);",
            f"CREATE INDEX IF NOT EXISTS idx_{self.name}_sender ON {self.name} (sender);",
        ]

        if "flagged" in self.additional_columns:
            indexes.append(f"CREATE INDEX IF NOT EXISTS idx_{self.name}_flagged ON {self.name} (flagged) WHERE flagged = 1;")

        return indexes


SCHEMAS = {
    "inbox": TableSchema("inbox", ["flagged"]),
    "sent": TableSchema("sent", ["sent_status", "send_at"]),
    "drafts": TableSchema("drafts"),
    "trash": TableSchema("trash", ["deleted_at"]),
}


## Database Access Layer

class Database:
    """Async database access layer for email storage and retrieval."""

    def __init__(self, config_manager=None, db_path: Optional[Path] = None) -> None:
        """Initialize database with config manager."""

        self.config_manager = config_manager
        self.db_path = db_path or self._resolve_db_path(config_manager)
        self._connection = None
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


    ## Connection Management

    async def _get_connection(self) -> aiosqlite.Connection:
        """Get or create an database connection."""

        if self._connection is None:
            await self._connect()

        return self._connection
    
    async def _connect(self) -> None:
        """Establish a new database connection."""

        try:
            self.db_path = self.get_db_path()
            self.db_path.mkdir(parents=True, exist_ok=True)

            self._connection = await aiosqlite.connect(
                str(self.db_path),
                timeout=30.0
            )

            await self._connection.execute("PRAGMA foreign_keys = ON;")
            await self._connection.execute("PRAGMA journal_mode = WAL;")

            self._connection.row_factory = aiosqlite.Row
            logger.debug(f"Database connected: {self.db_path}")

        except Exception as e:
            raise DatabaseConnectionError(
                "Failed to connect to database",
                details={"db_path": str(self.db_path), "error": str(e)}
            ) from e

    async def close_connection(self) -> None:
        """Close the database connection."""

        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.debug("Database connection closed")


    ## Initialization

    async def __initialize(self) -> None:
        """Create all necessary tables and indexes in the database."""

        if self.initialized:
            return

        try:
            conn = await self._get_connection()

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


    ## Validation

    def _validate_table(self, table: str) -> None:
        """Validate if the table name is valid."""

        if table not in SCHEMAS:
            raise InvalidTableError(
                f"Invalid table name: {table}",
                details={"table": table, "valid_tables": list(SCHEMAS.keys())}
            )


    def _get_schema(self, table: str) -> TableSchema:
        """Get the schema for a given table."""

        self._validate_table(table)
        return SCHEMAS[table]


    ## CRUD Operations

    @async_log_call
    async def save_email(self, table: str, email: Dict[str, Any]) -> None:
        """Save an email to the specified table (INSERT or REPLACE)."""

        if not self.initialized:
            await self.__initialize()

        schema = self._get_schema(table)

        values = []
        for col in schema.all_columns:
            if col == "attachments":
                att = email.get("attachments", "")
                values.append(",".join(att) if isinstance(att, (list, tuple)) else att)
            elif col == "sender":
                values.append(email.get("sender") or email.get("from", ""))
            elif col == "recipient":
                values.append(email.get("recipient") or email.get("to", ""))
            else:
                values.append(email.get(col, ""))

        placeholders = ", ".join(["?" for _ in schema.all_columns])
        query = f"INSERT OR REPLACE INTO {table} ({schema.insert_columns}) VALUES ({placeholders})"

        try:
            conn = await self._get_connection()
            await conn.execute(query, tuple(values))
            await conn.commit()
            logger.debug(f"Saved email {email.get('uid')} to {table}")

        except Exception as e:
            raise DatabaseError(
                f"Failed to save email to {table}",
                details={"uid": email.get("uid"), "error": str(e)}
            ) from e

    @async_log_call
    async def get_email(self, table: str, uid: str, include_body: bool = True) -> Optional[Dict]:
        """Retrieve an email by UID from the specified table."""

        if not self.initialized:
            await self.__initialize()

        schema = self._get_schema(table)
        columns = self._get_columns(schema, include_body)

        query = f"SELECT {columns} FROM {table} WHERE uid = ?"

        try:
            conn = await self._get_connection()
            async with conn.execute(query, (str(uid),)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

        except Exception as e:
            raise DatabaseError(
                f"Failed to retrieve email from {table}",
                details={"uid": uid, "error": str(e)}
            ) from e

    @async_log_call
    async def get_emails(self, table: str, limit: int = 50,
                   include_body: bool = False, offset: int = 0) -> List[Dict]:
        """Retrieve multiple emails from the specified table."""

        if not self.initialized:
            await self.__initialize()

        schema = self._get_schema(table)
        columns = self._get_columns(schema, include_body)

        query = f"""
            SELECT {columns}
            FROM {table}
            ORDER BY date DESC, time DESC
            LIMIT ? OFFSET ?
        """

        try:
            conn = await self._get_connection()
            async with conn.execute(query, (limit, offset)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

        except Exception as e:
            raise DatabaseError(
                f"Failed to retrieve emails from {table}",
                details={"error": str(e)}
            ) from e

    @async_log_call
    async def get_filtered_emails(self, table: str, limit: int = 50,
                              is_flagged: Optional[bool] = None,
                              is_read: Optional[bool] = None,
                              has_attachments: bool = None) -> List[Dict]:
        """Retrieve emails from the specified table with filters."""

        if not self.initialized:
            await self.__initialize()

        schema = self._get_schema(table)
        columns = self._get_columns(schema, include_body=False)

        conditions = []
        params = []

        if is_flagged is not None:
            conditions.append("flagged = ?")
            params.append(1 if is_flagged else 0)

        if is_read is not None:
            conditions.append("read = ?")
            params.append(1 if is_read else 0)

        if has_attachments is not None:
            conditions.append("attachments IS NOT NULL AND attachments != ''")

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)

        query = f"""
            SELECT {columns}
            FROM {table}
            WHERE {where_clause}
            ORDER BY date DESC, time DESC
            LIMIT ?
        """

        try:
            conn = await self._get_connection()
            async with conn.execute(query, tuple(params)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

        except Exception as e:
            raise DatabaseError(
                f"Failed to retrieve filtered emails from {table}",
                details={"error": str(e)}
            ) from e

    @async_log_call
    async def delete_email(self, table: str, uid: str) -> None:
        """Delete an email by UID from the specified table."""

        if not self.initialized:
            await self.__initialize()

        self._validate_table(table)

        query = f"DELETE FROM {table} WHERE uid = ?"

        try:
            conn = await self._get_connection()
            await conn.execute(query, (str(uid),))
            await conn.commit()
            logger.debug(f"Deleted email {uid} from {table}")

        except Exception as e:
            raise DatabaseError(
                f"Failed to delete email from {table}",
                details={"uid": uid, "error": str(e)}
            ) from e

    @async_log_call
    async def email_exists(self, table: str, uid: str) -> bool:
        """Check if an email exists in the specified table by UID."""

        if not self.initialized:
            await self.__initialize()

        self._validate_table(table) 

        query = f"SELECT 1 FROM {table} WHERE uid = ? LIMIT 1"

        try:
            conn = await self._get_connection()
            async with conn.execute(query, (str(uid),)) as cursor:
                row = await cursor.fetchone()
                return row is not None
            
        except Exception as e:
            raise DatabaseError(
                f"Failed to check email existence in {table}",
                details={"uid": uid, "error": str(e)}
            ) from e
    
    @async_log_call
    async def move_email(self, source_table: str, dest_table: str, uid: str, **extra_fields) -> None:
        """Move an email from source table to destination table by UID."""

        if not self.initialized:
            await self.__initialize()

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
    async def update_field(self, table: str, uid: str, field: str, value: Any) -> None:
        """Update a specific field of an email by UID in the specified table."""

        if not self.initialized:
            await self.__initialize()

        schema = self._get_schema(table)
        
        allowed_fields = schema.all_columns
        if field not in allowed_fields:
            raise InvalidTableError(
                f"Invalid field for {table} table: {field}",
                details={"field": field, "table": table, "allowed_fields": allowed_fields}
            )
        
        query = f"UPDATE {table} SET {field} = ? WHERE uid = ?"

        try:
            conn = await self._get_connection()
            await conn.execute(query, (value, str(uid)))
            await conn.commit()
            logger.debug(f"Updated field {field} of email {uid} in {table}")

        except Exception as e:
            raise DatabaseError(
                f"Failed to update field {field} in {table}",
                details={"uid": uid, "field": field, "error": str(e)}
            ) from e


    ## Search Operations

    @async_log_call
    async def search(self, table: str, keyword: str, limit: int = 50,
                     fields: List[str] = None) -> List[Dict]:
        """Search emails in the specified table by keyword."""

        if not self.initialized:
            await self.__initialize()

        schema = self._get_schema(table)
        
        if fields is None:
            fields = ["subject", "sender", "recipient", "body"]

        where_clauses = [f"{field} LIKE ?" for field in fields]
        where_sql = " OR ".join(where_clauses)
        params = [f"%{keyword}%" for _ in fields] + [limit]

        query = f"""
            SELECT {schema.select_columns}
            FROM {table}
            WHERE {where_sql}
            ORDER BY date DESC, time DESC
            LIMIT ?
        """

        try:
            conn = await self._get_connection()
            async with conn.execute(query, tuple(params)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
            
        except Exception as e:
            raise DatabaseError(
                f"Failed to search emails in {table}",
                details={"keyword": keyword, "error": str(e)}
            ) from e

    @async_log_call
    async def search_all_tables(self, keyword: str, limit: int = 50) -> List[Dict]:
        """Search emails across all tables by keyword."""

        if not self.initialized:
            await self.__initialize()

        union_parts = []
        params = []

        for table in SCHEMAS:
            schema = SCHEMAS[table]
            where_clauses = [
                "subject LIKE ?",
                "sender LIKE ?",
                "recipient LIKE ?",
                "body LIKE ?"
            ]
            where_sql = " OR ".join(where_clauses)

            union_parts.append(f"""
                SELECT {schema.select_columns}, '{table}' AS source_table
                FROM {table}
                WHERE {where_sql}
            """)

            params.extend([f"%{keyword}%"] * 4)

        query = " UNION ALL ".join(union_parts) + " ORDER BY date DESC, time DESC LIMIT ?"
        params.append(limit)

        try:
            conn = await self._get_connection()
            async with conn.execute(query, tuple(params)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
            
        except Exception as e:
            raise DatabaseError(
                "Failed to search emails across all tables",
                details={"keyword": keyword, "error": str(e)}
            ) from e

    @async_log_call
    async def search_with_attachments(self, table: str = "inbox", limit: int = 50) -> List[Dict]:
        """Search emails with attachments in the specified table."""

        if not self.initialized:
            await self.__initialize()

        schema = self._get_schema(table)

        query = f"""
            SELECT {schema.select_columns}
            FROM {table}
            WHERE attachments IS NOT NULL AND attachments != ''
            ORDER BY date DESC, time DESC
            LIMIT ?
        """

        try:
            conn = await self._get_connection()
            async with conn.execute(query, (limit,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

        except Exception as e:
            raise DatabaseError(
                f"Failed to search emails with attachments in {table}",
                details={"error": str(e)}
            ) from e


    ## Utility Operations

    @async_log_call
    async def get_highest_uid(self) -> Optional[int]:
        """Get the highest UID from the inbox table."""

        if not self.initialized:
            await self.__initialize()

        query = "SELECT MAX(CAST(uid AS INTEGER)) AS max_uid FROM inbox"

        try:
            conn = await self._get_connection()
            async with conn.execute(query) as cursor:
                row = await cursor.fetchone()
                
                if row and row[0] is not None:
                    return int(row[0])
                
                return None
        
        except Exception as e:
            logger.error(f"Failed to get highest UID: {e}")
            return None

    @async_log_call
    async def get_email_count(self, table: str) -> int:
        """Get the total number of emails in the specified table."""

        if not self.initialized:
            await self.__initialize()

        self._validate_table(table)
        
        query = f"SELECT COUNT(*) AS count FROM {table}"

        try:
            conn = await self._get_connection()
            async with conn.execute(query) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0
            
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

            if self._connection:
                await self.close_connection()

            shutil.copy2(self.get_db_path(), backup_path)

            logger.info(f"Database backed up to: {backup_path}")
            return backup_path
        
        except Exception as e:
            raise DatabaseError(
                "Failed to backup database",
                details={"error": str(e)}
            ) from e
        
        finally:
            if not self._connection:
                await self._connect()

    async def export_to_csv(self, export_dir: Path, tables: List[str] = None) -> List[Path]:
        """Export specified tables to CSV files."""

        if not self.initialized:
            await self.__initialize()

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

                emails = await self.get_emails(table, limit=1000000, include_body=True)

                if not emails:
                    logger.info(f"No emails to export in table: {table}")
                    continue
                
                csv_path = export_dir / f"{table}.csv"

                await self._write_csv(csv_path, emails)
                exported_files.append(csv_path)

            return exported_files
        
        except Exception as e:
            raise DatabaseError(
                "Failed to export database to CSV",
                details={"error": str(e)}
            ) from e
        
    async def _write_csv(self, csv_path: Path, emails: List[Dict]) -> None:
        """Write emails to a CSV file."""

        import csv

        def write():
            with open(csv_path, mode="w", newline="", encoding="utf-8") as csvfile:
                if emails:
                    writer = csv.DictWriter(csvfile, fieldnames=emails[0].keys())
                    writer.writeheader()
                    writer.writerows(emails)
        
        import asyncio
        await asyncio.to_thread(write)

    async def delete_database(self) -> None:
        """Delete the entire database file."""

        try:
            await self.close_connection()

            db_path = self.get_db_path()
            if db_path.exists():
                db_path.unlink()
                logger.warning(f"Database file deleted: {db_path}")

        except Exception as e:
            raise DatabaseError(
                "Failed to delete database",
                details={"error": str(e)}
            ) from e

    
    ## Helper Methods

    def _get_columns(self, schema: TableSchema, include_body: bool) -> str:
        """Get the appropriate columns for SELECT statements."""

        columns = schema.select_columns
        
        if not include_body:
            columns = ", ".join([
                col for col in columns.split(", ")
                if "body" not in col.lower()
            ])

        return columns

    
    ## Context Management

    async def __aenter__(self):
        """Async context manager entry."""

        if not self.initialized:
            await self.__initialize()

        return self
    
    async def __aexit__(self, exc_type, exc_value, traceback):
        """Async context manager exit."""

        await self.close_connection()


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
                