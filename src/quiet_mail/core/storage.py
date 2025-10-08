import sqlite3
import pandas as pd
from pathlib import Path
from contextlib import contextmanager
from quiet_mail.utils.config import load_config

def get_config_path(path_key):
    """Get a path from config by key name"""
    config = load_config()
    return Path(config[path_key])

def get_db_path():
    return get_config_path("db_path")

def get_backup_path():
    return get_config_path("backup_path")

def get_db_connection():
    try:
        db_path = get_db_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
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

_BASE_EMAIL_COLUMNS_WITH_ATTACHMENTS = """uid, subject, sender as "from", recipient as "to", date, time, attachments"""

_FLAGGED_COLUMN = "flagged"
_BODY_COLUMN = "body"
_DELETED_DATE_COLUMN = "deleted_at"
_SENT_STATUS = "sent_status"
_SEND_AT = "send_at"

STANDARD_EMAIL_COLUMNS = f"{_BASE_EMAIL_COLUMNS_WITH_ATTACHMENTS}, {_FLAGGED_COLUMN}"
STANDARD_EMAIL_COLUMNS_WITH_BODY = f"{_BASE_EMAIL_COLUMNS_WITH_ATTACHMENTS}, {_FLAGGED_COLUMN}, {_BODY_COLUMN}"
STANDARD_EMAIL_COLUMNS_NO_FLAG = _BASE_EMAIL_COLUMNS_WITH_ATTACHMENTS
STANDARD_EMAIL_COLUMNS_NO_FLAG_WITH_BODY = f"{_BASE_EMAIL_COLUMNS_WITH_ATTACHMENTS}, {_BODY_COLUMN}"

STANDARD_EMAIL_ORDER = "ORDER BY date DESC, time DESC"

_BASE_SCHEMA_COLUMNS = """uid TEXT PRIMARY KEY,
    subject TEXT,
    sender TEXT,
    recipient TEXT,
    date TEXT,
    time TEXT,
    body TEXT,
    attachments TEXT DEFAULT ''"""

FLAGGED_COLUMN = "flagged BOOLEAN DEFAULT 0"
DELETED_AT_COLUMN = "deleted_at TEXT"
SENT_STATUS_COLUMN = "sent_status TEXT DEFAULT 'pending'"
SEND_AT_COLUMN = "send_at TEXT"

