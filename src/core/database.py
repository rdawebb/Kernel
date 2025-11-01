"""Unified database access layer for email storage and retrieval."""

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.db_manager import DatabaseManager
from src.utils.error_handling import (
    DatabaseConnectionError,
    DatabaseError,
    EmailNotFoundError,
    InvalidTableError,
)
from src.utils.log_manager import get_logger
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


SCHEMAS = {
    "inbox": TableSchema("inbox", ["flagged"]),
    "sent": TableSchema("sent", ["sent_status", "send_at"]),
    "drafts": TableSchema("drafts"),
    "trash": TableSchema("trash", ["deleted_at"]),
}


## Database Access Layer

class Database:
    """Database access layer for email storage and retrieval."""

    def __init__(self, config_manager=None, db_manager: Optional[DatabaseManager] = None) -> None:
        """Initialize database with config manager and db manager."""

        self.config_manager = config_manager

        if db_manager:
            self.db_manager = db_manager
        else:
            db_path = self._resolve_db_path(config_manager)
            self.db_manager = DatabaseManager(db_path)

        self.initialized = False
        self.__initialize()


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

        return self.db_manager.db_path
    

    def get_backup_path(self) -> Path:
        """Get the database backup file path."""

        if self.config_manager:
            backup_path = self.config_manager.database.backup_path
            if backup_path:
                return Path(backup_path)
            
        return self.get_db_path().parent / "kernel_backup.db"

        
    ## Initialization

    def __initialize(self) -> None:
        """Create all necessary tables in the database."""

        if self.initialized:
            return

        try:
            for schema in SCHEMAS.values():
                self.db_manager.execute(schema.create_table_sql(), commit=True)

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

    def save_email(self, table: str, email: Dict[str, Any]) -> None:
        """Save an email to the specified table (INSERT or REPLACE)."""

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

        self.db_manager.execute(query, tuple(values), commit=True)


    def get_email(self, table: str, uid: str, include_body: bool = True) -> Optional[Dict]:
        """Retrieve an email by UID from the specified table."""

        schema = self._get_schema(table)
        columns = self._get_columns(schema, include_body)

        query = f"SELECT {columns} FROM {table} WHERE uid = ?"

        return self.db_manager.execute(query, (str(uid),), fetch_one=True)


    def get_emails(self, table: str, limit: int = 50,
                   include_body: bool = False, offset: int = 0) -> List[Dict]:
        """Retrieve multiple emails from the specified table."""

        schema = self._get_schema(table)
        columns = self._get_columns(schema, include_body)

        query = f"""
            SELECT {columns}
            FROM {table}
            ORDER BY date DESC, time DESC
            LIMIT ? OFFSET ?
        """

        return self.db_manager.execute(query, (limit, offset))


    def delete_email(self, table: str, uid: str) -> None:
        """Delete an email by UID from the specified table."""

        self._validate_table(table)

        query = f"DELETE FROM {table} WHERE uid = ?"

        self.db_manager.execute(query, (str(uid),), commit=True)


    def email_exists(self, table: str, uid: str) -> bool:
        """Check if an email exists in the specified table by UID."""

        self._validate_table(table) 

        query = f"SELECT 1 FROM {table} WHERE uid = ? LIMIT 1"

        return self.db_manager.execute(query, (str(uid),), fetch_one=True) is not None
    

    def move_email(self, source_table: str, dest_table: str, uid: str) -> None:
        """Move an email from source table to destination table by UID."""

        email = self.get_email(source_table, uid, include_body=True)
        if not email:
            raise EmailNotFoundError(
                f"Email with UID {uid} not found in {source_table}",
                details={"uid": uid, "table": source_table}
            )

        if dest_table == "trash":
            from datetime import datetime
            email["deleted_at"] = datetime.now().strftime("%Y-%m-%d")
        
        self.save_email(dest_table, email)
        self.delete_email(source_table, uid)


    def update_field(self, table: str, uid: str, field: str, value: Any) -> None:
        """Update a specific field of an email by UID in the specified table."""

        schema = self._get_schema(table)
        
        allowed_fields = schema.all_columns
        if field not in allowed_fields:
            raise InvalidTableError(
                f"Invalid field for {table} table: {field}",
                details={"field": field, "table": table, "allowed_fields": allowed_fields}
            )
        
        query = f"UPDATE {table} SET {field} = ? WHERE uid = ?"

        self.db_manager.execute(query, (value, str(uid)), commit=True)


    ## Search Operations

    def search(self, table: str, keyword: str, limit: int = 50,
               fields: List[str] = None) -> List[Dict]:
        """Search emails in the specified table by keyword."""

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

        return self.db_manager.execute(query, tuple(params))


    def search_all_tables(self, keyword: str, limit: int = 50) -> List[Dict]:
        """Search emails across all tables by keyword."""

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

        return self.db_manager.execute(query, tuple(params))


    def search_flagged(self, flagged: bool = True, limit: int = 50) -> List[Dict]:
        """Search flagged emails in the inbox."""

        schema = self._get_schema("inbox")

        query = f"""
            SELECT {schema.select_columns}
            FROM inbox
            WHERE flagged = ?
            ORDER BY date DESC, time DESC
            LIMIT ?
        """

        return self.db_manager.execute(query, (1 if flagged else 0, limit))


    def search_with_attachments(self, table: str = "inbox", limit: int = 50) -> List[Dict]:
        """Search emails with attachments in the specified table."""

        schema = self._get_schema(table)

        query = f"""
            SELECT {schema.select_columns}
            FROM {table}
            WHERE attachments IS NOT NULL AND attachments != ''
            ORDER BY date DESC, time DESC
            LIMIT ?
        """

        return self.db_manager.execute(query, (limit,))


    def get_pending_emails(self) -> List[Dict]:
        """Retrieve emails pending to be sent from the sent table."""

        schema = self._get_schema("sent")

        query = f"""
            SELECT {schema.select_columns}
            FROM sent
            WHERE sent_status = 'pending'
            ORDER BY send_at ASC
        """

        return self.db_manager.execute(query)


    ## Utility Operations

    def get_highest_uid(self) -> Optional[int]:
        """Get the highest UID from the inbox table."""

        query = "SELECT MAX(CAST(uid AS INTEGER)) AS max_uid FROM inbox"

        result = self.db_manager.execute(query, fetch_one=True)

        return int(result["max_uid"]) if result and result["max_uid"] else None


    def get_email_count(self, table: str) -> int:
        """Get the total number of emails in the specified table."""

        self._validate_table(table)
        
        query = f"SELECT COUNT(*) AS count FROM {table}"

        result = self.db_manager.execute(query, fetch_one=True)

        return result["count"] if result else 0
    

    ## Backup & Export Operations

    def backup(self, backup_path: Optional[Path] = None) -> Path:
        """Create a backup of the database."""

        from datetime import datetime

        try:
            if backup_path is None:
                backup_dir = self.get_backup_path()
                backup_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = backup_dir / f"kernel_backup_{timestamp}.db"
            else:
                backup_path = Path(backup_path)
                backup_path.parent.mkdir(parents=True, exist_ok=True)

            with self.db_manager.connection() as source_conn:
                with sqlite3.connect(backup_path) as dest_conn:
                    source_conn.backup(dest_conn)

            logger.info(f"Database backed up to {backup_path}")

            return backup_path
        
        except sqlite3.DatabaseError as e:
            raise DatabaseConnectionError("Failed to backup database") from e
        except Exception as e:
            raise DatabaseError("Failed to backup database") from e
    
    
    def export_to_csv(self, export_dir: Path, tables: List[str] = None) -> List[Path]:
        """Export specified tables to CSV files."""

        import csv

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
                
                emails = self.get_emails(table, limit=1000000, include_body=True)

                if not emails:
                    logger.info(f"No emails to export in table: {table}")
                    continue
                
                csv_path = export_dir / f"{table}.csv"

                with open(csv_path, mode="w", newline="", encoding="utf-8") as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=emails[0].keys())
                    writer.writeheader()
                    writer.writerows(emails)
                
                exported_files.append(csv_path)

            return exported_files
        
        except OSError as e:
            raise DatabaseError("Failed to export database to CSV") from e
        except Exception as e:
            raise DatabaseError("Failed to export database to CSV") from e
    

    def delete_database(self) -> None:
        """Delete the entire database file."""

        try:
            self.db_manager.close()
            db_path = self.get_db_path()
            if db_path.exists():
                db_path.unlink()
                logger.warning(f"Database deleted: {db_path}")
        except Exception as e:
            raise DatabaseError("Failed to delete database") from e

    
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

    
    def close(self) -> None:
        """Close database connections."""

        if self.db_manager:
            self.db_manager.close()
            logger.info("Database connections closed")


## Singleton Instance

_db_instance = None

def get_database(config_manager=None, db_manager: Optional[DatabaseManager] = None) -> Database:
    """Get or create singleton database instance."""

    global _db_instance

    if _db_instance is None:
        if config_manager is None:
            from src.utils.config_manager import ConfigManager
            config_manager = ConfigManager()

        _db_instance = Database(config_manager, db_manager)
        logger.debug("Database singleton instance created")

    elif config_manager is not None or db_manager is not None:
        _db_instance = Database(config_manager, db_manager)
        logger.debug("Database singleton instance reconfigured")

    return _db_instance

def reset_database() -> None:
    """Reset the singleton database instance (for testing/reconfiguration)."""

    global _db_instance

    if _db_instance:
        _db_instance.close()
        _db_instance = None
        logger.debug("Database singleton instance reset")
                