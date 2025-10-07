import sqlite3
from pathlib import Path
from contextlib import contextmanager
from quiet_mail.utils.config import load_config

def get_db_path():
    config = load_config()
    return Path(config["db_path"])

def get_db_connection():
    try:
        db_path = get_db_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        # Enable row_factory for dict-like access to query results
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        raise RuntimeError(f"Failed to connect to database: {e}")

@contextmanager
def db_connection():
    """Context manager for database connections with automatic cleanup"""
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()

def execute_query(query, params=(), fetch_one=False, fetch_all=True, commit=False):
    """Execute a database query with automatic connection management"""
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        
        if commit:
            conn.commit()
        
        if fetch_one:
            return cursor.fetchone()
        elif fetch_all:
            return cursor.fetchall()
        return cursor

def convert_emails_to_dict_list(emails):
    """Convert cursor results to list of dictionaries"""
    return [dict(email) for email in emails]

# Base email columns shared by all tables (includes attachments since all tables have it)
_BASE_EMAIL_COLUMNS_WITH_ATTACHMENTS = """uid, subject, sender as "from", recipient as "to", date, time, attachments"""

# Additional columns
_FLAGGED_COLUMN = "flagged"
_BODY_COLUMN = "body"

# Constructed column constants
STANDARD_EMAIL_COLUMNS = f"{_BASE_EMAIL_COLUMNS_WITH_ATTACHMENTS}, {_FLAGGED_COLUMN}"
STANDARD_EMAIL_COLUMNS_WITH_BODY = f"{_BASE_EMAIL_COLUMNS_WITH_ATTACHMENTS}, {_FLAGGED_COLUMN}, {_BODY_COLUMN}"
STANDARD_EMAIL_COLUMNS_NO_FLAG = _BASE_EMAIL_COLUMNS_WITH_ATTACHMENTS
STANDARD_EMAIL_COLUMNS_NO_FLAG_WITH_BODY = f"{_BASE_EMAIL_COLUMNS_WITH_ATTACHMENTS}, {_BODY_COLUMN}"

STANDARD_EMAIL_ORDER = "ORDER BY date DESC, time DESC"

# Table schema constants
_BASE_SCHEMA_COLUMNS = """uid TEXT PRIMARY KEY,
    subject TEXT,
    sender TEXT,
    recipient TEXT,
    date TEXT,
    time TEXT,
    body TEXT,
    attachments TEXT DEFAULT ''"""

FLAGGED_COLUMN = "flagged BOOLEAN DEFAULT 0"