def create_email_table(table_name, include_flagged=False, include_deleted=False, include_sent_status=False, include_send_at=False):
    """Create a standardized email table with optional flagged, deleted, and sent status columns"""
    schema = _BASE_SCHEMA_COLUMNS
    
    if include_flagged:
        schema = schema.replace("body TEXT,", f"{FLAGGED_COLUMN},\n    body TEXT,")
    
    additional_columns = []
    
    if include_deleted:
        additional_columns.append(DELETED_AT_COLUMN)
    
    if include_sent_status:
        additional_columns.append(SENT_STATUS_COLUMN)
    
    if include_send_at:
        additional_columns.append(SEND_AT_COLUMN)
    
    if additional_columns:
        additional_cols_str = ",\n    " + ",\n    ".join(additional_columns)
        schema = schema.replace("attachments TEXT DEFAULT ''", f"attachments TEXT DEFAULT ''{additional_cols_str}")

    return f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            {schema}
        )
    """

def initialize_db():
    try:
        execute_query(create_email_table("inbox", include_flagged=True), commit=True)

        execute_query(create_email_table("sent_emails", include_sent_status=True, include_send_at=True), commit=True)
        execute_query(create_email_table("drafts"), commit=True)
        execute_query(create_email_table("deleted_emails", include_deleted=True), commit=True)

    except Exception as e:
        raise RuntimeError(f"Failed to initialize database: {e}")

def backup_db(backup_path=None):
    try:
        db_path = get_db_path()
        if backup_path is None:
            backup_path = get_backup_path()
        else:
            backup_path = Path(backup_path)
        
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(db_path) as source_conn:
            with sqlite3.connect(backup_path) as dest_conn:
                source_conn.backup(dest_conn)
        
        return str(backup_path)
                
    except Exception as e:
        raise RuntimeError(f"Failed to backup database: {e}")
    
def export_db_to_csv(export_dir):
    try:
        export_path = Path(export_dir)
        export_path.mkdir(parents=True, exist_ok=True)
        
        tables = ["inbox", "sent_emails", "drafts", "deleted_emails"]
        exported_files = []
        
        with db_connection() as conn:
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
        raise RuntimeError(f"Failed to export database to CSV: {e}")

def delete_db():
    try:
        db_path = get_db_path()
        if db_path.exists():
            db_path.unlink()
    except Exception as e:
        raise RuntimeError(f"Failed to delete database: {e}")

def save_email_metadata(email):
    """Save email metadata to the inbox table."""
    save_email_to_table("inbox", email)

def save_email_body(uid, body):
    """Save email body content separately (loaded only when viewing specific emails)"""
    execute_query("""
        UPDATE inbox
        SET body = ?
        WHERE uid = ?
    """, (body, uid), commit=True)

def get_inbox(limit=10):
    try:
        emails = execute_query(f"""
            SELECT {STANDARD_EMAIL_COLUMNS}
            FROM inbox
            {STANDARD_EMAIL_ORDER}
            LIMIT ?
        """, (limit,))
        return convert_emails_to_dict_list(emails)
    
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve inbox: {e}")
    
def search_emails(table_name, keyword, limit=10):
    """Search emails by keyword in subject or sender"""
    try:
        search_term = f"%{keyword}%"
        
        if table_name == "inbox":
            columns = STANDARD_EMAIL_COLUMNS
        else:
            columns = STANDARD_EMAIL_COLUMNS_NO_FLAG
        
        emails = execute_query(f"""
            SELECT {columns}
            FROM {table_name}
            WHERE subject LIKE ? OR sender LIKE ? or body LIKE ?
            {STANDARD_EMAIL_ORDER}
            LIMIT ?
        """, (search_term, search_term, search_term, limit))
        return convert_emails_to_dict_list(emails)
    
    except Exception as e:
        raise RuntimeError(f"Failed to search emails with keyword '{keyword}' in {table_name}: {e}")

def search_all_emails(keyword, limit=50):
    """Search all email tables by keyword in subject or sender"""
    try:
        search_term = f"%{keyword}%"
        all_emails = []
        
        for table_name in ["inbox", "sent_emails", "drafts", "deleted_emails"]:
            if table_name == "inbox":
                columns = STANDARD_EMAIL_COLUMNS
            else:
                columns = STANDARD_EMAIL_COLUMNS_NO_FLAG
            
            emails = execute_query(f"""
                SELECT {columns}, '{table_name}' AS source_table
                FROM {table_name}
                WHERE subject LIKE ? OR sender LIKE ? OR body LIKE ?
                {STANDARD_EMAIL_ORDER}
                LIMIT ?
            """, (search_term, search_term, search_term, limit))
            all_emails.extend(convert_emails_to_dict_list(emails))

        all_emails.sort(key=lambda email: (email['date'], email['time']), reverse=True)

        return all_emails[:limit]
    
    except Exception as e:
        raise RuntimeError(f"Failed to search all emails with keyword '{keyword}': {e}")
    
def mark_email_flagged(email_uid, flagged=True):
    """Mark or unmark an email as flagged"""
    try:
        execute_query("""
            UPDATE inbox
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
            FROM inbox
            WHERE flagged = ?
            {STANDARD_EMAIL_ORDER}
            LIMIT ?
        """, (1 if flagged_status else 0, limit))
        return convert_emails_to_dict_list(emails)
    except Exception as e:
        status_name = "flagged" if flagged_status else "unflagged"
        raise RuntimeError(f"Failed to retrieve {status_name} emails: {e}")
    
def search_emails_with_attachments(table_name, limit=10):
    """Retrieve emails that have attachments"""
    try:
        emails = execute_query(f"""
            SELECT {STANDARD_EMAIL_COLUMNS}
            FROM {table_name}
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
        result = execute_query("SELECT MAX(CAST(uid AS INTEGER)) FROM inbox", fetch_one=True, fetch_all=False)
        return int(result[0]) if result[0] is not None else None
    except Exception as e:
        print(f"Error getting highest UID: {e}")
        return None

