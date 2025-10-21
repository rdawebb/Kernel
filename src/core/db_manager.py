"""Database management layer - handles connections, transactions, and low-level operations"""

import sqlite3
import pandas as pd
from pathlib import Path
from contextlib import contextmanager
from src.utils.config import load_config
from src.utils.log_manager import get_logger

logger = get_logger()

class DatabaseManager:
    """Handles database connections and low-level operations"""
    
    def __init__(self):
        self.config = load_config()
    
    def get_config_path(self, path_key):
        """Get a path from config by key name"""
        return Path(self.config[path_key])

    def get_db_path(self):
        return self.get_config_path("db_path")

    def get_backup_path(self):
        return self.get_config_path("backup_path")

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
            
            return str(backup_path)
                    
        except Exception as e:
            logger.error(f"Failed to backup database: {e}")
            print("Unable to backup the database. Please check your configuration and try again.")
            return None

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
                        print(f"Exported {len(df)} rows from {table} to {csv_file}")
                    else:
                        print(f"Table {table} does not exist in the database. Skipping export.")
            
            return exported_files
        
        except Exception as e:
            logger.error(f"Failed to export database to CSV: {e}")
            print("Unable to export the database to CSV. Please check your configuration and try again.")
            return None

    def delete_db(self):
        try:
            db_path = self.get_db_path()
            if db_path.exists():
                db_path.unlink()
        except Exception as e:
            logger.error(f"Failed to delete database: {e}")
            print("Unable to delete the database. Please check your configuration and try again.")
            return None

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