def create_email_table(table_name, include_flagged=False):
    """Create a standardized email table with optional flagged column"""
    schema = _BASE_SCHEMA_COLUMNS
    if include_flagged:
        # Insert flagged column before body
        schema = schema.replace("body TEXT,", f"{FLAGGED_COLUMN},\n    body TEXT,")
    
    return f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            {schema}
        )
    """

def initialize_db():
    try:
        execute_query(create_email_table("emails", include_flagged=True), commit=True)
        
        execute_query(create_email_table("sent_emails"), commit=True)
        execute_query(create_email_table("drafts"), commit=True)
        execute_query(create_email_table("deleted_emails"), commit=True)

    except Exception as e:
        raise RuntimeError(f"Failed to initialize database: {e}")

def save_email_metadata(email):
    """Save email metadata to the emails table."""
    save_email_to_table("emails", email)

def save_email_body(uid, body):
    """Save email body content separately (loaded only when viewing specific emails)"""
    execute_query("""
        UPDATE emails
        SET body = ?
        WHERE uid = ?
    """, (body, uid), commit=True)

def get_inbox(limit=10):
    try:
        emails = execute_query(f"""
            SELECT {STANDARD_EMAIL_COLUMNS}
            FROM emails
            {STANDARD_EMAIL_ORDER}
            LIMIT ?
        """, (limit,))
        return convert_emails_to_dict_list(emails)
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve inbox: {e}")

def get_email(email_uid):
    try:
        email = execute_query(f"""
            SELECT {STANDARD_EMAIL_COLUMNS_WITH_BODY}
            FROM emails
            WHERE uid = ?
        """, (str(email_uid),), fetch_one=True, fetch_all=False)
        return dict(email) if email else None
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve email {email_uid}: {e}")
    
def search_emails(keyword, limit=10):
    """Search emails by keyword in subject or sender"""
    try:
        search_term = f"%{keyword}%"
        emails = execute_query(f"""
            SELECT {STANDARD_EMAIL_COLUMNS}
            FROM emails
            WHERE subject LIKE ? OR sender LIKE ? or body LIKE ?
            {STANDARD_EMAIL_ORDER}
            LIMIT ?
        """, (search_term, search_term, search_term, limit))
        return convert_emails_to_dict_list(emails)
    except Exception as e:
        raise RuntimeError(f"Failed to search emails with keyword '{keyword}': {e}")
    
def mark_email_flagged(email_uid, flagged=True):
    """Mark or unmark an email as flagged"""
    try:
        execute_query("""
            UPDATE emails
            SET flagged = ?
            WHERE uid = ?
        """, (1 if flagged else 0, str(email_uid)), commit=True)
    except Exception as e:
        raise RuntimeError(f"Failed to update flag status for email {email_uid}: {e}")
    
def search_emails_by_flag_status(flagged_status, limit=10):
    """Retrieve emails based on their flagged status"""
    try:
        emails = execute_query(f"""
            SELECT {STANDARD_EMAIL_COLUMNS}
            FROM emails
            WHERE flagged = ?
            {STANDARD_EMAIL_ORDER}
            LIMIT ?
        """, (1 if flagged_status else 0, limit))
        return convert_emails_to_dict_list(emails)
    except Exception as e:
        status_name = "flagged" if flagged_status else "unflagged"
        raise RuntimeError(f"Failed to retrieve {status_name} emails: {e}")
    
def search_emails_with_attachments(limit=10):
    """Retrieve emails that have attachments"""
    try:
        emails = execute_query(f"""
            SELECT {STANDARD_EMAIL_COLUMNS}
            FROM emails
            WHERE attachments IS NOT NULL AND attachments != ''
            {STANDARD_EMAIL_ORDER}
            LIMIT ?
        """, (limit,))
        return convert_emails_to_dict_list(emails)
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve emails with attachments: {e}")
    
def get_highest_uid():
    """Get the highest UID from the database to determine where to start fetching new emails"""
    try:
        # Cast UID to INTEGER for proper numeric comparison
        result = execute_query("SELECT MAX(CAST(uid AS INTEGER)) FROM emails", fetch_one=True, fetch_all=False)
        return int(result[0]) if result[0] is not None else None
    except Exception as e:
        print(f"Error getting highest UID: {e}")
        return None

def delete_email(email_uid):
    """Delete an email from the local database by UID"""
    try:
        execute_query("DELETE FROM emails WHERE uid = ?", (str(email_uid),), commit=True)
    except Exception as e:
        raise RuntimeError(f"Failed to delete email {email_uid}: {e}")

### Generic helper functions for working with multiple email tables ###

def save_email_to_table(table_name, email):
    """Save email to any email table (sent_emails, drafts, deleted_emails, etc.)"""
    attachments_str = ','.join(email.get("attachments", []))
    
    # Check if table has flagged column (only emails table)
    has_flagged = table_name == "emails"
    
    if has_flagged:
        execute_query(f"""
            INSERT OR REPLACE INTO {table_name} (uid, subject, sender, recipient, date, time, body, flagged, attachments)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            email["uid"],
            email["subject"],
            email["from"],
            email["to"], 
            email["date"],
            email["time"],
            email["body"],
            email["flagged"],
            attachments_str
        ), commit=True)
    else:
        execute_query(f"""
            INSERT OR REPLACE INTO {table_name} (uid, subject, sender, recipient, date, time, body, attachments)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            email["uid"],
            email["subject"],
            email["from"],
            email["to"], 
            email["date"],
            email["time"],
            email["body"],
            attachments_str
        ), commit=True)

def get_emails_from_table(table_name, limit=10):
    """Get emails from any email table with standard columns and ordering"""
    try:
        # Determine which columns to select based on table
        if table_name == "emails":
            columns = STANDARD_EMAIL_COLUMNS
        else:
            columns = STANDARD_EMAIL_COLUMNS_NO_FLAG
        
        emails = execute_query(f"""
            SELECT {columns}
            FROM {table_name}
            {STANDARD_EMAIL_ORDER}
            LIMIT ?
        """, (limit,))
        return convert_emails_to_dict_list(emails)
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve emails from {table_name}: {e}")

def get_email_from_table(table_name, email_uid):
    """Get a specific email from any email table"""
    try:
        # Include body and determine if flagged column exists
        if table_name == "emails":
            columns = STANDARD_EMAIL_COLUMNS_WITH_BODY
        else:
            columns = STANDARD_EMAIL_COLUMNS_NO_FLAG_WITH_BODY
        
        email = execute_query(f"""
            SELECT {columns}
            FROM {table_name}
            WHERE uid = ?
        """, (str(email_uid),), fetch_one=True, fetch_all=False)
        return dict(email) if email else None
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve email {email_uid} from {table_name}: {e}")

def delete_email_from_table(table_name, email_uid):
    """Delete an email from any email table by UID"""
    try:
        execute_query(f"DELETE FROM {table_name} WHERE uid = ?", (str(email_uid),), commit=True)
    except Exception as e:
        raise RuntimeError(f"Failed to delete email {email_uid} from {table_name}: {e}")

### Specific functions for sent_emails, drafts, deleted_emails tables ###

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