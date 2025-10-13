"""Email operations - handles CRUD operations for emails"""

## TODO: refactor to use schema and remove duplicates

from typing import List, Dict, Optional
from .db_manager import DatabaseManager
from .email_schema import EmailSchemaManager
from tui_mail.utils.logger import get_logger

logger = get_logger()

class EmailOperationsManager:
    """Handles all email CRUD operations"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.schema = EmailSchemaManager()
    
    ## TODO: refactor to use unified methods with table_name parameter & use query schema
    def save_email_to_table(self, table_name: str, email: Dict) -> None:
        """Save email to any email table with appropriate schema"""
        try:
            attachments_str = ','.join(email.get("attachments", []))
            
            # Determine table type and build appropriate query
            if table_name == "inbox":
                self.db.execute_query(f"""
                    INSERT OR REPLACE INTO {table_name} 
                    (uid, subject, sender, recipient, date, time, body, flagged, attachments)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    email["uid"], email["subject"], email["from"], email["to"], 
                    email["date"], email["time"], email.get("body", ""),
                    email.get("flagged", 0), attachments_str
                ), commit=True)
                
            elif table_name == "sent_emails":
                self.db.execute_query(f"""
                    INSERT OR REPLACE INTO {table_name} 
                    (uid, subject, sender, recipient, date, time, body, attachments, sent_status, send_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    email["uid"], email["subject"], email["from"], email["to"], 
                    email["date"], email["time"], email.get("body", ""),
                    attachments_str, email.get("sent_status", "pending"), email.get("send_at")
                ), commit=True)
                
            elif table_name == "deleted_emails":
                self.db.execute_query(f"""
                    INSERT OR REPLACE INTO {table_name} 
                    (uid, subject, sender, recipient, date, time, body, attachments, deleted_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    email["uid"], email["subject"], email["from"], email["to"], 
                    email["date"], email["time"], email.get("body", ""),
                    attachments_str, email.get("deleted_at")
                ), commit=True)
                
            else:  # drafts or other simple tables
                self.db.execute_query(f"""
                    INSERT OR REPLACE INTO {table_name} 
                    (uid, subject, sender, recipient, date, time, body, attachments)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    email["uid"], email["subject"], email["from"], email["to"], 
                    email["date"], email["time"], email.get("body", ""),
                    attachments_str
                ), commit=True)
                
        except Exception as e:
            logger.error(f"Failed to save email to {table_name}: {e}")
            print("Unable to save the email. Please check your configuration and try again.")
            return None
    
    def get_emails_from_table(self, table_name: str, limit: int = 10) -> List[Dict]:
        """Get emails from any email table with standard columns and ordering"""
        try:
            columns = self.schema.get_columns_for_table(table_name)
            emails = self.db.execute_query(f"""
                SELECT {columns}
                FROM {table_name}
                {self.schema.STANDARD_EMAIL_ORDER}
                LIMIT ?
            """, (limit,))
            return self.db.convert_emails_to_dict_list(emails)
        except Exception as e:
            logger.error(f"Failed to retrieve emails from {table_name}: {e}")
            print("Unable to retrieve emails. Please check your configuration and try again.")
            return []

    def get_email_from_table(self, table_name: str, email_uid: str) -> Optional[Dict]:
        """Get a specific email from any email table"""
        try:
            columns = self.schema.get_columns_for_table(table_name, include_body=True)
            email = self.db.execute_query(f"""
                SELECT {columns}
                FROM {table_name}
                WHERE uid = ?
            """, (str(email_uid),), fetch_one=True, fetch_all=False)
            return dict(email) if email else None
        except Exception as e:
            logger.error(f"Failed to retrieve email {email_uid} from {table_name}: {e}")
            print("Unable to retrieve email. Please check your configuration and try again.")
            return None

    def delete_email_from_table(self, table_name: str, email_uid: str) -> None:
        """Delete an email from any email table by UID"""
        try:
            self.db.execute_query(f"DELETE FROM {table_name} WHERE uid = ?", 
                                (str(email_uid),), commit=True)
        except Exception as e:
            logger.error(f"Failed to delete email {email_uid} from {table_name}: {e}")
            print("Unable to delete the email. Please check your configuration and try again.")
            return None

    def email_exists(self, table_name: str, email_uid: str) -> bool:
        """Check if an email exists in the specified table"""
        try:
            result = self.db.execute_query(f"""
                SELECT uid FROM {table_name} 
                WHERE uid = ?
            """, (str(email_uid),), fetch_one=True, fetch_all=False)
            return result is not None
        except Exception as e:
            logger.error(f"Failed to check if email {email_uid} exists in {table_name}: {e}")
            print("Unable to check if email exists. Please check your configuration and try again.")
            return None

    def move_email_between_tables(self, source_table: str, dest_table: str, email_uid: str) -> None:
        """Move an email from one table to another"""
        try:
            email = self.get_email_from_table(source_table, email_uid)
            if not email:
                raise ValueError(f"Email {email_uid} not found in {source_table}")
            
            # Add table-specific fields if moving to special tables
            if dest_table == "deleted_emails":
                from datetime import datetime
                email["deleted_at"] = datetime.now().strftime("%Y-%m-%d")
            elif dest_table == "sent_emails" and "sent_status" not in email:
                email["sent_status"] = "sent"
            
            self.save_email_to_table(dest_table, email)
            self.delete_email_from_table(source_table, email_uid)
        except Exception as e:
            logger.error(f"Failed to move email {email_uid} from {source_table} to {dest_table}: {e}")
            print("Unable to move the email. Please check your configuration and try again.")
            return None

    ## TODO: not necessary?
    def update_email_body(self, table_name: str, email_uid: str, body: str) -> None:
        """Update email body content"""
        try:
            self.db.execute_query(f"""
                UPDATE {table_name}
                SET body = ?
                WHERE uid = ?
            """, (body, str(email_uid)), commit=True)
        except Exception as e:
            logger.error(f"Failed to update email body for {email_uid} in {table_name}: {e}")
            print("Unable to update the email body. Please check your configuration and try again.")
            return None

    ## TODO: refactor & use query schema
    def update_email_flag(self, email_uid: str, flagged: bool) -> None:
        """Mark or unmark an email as flagged (inbox only)"""
        try:
            self.db.execute_query("""
                UPDATE inbox
                SET flagged = ?
                WHERE uid = ?
            """, (1 if flagged else 0, str(email_uid)), commit=True)
        except Exception as e:
            logger.error(f"Failed to update flag status for email {email_uid}: {e}")
            print("Unable to update the email flag status. Please check your configuration and try again.")
            return None

    def update_email_status(self, email_uid: str, new_status: str) -> None:
        """Update the status of an email in sent_emails table"""
        try:
            self.db.execute_query("""
                UPDATE sent_emails
                SET sent_status = ?
                WHERE uid = ?
            """, (new_status, str(email_uid)), commit=True)
        except Exception as e:
            logger.error(f"Failed to update email status for {email_uid}: {e}")
            print("Unable to update the email status. Please check your configuration and try again.")
            return None

    def get_highest_uid(self) -> Optional[int]:
        """Get the highest UID from the inbox to determine where to start fetching new emails"""
        try:
            result = self.db.execute_query("SELECT MAX(CAST(uid AS INTEGER)) FROM inbox", 
                                         fetch_one=True, fetch_all=False)
            return int(result[0]) if result[0] is not None else None
        except Exception as e:
            logger.error(f"Failed to get highest UID from inbox: {e}")
            return None

    ## TODO: not necessary?
    def get_all_emails_from_table(self, table_name: str) -> List[Dict]:
        """Get all emails from a specific table (used by scheduler)"""
        try:
            columns = self.schema.get_columns_for_table(table_name, include_body=True)
            emails = self.db.execute_query(f"""
                SELECT {columns}
                FROM {table_name}
                {self.schema.STANDARD_EMAIL_ORDER}
            """)
            return self.db.convert_emails_to_dict_list(emails)
        except Exception as e:
            logger.error(f"Failed to retrieve all emails from {table_name}: {e}")
            print("Unable to retrieve emails from the table. Please check your configuration and try again.")
            return None
