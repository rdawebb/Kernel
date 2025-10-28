"""Database connection manager module."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional


class ConnectionPool:
    """A simple connection pool for SQLite database connections."""

    def __init__(self, db_path: Path):
        """Initialize the connection pool with the database path."""

        self.db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None
        self._in_use = False

    def get_connection(self) -> sqlite3.Connection:
        """Get a database connection from the pool."""
        
        if self._connection is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._connection.row_factory = sqlite3.Row

        return self._connection
    
    @contextmanager
    def connection(self):
        """Context manager for safe connection usage."""

        if self._in_use:
            temp_conn = sqlite3.connect(str(self.db_path))
            temp_conn.row_factory = sqlite3.Row

            try:
                yield temp_conn
            finally:
                temp_conn.close()
        
        else:
            self._in_use = True

            try:
                yield self.get_connection()
            finally:
                self._in_use = False

    def close(self) -> None:
        """Close the connection pool"""

        if self._connection:
            self._connection.close()
            self._connection = None

    def execute(self, query: str, params: tuple = (), 
                fetch_one: bool = False, commit: bool = False):
        """Execute a query using pooled connection."""

        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)

            if commit:
                conn.commit()
                return cursor.lastrowid
            
            if fetch_one:
                result = cursor.fetchone()
                return dict(result) if result else None
            
            results = cursor.fetchall()
            return [dict(row) for row in results]
        
    
class DatabaseManager:
    """Database manager for daemon operations."""

    def __init__(self, db_path: Path):
        """Initialize the database manager"""

        self.db_path = db_path
        self.pool = ConnectionPool(db_path)

    def execute(self, query: str, params: tuple = (), 
                fetch_one: bool = False, commit: bool = False):
        """Execute a query using the connection pool."""

        return self.pool.execute(query, params, fetch_one, commit)
    
    @contextmanager
    def connection(self):
        """Get a connection from the pool."""

        with self.pool.connection() as conn:
            yield conn

    def close(self) -> None:
        """Close all connections in the pool."""

        self.pool.close()

    def __enter__(self):
        """Context manager entry."""

        return self
    
    def __exit__(self, exc_type, exc_value, exc_tb):
        """Context manager exit - close connections."""

        self.close()
