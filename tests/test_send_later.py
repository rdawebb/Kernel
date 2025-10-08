#!/usr/bin/env python3
import sys
import sqlite3
from datetime import datetime, timedelta
sys.path.insert(0, 'src')

from quiet_mail.core import storage
from quiet_mail.core.storage import get_db_path

def test_send_later_functionality():
    print("Testing Send Later functionality...")
    
    # Initialize database
    storage.initialize_db()
    
    # Test database schema
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check sent_emails table schema
    cursor.execute("PRAGMA table_info(sent_emails)")
    columns = cursor.fetchall()
    print("sent_emails table columns:")
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")
    
    # Check if sent_status and send_at columns exist
    column_names = [col[1] for col in columns]
    has_sent_status = 'sent_status' in column_names
    has_send_at = 'send_at' in column_names
    
    print(f"\nsent_status column exists: {has_sent_status}")
    print(f"send_at column exists: {has_send_at}")
    
    # Test saving a scheduled email
    if has_sent_status and has_send_at:
        future_time = (datetime.now() + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M")
        test_email = {
            "uid": "test_scheduled_123",
            "subject": "Test Scheduled Email",
            "from": "test@example.com",
            "to": "recipient@example.com",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M:%S"),
            "body": "This is a test scheduled email",
            "attachments": [],
            "sent_status": "pending",
            "send_at": future_time
        }
        
        print(f"\nSaving test scheduled email for {future_time}...")
        storage.save_sent_email(test_email)
        
        # Verify it was saved
        pending_emails = storage.get_pending_emails()
        print(f"Found {len(pending_emails)} pending email(s)")
        
        if pending_emails:
            for email in pending_emails:
                print(f"  - UID: {email['uid']}, Status: {email['sent_status']}, Send At: {email['send_at']}")
    
    # Check deleted_emails table schema
    cursor.execute("PRAGMA table_info(deleted_emails)")
    columns = cursor.fetchall()
    print("\ndeleted_emails table columns:")
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")
    
    column_names = [col[1] for col in columns]
    has_deleted_at = 'deleted_at' in column_names
    print(f"\ndeleted_at column exists: {has_deleted_at}")
    
    conn.close()
    print("\nSend Later functionality test completed!")

if __name__ == "__main__":
    test_send_later_functionality()
