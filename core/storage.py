import sqlite3
from pathlib import Path
from utils.config import load_config

def get_db_path():
    config = load_config()
    return Path(config["db_path"])

def get_db_connection():
    try:
        db_path = get_db_path()
        # Ensure the database directory exists before connecting
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        # Enable accessing columns by name instead of just index
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
                body TEXT
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        raise RuntimeError(f"Failed to initialize database: {e}")

def save_email_metadata(email_data):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Use UPSERT to avoid duplicates when re-fetching emails
        cursor.execute("""
            INSERT INTO emails (subject, sender, recipient, date)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(uid) DO UPDATE SET
                subject=excluded.subject,
                sender=excluded.sender,
                date=excluded.date
        """, (
            email_data.get("subject"),
            email_data.get("from"),
            email_data.get("to"),
            email_data.get("date")
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        raise RuntimeError(f"Failed to save email metadata: {e}")

def save_email_body(uid, body):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE emails
            SET body = ?
            WHERE uid = ?
        """, (body, uid))
        conn.commit()
        conn.close()
    except Exception as e:
        raise RuntimeError(f"Failed to save email body: {e}")

def get_inbox(limit=10):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, uid, subject, sender, recipient, date 
            FROM emails 
            ORDER BY date DESC 
            LIMIT ?
        """, (limit,))
        emails = cursor.fetchall()
        conn.close()
        return [dict(email) for email in emails]
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve inbox: {e}")

def get_email(email_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Alias 'sender' as 'from' to match expected email format
        cursor.execute("""
            SELECT id, uid, sender as "from", subject, date, body
            FROM emails
            WHERE id = ?
        """, (email_id,))
        email = cursor.fetchone()
        conn.close()
        return dict(email) if email else None
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve email {email_id}: {e}")