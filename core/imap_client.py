import imaplib, email
from email.header import decode_header
from utils.config import load_config

config = load_config()

def connect_to_imap(config):
    try:
        # Use port from config, default to 993 for SSL
        port = config.get('imap_port', 993)
        if config.get('imap_use_ssl', True):
            mail = imaplib.IMAP4_SSL(config['imap_server'], port)
        else:
            mail = imaplib.IMAP4(config['imap_server'], port)
        
        mail.login(config['email'], config['password'])
        mail.select("inbox")

    except Exception as e:
        print(f"Error connecting to email server: {e}")
        return None
    
    return mail

def fetch_inbox(config, limit=10):
    try:
        return [
            {"id": 1, "uid": "abc123", "from": "alice@example.com",
            "subject": "Hello!", "date": "2025-09-25", "time": "10:30:00"},
            {"id": 2, "uid": "def456", "from": "bob@example.com",
            "subject": "Meeting update", "date": "2025-09-24", "time": "14:00:00"},
        ][:limit]
    except Exception as e:
        print(f"Error fetching emails: {e}")
        return []
