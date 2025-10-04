import sqlite3
from pathlib import Path
from quiet_mail.utils.config import load_config

def get_db_path():
    config = load_config()
    return Path(config["db_path"])

def get_db_connection():
    try:
        db_path = get_db_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        # Enable accessing columns by name instead of index
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        raise RuntimeError(f"Failed to connect to database: {e}")

def initialize_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY,
                uid TEXT UNIQUE,
                subject TEXT,
                sender TEXT,
                recipient TEXT,
                date TEXT,
                time TEXT,
                body TEXT,
                flagged BOOLEAN DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        raise RuntimeError(f"Failed to initialize database: {e}")

def save_email_metadata(uid, sender, subject, recipient, date, time):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO emails (uid, sender, subject, recipient, date, time, flagged)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(uid) DO UPDATE SET
                sender = excluded.sender,
                subject = excluded.subject,
                recipient = excluded.recipient,
                date = excluded.date,
                time = excluded.time,
                flagged = excluded.flagged
        """, (uid, sender, subject, recipient, date, time, False))
        conn.commit()
    finally:
        conn.close()

def save_email_body(uid, body):
    """Save email body content separately (loaded only when viewing specific emails)"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Use UPDATE to add body to existing email record
        cursor.execute("""
            UPDATE emails
            SET body = ?
            WHERE uid = ?
        """, (body, uid))
        conn.commit()
    finally:
        conn.close()

def get_inbox(limit=10):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT uid as id, uid, subject, sender as "from", recipient as "to", date, time, flagged
            FROM emails
            ORDER BY date DESC, time DESC
            LIMIT ?
        """, (limit,))
        emails = cursor.fetchall()
        conn.close()
        return [dict(email) for email in emails]
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve inbox: {e}")

def get_email(email_uid):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, uid, sender as "from", subject, date, time, flagged, body
            FROM emails
            WHERE uid = ?
        """, (str(email_uid),))
        email = cursor.fetchone()
        conn.close()
        return dict(email) if email else None
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve email {email_uid}: {e}")
    
def search_emails(keyword, limit=10):
    """Search emails by keyword in subject or sender"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        search_term = f"%{keyword}%"
        cursor.execute("""
            SELECT uid as id, uid, subject, sender as "from", recipient as "to", date, time, flagged
            FROM emails
            WHERE subject LIKE ? OR sender LIKE ? or body LIKE ?
            ORDER BY date DESC, time DESC
            LIMIT ?
        """, (search_term, search_term, search_term, limit))
        emails = cursor.fetchall()
        conn.close()
        return [dict(email) for email in emails]
    except Exception as e:
        raise RuntimeError(f"Failed to search emails with keyword '{keyword}': {e}")
    
def mark_email_flagged(email_uid, flagged=True):
    """Mark or unmark an email as flagged"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE emails
            SET flagged = ?
            WHERE uid = ?
        """, (1 if flagged else 0, str(email_uid)))
        conn.commit()
        conn.close()
    except Exception as e:
        raise RuntimeError(f"Failed to update flag status for email {email_uid}: {e}")
    
def search_emails_by_flag_status(flagged_status, limit=10):
    """Retrieve emails based on their flagged status"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT uid as id, uid, subject, sender as "from", recipient as "to", date, time, flagged
            FROM emails
            WHERE flagged = ?
            ORDER BY date DESC, time DESC
            LIMIT ?
        """, (1 if flagged_status else 0, limit))
        emails = cursor.fetchall()
        conn.close()
        return [dict(email) for email in emails]
    except Exception as e:
        status_name = "flagged" if flagged_status else "unflagged"
        raise RuntimeError(f"Failed to retrieve {status_name} emails: {e}")