"""Email search functionality - handles all search operations and queries"""

## TODO: refactor to consolidate and remove duplication and optimise search methods

from typing import List, Dict
from .db_manager import DatabaseManager
from .email_schema import EmailSchemaManager
from tui_mail.utils.logger import get_logger

logger = get_logger()

class EmailSearchManager:
    """Handles all email search operations"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.schema = EmailSchemaManager()
    
    def _build_search_query(self, table_name: str, search_fields: List[str], limit: int = 10, 
                           additional_conditions: str = "") -> tuple:
        """Build a standardized search query"""
        columns = self.schema.get_columns_for_table(table_name)
        placeholders = " OR ".join([f"{field} LIKE ?" for field in search_fields])
        
        query = f"""
            SELECT {columns}
            FROM {table_name}
            WHERE {placeholders}
            {additional_conditions}
            {self.schema.STANDARD_EMAIL_ORDER}
            LIMIT ?
        """
        return query, columns
    
    def search_by_keyword(self, table_name: str, keyword: str, limit: int = 10, 
                         search_fields: List[str] = None) -> List[Dict]:
        """Search emails by keyword in specified fields"""
        try:
            if search_fields is None:
                search_fields = ["subject", "sender", "body"]
            
            search_term = f"%{keyword}%"
            query, _ = self._build_search_query(table_name, search_fields, limit)
            
            # Create parameters for each search field plus limit
            params = [search_term] * len(search_fields) + [limit]
            
            emails = self.db.execute_query(query, params)
            return self.db.convert_emails_to_dict_list(emails)
        
        except Exception as e:
            logger.error(f"Failed to search emails with keyword '{keyword}' in {table_name}: {e}")
            print("Unable to search emails. Please check your configuration and try again.")
            return None
    
    def search_all_tables(self, keyword: str, limit: int = 50, 
                         tables: List[str] = None) -> List[Dict]:
        """Search all email tables by keyword"""
        try:
            if tables is None:
                tables = ["inbox", "sent_emails", "drafts", "deleted_emails"]
            
            search_term = f"%{keyword}%"
            all_emails = []
            
            for table_name in tables:
                if not self.db.table_exists(table_name):
                    continue
                    
                columns = self.schema.get_columns_for_table(table_name)
                search_fields = ["subject", "sender", "body"]
                placeholders = " OR ".join([f"{field} LIKE ?" for field in search_fields])
                
                emails = self.db.execute_query(f"""
                    SELECT {columns}, '{table_name}' AS source_table
                    FROM {table_name}
                    WHERE {placeholders}
                    {self.schema.STANDARD_EMAIL_ORDER}
                    LIMIT ?
                """, [search_term] * len(search_fields) + [limit])
                
                all_emails.extend(self.db.convert_emails_to_dict_list(emails))

            # Sort by date and time, then limit
            all_emails.sort(key=lambda email: (email['date'], email['time']), reverse=True)
            return all_emails[:limit]
        
        except Exception as e:
            logger.error(f"Failed to search all emails with keyword '{keyword}': {e}")
            print("Unable to search emails. Please check your configuration and try again.")
            return None

    def search_by_flag_status(self, flagged_status: bool, limit: int = 10) -> List[Dict]:
        """Search emails by flag status (inbox only)"""
        try:
            query, _ = self._build_search_query("inbox", ["flagged"], limit)
            query = query.replace("flagged LIKE ?", "flagged = ?")
            
            emails = self.db.execute_query(query, (1 if flagged_status else 0, limit))
            return self.db.convert_emails_to_dict_list(emails)
        except Exception as e:
            status_name = "flagged" if flagged_status else "unflagged"
            logger.error(f"Failed to retrieve {status_name} emails: {e}")
            print("Unable to retrieve emails. Please check your configuration and try again.")
            return None

    def search_with_attachments(self, table_name: str, limit: int = 10) -> List[Dict]:
        """Search emails that have attachments"""
        try:
            columns = self.schema.get_columns_for_table(table_name)
            emails = self.db.execute_query(f"""
                SELECT {columns}
                FROM {table_name}
                WHERE attachments IS NOT NULL AND attachments != ''
                {self.schema.STANDARD_EMAIL_ORDER}
                LIMIT ?
            """, (limit,))
            return self.db.convert_emails_to_dict_list(emails)
        except Exception as e:
            logger.error(f"Failed to retrieve emails with attachments from {table_name}: {e}")
            print("Unable to retrieve emails. Please check your configuration and try again.")
            return None

    def search_by_date_range(self, table_name: str, start_date: str, end_date: str, 
                           limit: int = 10) -> List[Dict]:
        """Search emails within a date range"""
        try:
            columns = self.schema.get_columns_for_table(table_name)
            emails = self.db.execute_query(f"""
                SELECT {columns}
                FROM {table_name}
                WHERE date BETWEEN ? AND ?
                {self.schema.STANDARD_EMAIL_ORDER}
                LIMIT ?
            """, (start_date, end_date, limit))
            return self.db.convert_emails_to_dict_list(emails)
        except Exception as e:
            logger.error(f"Failed to search emails by date range in {table_name}: {e}")
            print("Unable to search emails. Please check your configuration and try again.")
            return None

    def search_by_sender(self, table_name: str, sender: str, limit: int = 10) -> List[Dict]:
        """Search emails by sender"""
        return self.search_by_keyword(table_name, sender, limit, ["sender"])
    
    def search_by_subject(self, table_name: str, subject: str, limit: int = 10) -> List[Dict]:
        """Search emails by subject"""
        return self.search_by_keyword(table_name, subject, limit, ["subject"])
    
    def get_pending_emails(self) -> List[Dict]:
        """Get all emails with pending status from sent_emails table"""
        try:
            emails = self.db.execute_query("""
                SELECT uid, subject, sender, recipient, date, time, body, attachments, sent_status, send_at
                FROM sent_emails
                WHERE sent_status = 'pending'
                ORDER BY send_at ASC
            """)
            return self.db.convert_emails_to_dict_list(emails)
        except Exception as e:
            logger.error(f"Failed to retrieve pending emails: {e}")
            print("Unable to retrieve emails. Please check your configuration and try again.")
            return None
