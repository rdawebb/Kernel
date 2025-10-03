import sqlite3
from pathlib import Path
from utils.config import load_config

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
                body TEXT
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        raise RuntimeError(f"Failed to initialize database: {e}")

def save_email_metadata(uid, sender, subject, date, time):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Use UPSERT to avoid duplicates while updating existing records
        cursor.execute("""
            INSERT INTO emails (uid, sender, subject, date, time)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(uid) DO UPDATE SET
                sender = excluded.sender,
                subject = excluded.subject,
                date = excluded.date,
                time = excluded.time
        """, (uid, sender, subject, date, time))
        conn.commit()
    finally:
        conn.close()

def save_email_body(uid, body):
    """Save email body content separately (loaded only when viewing specific emails)"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Use UPSERT for body storage
        cursor.execute("""
            INSERT INTO emails (uid, body)
            VALUES (?, ?)
            ON CONFLICT(uid) DO UPDATE SET
                body = excluded.body
        """, (body, uid))
        conn.commit()
    finally:
        conn.close()

def get_inbox(limit=10):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, uid, subject, sender, recipient, date, time
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
            SELECT id, uid, sender as "from", subject, date, time, body
            FROM emails
            WHERE uid = ?
        """, (str(email_uid),))
        email = cursor.fetchone()
        conn.close()
        return dict(email) if email else None
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve email {email_uid}: {e}")