def delete_email(email_uid):
    """Delete an email from the local database by UID"""
    try:
        execute_query("DELETE FROM inbox WHERE uid = ?", (str(email_uid),), commit=True)
    except Exception as e:
        raise RuntimeError(f"Failed to delete email {email_uid}: {e}")

# Generic helper functions for working with multiple email tables

def save_email_to_table(table_name, email):
    """Save email to any email table (sent_emails, drafts, deleted_emails, etc.)"""
    attachments_str = ','.join(email.get("attachments", []))
    
    has_flagged = table_name == "emails"
    has_deleted = table_name == "deleted_emails"
    has_sent_status = table_name == "sent_emails"

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

    elif has_deleted:
        execute_query(f"""
            INSERT OR REPLACE INTO {table_name} (uid, subject, sender, recipient, date, time, body, attachments, deleted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            email["uid"],
            email["subject"],
            email["from"],
            email["to"], 
            email["date"],
            email["time"],
            email["body"],
            attachments_str,
            email.get("deleted_at")
        ), commit=True)

    elif has_sent_status:
        execute_query(f"""
            INSERT OR REPLACE INTO {table_name} (uid, subject, sender, recipient, date, time, body, attachments, sent_status, send_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            email["uid"],
            email["subject"],
            email["from"],
            email["to"], 
            email["date"],
            email["time"],
            email["body"],
            attachments_str,
            email.get("sent_status", "pending"),
            email.get("send_at")
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
        if table_name == "inbox":
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
    
def email_exists(table_name, email_uid):
    """Check if an email exists in the specified table"""
    try:
        result = execute_query(f"""
            SELECT uid FROM {table_name} 
            WHERE uid = ?
        """, (str(email_uid),), fetch_one=True, fetch_all=False)
        return result is not None
    except Exception as e:
        raise RuntimeError(f"Failed to check if email {email_uid} exists in {table_name}: {e}")
    
def move_email_between_tables(source_table, dest_table, email_uid):
    """Move an email from one table to another (e.g., inbox to deleted_emails)"""
    try:
        email = get_email_from_table(source_table, email_uid)
        if not email:
            raise ValueError(f"Email {email_uid} not found in {source_table}")
        
        save_email_to_table(dest_table, email)
        delete_email_from_table(source_table, email_uid)
    except Exception as e:
        raise RuntimeError(f"Failed to move email {email_uid} from {source_table} to {dest_table}: {e}")

# Specific functions for sent_emails, drafts, deleted_emails tables

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

def get_pending_emails():
    """Get all emails with pending status from sent_emails table"""
    try:
        emails = execute_query("""
            SELECT uid, subject, sender, recipient, date, time, body, attachments, sent_status, send_at
            FROM sent_emails
            WHERE sent_status = 'pending'
            ORDER BY send_at ASC
        """)
        return convert_emails_to_dict_list(emails)
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve pending emails: {e}")

def update_email_status(email_uid, new_status):
    """Update the status of an email in sent_emails table"""
    try:
        execute_query("""
            UPDATE sent_emails
            SET sent_status = ?
            WHERE uid = ?
        """, (new_status, str(email_uid)), commit=True)
    except Exception as e:
        raise RuntimeError(f"Failed to update email status for {email_uid}: {e}")

def get_all_emails_from_table(table_name):
    """Get all emails from a specific table (used by scheduler)"""
    try:
        if table_name == "inbox":
            columns = STANDARD_EMAIL_COLUMNS_WITH_BODY
        elif table_name == "sent_emails":
            columns = f"{STANDARD_EMAIL_COLUMNS_NO_FLAG_WITH_BODY}, sent_status, send_at"
        elif table_name == "deleted_emails":
            columns = f"{STANDARD_EMAIL_COLUMNS_NO_FLAG_WITH_BODY}, deleted_at"
        else:
            columns = STANDARD_EMAIL_COLUMNS_NO_FLAG_WITH_BODY
        
        emails = execute_query(f"""
            SELECT {columns}
            FROM {table_name}
            {STANDARD_EMAIL_ORDER}
        """)
        return convert_emails_to_dict_list(emails)
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve all emails from {table_name}: {e}")
