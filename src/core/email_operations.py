"""Email operations - handles CRUD operations for emails"""

from typing import List, Dict, Optional
from datetime import datetime
from .db_manager import DatabaseManager
from .email_schema import EmailSchemaManager
from ..utils.log_manager import get_logger, log_call

logger = get_logger(__name__)


class EmailOperationsManager:
    """Handles all email CRUD operations with unified methods"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.schema = EmailSchemaManager()
    
    def _format_attachments(self, attachments) -> str:
        """Convert attachments to comma-separated string."""
        if isinstance(attachments, str):
            return attachments
        if isinstance(attachments, (list, tuple)):
            return ','.join(attachments)
        return ""
    
    def _get_email_field_value(self, email: Dict, field_name: str):
        """Get a field value from email, handling both database column names and their UI aliases."""
        # Map database column names to possible keys in the email dict
        field_map = {
            'sender': ['sender', 'from'],      # sender column might be passed as 'from'
            'recipient': ['recipient', 'to'],  # recipient column might be passed as 'to'
        }
        
        if field_name in field_map:
            # Try to get value using any of the possible keys
            for key in field_map[field_name]:
                if key in email:
                    return email[key]
            # If none found, return empty string
            return ""
        else:
            # For other fields, just use the field name as-is
            return email.get(field_name, "")
    
    @log_call
    def save_email_to_table(self, table_name: str, email: Dict) -> None:
        """Save email to any table using schema manager for dynamic columns."""
        try:
            columns_list = self.schema.get_insert_columns_for_table(table_name).split(', ')
            placeholders = ', '.join(['?' for _ in columns_list])
            
            # Build values list in correct column order
            values = []
            for col in columns_list:
                col = col.strip()
                if col == "attachments":
                    values.append(self._format_attachments(email.get("attachments", "")))
                else:
                    values.append(self._get_email_field_value(email, col))
            
            self.db.execute_query(
                f"INSERT OR REPLACE INTO {table_name} ({', '.join(columns_list)}) VALUES ({placeholders})",
                tuple(values),
                commit=True
            )
        except Exception as e:
            logger.error(f"Failed to save email to {table_name}: {e}")
            print("Failed to save email. Please check your configuration and try again.")
    
    @log_call
    def get_emails(self, table_name: str, limit: Optional[int] = None, include_body: bool = False) -> List[Dict]:
        """Get emails from a table with optional limit."""
        try:
            columns = self.schema.get_columns_for_table(table_name, include_body=include_body)
            query = f"SELECT {columns} FROM {table_name} {self.schema.STANDARD_EMAIL_ORDER}"
            
            if limit:
                query += " LIMIT ?"
                emails = self.db.execute_query(query, (limit,))
            else:
                emails = self.db.execute_query(query)

            return self.db.convert_emails_to_dict_list(emails) or []
        except Exception as e:
            logger.error(f"Failed to retrieve emails from {table_name}: {e}")
            print("Failed to retrieve emails. Please check your configuration and try again.")
            return []
    

    @log_call
    def get_email_from_table(self, table_name: str, email_uid: str) -> Optional[Dict]:
        """Get a specific email by UID."""
        try:
            columns = self.schema.get_columns_for_table(table_name, include_body=True)
            email = self.db.execute_query(
                f"SELECT {columns} FROM {table_name} WHERE uid = ?",
                (str(email_uid),),
                fetch_one=True,
                fetch_all=False
            )
            return dict(email) if email else None
        except Exception as e:
            logger.error(f"Failed to retrieve email {email_uid} from {table_name}: {e}")
            print("Failed to retrieve email. Please check your configuration and try again.")
            return None

    @log_call
    def delete_email_from_table(self, table_name: str, email_uid: str) -> None:
        """Delete an email from a table by UID."""
        try:
            self.db.execute_query(
                f"DELETE FROM {table_name} WHERE uid = ?",
                (str(email_uid),),
                commit=True
            )
            logger.info(f"Deleted email {email_uid} from {table_name}")
        except Exception as e:
            logger.error(f"Failed to delete email {email_uid} from {table_name}: {e}")
            print("Failed to delete email. Please check your configuration and try again.")

    @log_call
    def email_exists(self, table_name: str, email_uid: str) -> bool:
        """Check if an email exists in a table."""
        try:
            result = self.db.execute_query(
                f"SELECT uid FROM {table_name} WHERE uid = ?",
                (str(email_uid),),
                fetch_one=True,
                fetch_all=False
            )
            return result is not None
        except Exception as e:
            logger.error(f"Failed to check if email {email_uid} exists in {table_name}: {e}")
            return False

    @log_call
    def move_email_between_tables(self, source_table: str, dest_table: str, email_uid: str) -> None:
        """Move an email from one table to another with table-specific field handling."""
        try:
            email = self.get_email_from_table(source_table, email_uid)
            if not email:
                raise ValueError(f"Email {email_uid} not found in {source_table}")
            
            # Add table-specific fields if moving to special tables
            if dest_table == "deleted_emails":
                email["deleted_at"] = datetime.now().strftime("%Y-%m-%d")
            elif dest_table == "sent_emails" and "sent_status" not in email:
                email["sent_status"] = "sent"
            
            self.save_email_to_table(dest_table, email)
            self.delete_email_from_table(source_table, email_uid)
            logger.info(f"Moved email {email_uid} from {source_table} to {dest_table}")
        except Exception as e:
            logger.error(f"Failed to move email {email_uid} from {source_table} to {dest_table}: {e}")
            print("Failed to move email. Please check your configuration and try again.")

    @log_call
    def update_email_field(self, table_name: str, email_uid: str, field_name: str, value) -> None:
        """Update a specific field for an email in a table."""
        try:
            self.db.execute_query(
                f"UPDATE {table_name} SET {field_name} = ? WHERE uid = ?",
                (value, str(email_uid)),
                commit=True
            )
            logger.debug(f"Updated {field_name} for email {email_uid} in {table_name}")
        except Exception as e:
            logger.error(f"Failed to update {field_name} for email {email_uid} in {table_name}: {e}")
            print("Failed to update email. Please check your configuration and try again.")

    def update_email_flag(self, email_uid: str, flagged: bool) -> None:
        """Mark or unmark an email as flagged (inbox only)."""
        self.update_email_field("inbox", email_uid, "flagged", 1 if flagged else 0)

    def update_email_status(self, email_uid: str, new_status: str) -> None:
        """Update the status of an email in sent_emails table."""
        self.update_email_field("sent_emails", email_uid, "sent_status", new_status)

    @log_call
    def get_highest_uid(self) -> Optional[int]:
        """Get the highest UID from inbox to determine where to start fetching new emails."""
        try:
            result = self.db.execute_query(
                "SELECT MAX(CAST(uid AS INTEGER)) FROM inbox",
                fetch_one=True,
                fetch_all=False
            )
            return int(result[0]) if result and result[0] is not None else None
        except Exception as e:
            logger.error(f"Failed to get highest UID from inbox: {e}")
            return None
