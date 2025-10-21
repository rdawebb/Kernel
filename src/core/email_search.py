"""Email search functionality - handles all search operations and queries with optimized performance"""

from typing import List, Dict, Optional
from .db_manager import DatabaseManager
from .email_schema import EmailSchemaManager
from src.utils.log_manager import get_logger

logger = get_logger()


class EmailSearchManager:
    """Handles all email search operations with unified, optimized methods"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.schema = EmailSchemaManager()
    
    def _log_error(self, message: str, exception: Exception = None) -> None:
        """Log error and print user-friendly message."""
        if exception:
            logger.error(f"{message}: {exception}")
        else:
            logger.error(message)
        print(f"{message}. Please check your configuration and try again.")
    
    def _validate_table(self, table_name: str) -> bool:
        """Validate table exists to prevent SQL injection."""
        return self.db.table_exists(table_name)
    
    def _search(
        self, 
        table_name: str, 
        where_clause: str, 
        params: List, 
        columns: Optional[str] = None, 
        order: Optional[str] = None, 
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict]:
        """Unified search method for all search operations."""
        try:
            if not self._validate_table(table_name):
                raise ValueError(f"Invalid table name: {table_name}")
            
            columns = columns or self.schema.get_columns_for_table(table_name)
            order = order or self.schema.STANDARD_EMAIL_ORDER
            
            query = f"SELECT {columns} FROM {table_name} WHERE {where_clause} {order}"
            
            if limit:
                query += " LIMIT ?"
                params = list(params) + [limit]
            
            if offset:
                query += " OFFSET ?"
                params = list(params) + [offset]
            
            emails = self.db.execute_query(query, tuple(params))
            return self.db.convert_emails_to_dict_list(emails) or []
        
        except Exception as e:
            self._log_error(f"Failed to search emails in {table_name}", e)
            return []
    
    def search_by_keyword(
        self, 
        table_name: str, 
        keyword: str, 
        limit: int = 10, 
        offset: int = 0,
        fields: Optional[List[str]] = None
    ) -> List[Dict]:
        """Search emails by keyword in specified fields."""
        fields = fields or ["subject", "sender", "body"]
        where_clause = " OR ".join([f"{field} LIKE ?" for field in fields])
        params = [f"%{keyword}%"] * len(fields)
        
        return self._search(table_name, where_clause, params, limit=limit, offset=offset)
    
    def search_all_tables(
        self, 
        keyword: str, 
        limit: int = 50, 
        tables: Optional[List[str]] = None
    ) -> List[Dict]:
        """Search all email tables by keyword using UNION for better performance."""
        try:
            tables = tables or ["inbox", "sent_emails", "drafts", "deleted_emails"]
            union_queries = []
            params = []
            search_fields = ["subject", "sender", "body"]
            
            for table_name in tables:
                if not self._validate_table(table_name):
                    continue
                
                columns = self.schema.get_columns_for_table(table_name)
                where_clause = " OR ".join([f"{field} LIKE ?" for field in search_fields])
                
                union_queries.append(
                    f"SELECT {columns}, '{table_name}' AS source_table FROM {table_name} WHERE {where_clause}"
                )
                params.extend([f"%{keyword}%"] * len(search_fields))
            
            if not union_queries:
                return []
            
            query = " UNION ALL ".join(union_queries)
            query += f" {self.schema.STANDARD_EMAIL_ORDER} LIMIT ?"
            params.append(limit)
            
            emails = self.db.execute_query(query, tuple(params))
            return self.db.convert_emails_to_dict_list(emails) or []
        
        except Exception as e:
            self._log_error(f"Failed to search all tables with keyword '{keyword}'", e)
            return []
    
    def search_by_flag_status(self, flagged_status: bool, limit: int = 10, offset: int = 0) -> List[Dict]:
        """Search emails by flag status (inbox only)."""
        return self._search(
            "inbox",
            "flagged = ?",
            [1 if flagged_status else 0],
            limit=limit,
            offset=offset
        )
    
    def search_with_attachments(self, table_name: str, limit: int = 10, offset: int = 0) -> List[Dict]:
        """Search emails that have attachments."""
        return self._search(
            table_name,
            "attachments IS NOT NULL AND attachments != ''",
            [],
            limit=limit,
            offset=offset
        )
    
    def search_by_date_range(
        self, 
        table_name: str, 
        start_date: str, 
        end_date: str, 
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict]:
        """Search emails within a date range."""
        return self._search(
            table_name,
            "date BETWEEN ? AND ?",
            [start_date, end_date],
            limit=limit,
            offset=offset
        )
    
    def search_by_sender(self, table_name: str, sender: str, limit: int = 10, offset: int = 0) -> List[Dict]:
        """Search emails by sender (convenience wrapper)."""
        return self.search_by_keyword(table_name, sender, limit, offset, ["sender"])
    
    def search_by_subject(self, table_name: str, subject: str, limit: int = 10, offset: int = 0) -> List[Dict]:
        """Search emails by subject (convenience wrapper)."""
        return self.search_by_keyword(table_name, subject, limit, offset, ["subject"])
    
    def get_pending_emails(self) -> List[Dict]:
        """Get all emails with pending status from sent_emails table
        
        Returns:
            List of pending email dictionaries ordered by send_at
        """
        return self._search(
            "sent_emails",
            "sent_status = 'pending'",
            [],
            columns="uid, subject, sender, recipient, date, time, body, attachments, sent_status, send_at",
            order="ORDER BY send_at ASC"
        )
    
    def search_with_metadata(
        self, 
        table_name: str, 
        keyword: str, 
        page: int = 1, 
        page_size: int = 10
    ) -> Dict:
        """Search with pagination metadata for better UX
        
        Args:
            table_name: Table to search in
            keyword: Keyword to search for
            page: Page number (1-indexed)
            page_size: Number of results per page
            
        Returns:
            Dictionary with results, total count, page info, and has_more flag
        """
        try:
            # Get total count
            fields = ["subject", "sender", "body"]
            where_clause = " OR ".join([f"{field} LIKE ?" for field in fields])
            params = [f"%{keyword}%"] * len(fields)
            
            count_query = f"SELECT COUNT(*) FROM {table_name} WHERE {where_clause}"
            result = self.db.execute_query(count_query, tuple(params), fetch_one=True, fetch_all=False)
            total_count = result[0] if result else 0
            
            # Get paginated results
            offset = (page - 1) * page_size
            results = self.search_by_keyword(table_name, keyword, limit=page_size, offset=offset)
            
            return {
                "results": results,
                "total": total_count,
                "page": page,
                "page_size": page_size,
                "has_more": offset + len(results) < total_count
            }
        
        except Exception as e:
            self._log_error(f"Failed to search with metadata in {table_name}", e)
            return {
                "results": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "has_more": False
            }
