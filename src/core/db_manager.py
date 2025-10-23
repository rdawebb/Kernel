"""Database management layer - handles connections, transactions, and low-level operations"""

import sqlite3
import pandas as pd
from pathlib import Path
from contextlib import contextmanager
from ..utils.config_manager import ConfigManager
from ..utils.log_manager import get_logger, log_call

logger = get_logger(__name__)

class DatabaseManager:
    """Handles database connections and low-level operations"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
    
    def get_config_path(self, path_key):
        """Get a path from config by key name"""
        return Path(self.config_manager.get_config(path_key))

    def get_db_path(self):
        return self.get_config_path("database.database_path")

    def get_backup_path(self):
        backup_path = self.config_manager.get_config("database.backup_path")
        if backup_path is None:
            # Default to exports directory
            db_path = self.get_db_path()
            return db_path.parent / "exports" / "backup.db"
        return Path(backup_path)

    @log_call
    def get_db_connection(self):
        try:
            db_path = self.get_db_path()
            db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            print("Unable to connect to the database. Please check your configuration and try again.")
            return None

    @contextmanager
    def db_connection(self):
        """Context manager for database connections with automatic cleanup"""
        conn = self.get_db_connection()
        try:
            yield conn
        finally:
            if conn:
                conn.close()

    def execute_query(self, query, params=(), fetch_one=False, fetch_all=True, commit=False):
        """Execute a database query with automatic connection management"""
        with self.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            if commit:
                conn.commit()
            
            if fetch_one:
                return cursor.fetchone()
            elif fetch_all:
                return cursor.fetchall()
            return cursor

    def convert_emails_to_dict_list(self, emails):
        """Convert cursor results to list of dictionaries"""
        return [dict(email) for email in emails]

    @log_call
    def backup_db(self, backup_path=None):
        try:
            db_path = self.get_db_path()
            if backup_path is None:
                backup_path = self.get_backup_path()
            else:
                backup_path = Path(backup_path)
            
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            with sqlite3.connect(db_path) as source_conn:
                with sqlite3.connect(backup_path) as dest_conn:
                    source_conn.backup(dest_conn)
            
            logger.info(f"Database backup created at {backup_path}")
            return str(backup_path)
                    
        except Exception as e:
            logger.error(f"Failed to backup database: {e}")
            print("Unable to backup the database. Please check your configuration and try again.")
            return None

    @log_call
    def export_db_to_csv(self, export_dir, tables=None):
        try:
            export_path = Path(export_dir)
            export_path.mkdir(parents=True, exist_ok=True)
            
            if tables is None:
                tables = ["inbox", "sent_emails", "drafts", "deleted_emails"]
            
            exported_files = []
            
            with self.db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                existing_tables = {row[0] for row in cursor.fetchall()}

                for table in tables:
                    if table in existing_tables:
                        df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
                        csv_file = export_path / f"{table}.csv"
                        df.to_csv(csv_file, index=False)
                        exported_files.append(str(csv_file))
                        logger.info(f"Exported {len(df)} rows from {table}")
                        print(f"Exported {len(df)} rows from {table} to {csv_file}")
                    else:
                        logger.debug(f"Table {table} does not exist in the database. Skipping export.")
                        print(f"Table {table} does not exist in the database. Skipping export.")
            
            logger.info(f"Database export completed: {len(exported_files)} tables exported")
            return exported_files
        
        except Exception as e:
            logger.error(f"Failed to export database to CSV: {e}")
            print("Unable to export the database to CSV. Please check your configuration and try again.")
            return None

    @log_call
    def delete_db(self):
        try:
            db_path = self.get_db_path()
            if db_path.exists():
                db_path.unlink()
                logger.info(f"Database deleted: {db_path}")
        except Exception as e:
            logger.error(f"Failed to delete database: {e}")
            print("Unable to delete the database. Please check your configuration and try again.")
            return None

    @log_call
    def table_exists(self, table_name):
        """Check if a table exists in the database"""
        try:
            result = self.execute_query("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name=?
            """, (table_name,), fetch_one=True, fetch_all=False)
            return result is not None
        except Exception as e:
            logger.error(f"Failed to check if table {table_name} exists: {e}")
            print("Unable to check if table exists. Please check your configuration and try again.")
            return None
