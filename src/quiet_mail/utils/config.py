import os
from dotenv import load_dotenv

def load_config():
    try:
        load_dotenv()

        # Parse IMAP_PORT and SMTP_PORT with error handling
        try:
            imap_port = int(os.getenv("IMAP_PORT", 993))
        except ValueError:
            raise ValueError("IMAP_PORT must be a valid integer")
        
        # Determine SSL setting first to set smart default port
        smtp_use_ssl = os.getenv("SMTP_USE_SSL", "true").lower() == "true"
        default_smtp_port = 465 if smtp_use_ssl else 587
        
        try:
            smtp_port = int(os.getenv("SMTP_PORT", default_smtp_port))
        except ValueError:
            raise ValueError("SMTP_PORT must be a valid integer")

        config = {
            "imap_server": os.getenv("IMAP_SERVER"),
            "imap_port": imap_port,
            "imap_use_ssl": os.getenv("IMAP_USE_SSL", "true").lower() == "true",
            "smtp_server": os.getenv("SMTP_SERVER"),
            "smtp_port": smtp_port,
            "smtp_use_ssl": smtp_use_ssl,
            "email": os.getenv("EMAIL"),
            "password": os.getenv("PASSWORD"),
            "db_path": os.path.expanduser(os.getenv("DB_PATH", "emails.db")),
            "backup_path": os.path.expanduser(os.getenv("BACKUP_PATH", "backup.db"))
        }

        if not all([config["imap_server"], config["smtp_server"], config["email"], config["password"]]):
            raise ValueError("IMAP_SERVER, SMTP_SERVER, EMAIL, and PASSWORD must be set in environment variables or .env file.")

        return config
    
    except Exception as e:
        raise RuntimeError(f"Failed to load configuration: {e}")