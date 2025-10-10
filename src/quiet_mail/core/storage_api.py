"""
Email storage API - Main interface for all email database operations

This module provides a unified API for email storage operations using a modular architecture:
- DatabaseManager: handles connections, backups, and exports
- EmailSchemaManager: manages table schemas and column definitions  
- EmailSearchManager: provides comprehensive search functionality
- EmailOperationsManager: handles CRUD operations for emails

The modular design enables easy extension of functionality while maintaining
clean separation of concerns between different operational areas.
"""

## TODO: check for redundant functions and any duplicates

from .db_manager import DatabaseManager
from .email_schema import EmailSchemaManager
from .email_search import EmailSearchManager
from .email_operations import EmailOperationsManager

# Initialize managers
_db_manager = DatabaseManager()
_schema_manager = EmailSchemaManager()
_search_manager = EmailSearchManager()
_operations_manager = EmailOperationsManager()

# ========================================
# Database Management Functions
# ========================================

def get_config_path(path_key):
    """Get a path from config by key name"""
    return _db_manager.get_config_path(path_key)

def get_db_path():
    return _db_manager.get_db_path()

def get_backup_path():
    return _db_manager.get_backup_path()

def get_db_connection():
    return _db_manager.get_db_connection()

def db_connection():
    """Context manager for database connections with automatic cleanup"""
    return _db_manager.db_connection()

def execute_query(query, params=(), fetch_one=False, fetch_all=True, commit=False):
    """Execute a database query with automatic connection management"""
    return _db_manager.execute_query(query, params, fetch_one, fetch_all, commit)

def convert_emails_to_dict_list(emails):
    """Convert cursor results to list of dictionaries"""
    return _db_manager.convert_emails_to_dict_list(emails)

def backup_db(backup_path=None):
    return _db_manager.backup_db(backup_path)

def export_db_to_csv(export_dir):
    return _db_manager.export_db_to_csv(export_dir)

def delete_db():
    return _db_manager.delete_db()


# ========================================
# Database Initialization
# ========================================

def initialize_db():
    """Initialize all email tables with appropriate schemas"""
    try:
        tables = ["inbox", "sent_emails", "drafts", "deleted_emails"]
        for table_name in tables:
            config = _schema_manager.get_table_config(table_name)
            sql = _schema_manager.create_email_table_sql(table_name, **config)
            execute_query(sql, commit=True)
    except Exception as e:
        raise RuntimeError(f"Failed to initialize database: {e}")


# ========================================
# Email Operations (CRUD)
# ========================================

def save_email_to_table(table_name, email):
    """Save email to any email table"""
    return _operations_manager.save_email_to_table(table_name, email)

def get_emails_from_table(table_name, limit=10):
    """Get emails from any email table"""
    return _operations_manager.get_emails_from_table(table_name, limit)

def get_email_from_table(table_name, email_uid):
    """Get a specific email from any email table"""
    return _operations_manager.get_email_from_table(table_name, email_uid)

def delete_email_from_table(table_name, email_uid):
    """Delete an email from any email table by UID"""
    return _operations_manager.delete_email_from_table(table_name, email_uid)

def email_exists(table_name, email_uid):
    """Check if an email exists in the specified table"""
    return _operations_manager.email_exists(table_name, email_uid)

def move_email_between_tables(source_table, dest_table, email_uid):
    """Move an email from one table to another"""
    return _operations_manager.move_email_between_tables(source_table, dest_table, email_uid)

def update_email_status(email_uid, new_status):
    """Update the status of an email in sent_emails table"""
    return _operations_manager.update_email_status(email_uid, new_status)

def get_highest_uid():
    """Get the highest UID from the database"""
    return _operations_manager.get_highest_uid()

def get_all_emails_from_table(table_name):
    """Get all emails from a specific table (used by scheduler)"""
    return _operations_manager.get_all_emails_from_table(table_name)


# ========================================
# Search Functions
# ========================================

def search_emails(table_name, keyword, limit=10):
    """Search emails by keyword in subject, sender, or body"""
    return _search_manager.search_by_keyword(table_name, keyword, limit)

def search_all_emails(keyword, limit=50):
    """Search all email tables by keyword"""
    return _search_manager.search_all_tables(keyword, limit)

def search_emails_by_flag_status(flagged_status, limit=10):
    """Retrieve emails based on their flagged status"""
    return _search_manager.search_by_flag_status(flagged_status, limit)

def search_emails_with_attachments(table_name, limit=10):
    """Retrieve emails that have attachments"""
    return _search_manager.search_with_attachments(table_name, limit)

def get_pending_emails():
    """Get all emails with pending status from sent_emails table"""
    return _search_manager.get_pending_emails()


# ========================================
# Individual Email Operations
# ========================================

def save_email_metadata(email):
    """Save email metadata to the inbox table"""
    save_email_to_table("inbox", email)

def save_email_body(uid, body):
    """Save email body content separately"""
    _operations_manager.update_email_body("inbox", uid, body)

## TODO: not needed?
def get_inbox(limit=10):
    """Get inbox emails"""
    return get_emails_from_table("inbox", limit)

def mark_email_flagged(email_uid, flagged=True):
    """Mark or unmark an email as flagged"""
    _operations_manager.update_email_flag(email_uid, flagged)

def delete_email(email_uid):
    """Delete an email from the inbox"""
    delete_email_from_table("inbox", email_uid)


# ========================================
# Table-specific convenience functions
# ========================================

def save_sent_email(email):
    """Save email to sent_emails table"""
    save_email_to_table("sent_emails", email)

def save_draft_email(email):
    """Save email to drafts table"""
    save_email_to_table("drafts", email)

def save_deleted_email(email):
    """Save email to deleted_emails table"""
    save_email_to_table("deleted_emails", email)

def get_sent_emails(limit=10):
    """Get sent emails"""
    return get_emails_from_table("sent_emails", limit)

def get_draft_emails(limit=10):
    """Get draft emails"""
    return get_emails_from_table("drafts", limit)

def get_deleted_emails(limit=10):
    """Get deleted emails"""
    return get_emails_from_table("deleted_emails", limit)

def search_inbox_emails(keyword, limit=10):
    """Search inbox emails by keyword"""
    return search_emails("inbox", keyword, limit)

def search_sent_emails(keyword, limit=10):
    """Search sent emails by keyword"""
    return search_emails("sent_emails", keyword, limit)

def search_draft_emails(keyword, limit=10):
    """Search draft emails by keyword"""
    return search_emails("drafts", keyword, limit)

def search_deleted_emails(keyword, limit=10):
    """Search deleted emails by keyword"""
    return search_emails("deleted_emails", keyword, limit)
