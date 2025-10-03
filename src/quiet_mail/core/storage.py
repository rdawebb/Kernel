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
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        # Use UPSERT to avoid duplicates while updating existing records
        cursor.execute("""
            INSERT INTO emails (uid, sender, subject, recipient, date, time, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(uid) DO UPDATE SET
                sender = excluded.sender,
                subject = excluded.subject,
                recipient = excluded.recipient,
                date = excluded.date,
                time = excluded.time,
                fetched_at = CURRENT_TIMESTAMP
        """, (uid, sender, subject, recipient, date, time))
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
            SELECT uid as id, uid, subject, sender as "from", recipient as "to", date, time
            FROM emails
            ORDER BY fetched_at DESC
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
            SELECT id, uid, sender as "from", subject, date, time, body
            FROM emails
            WHERE uid = ?
        """, (str(email_uid),))
        email = cursor.fetchone()
        conn.close()
        return dict(email) if email else None
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve email {email_uid}: {e}")