import os
from dotenv import load_dotenv

def load_config():
    try:
        load_dotenv()

        # Parse IMAP_PORT with error handling
        try:
            imap_port = int(os.getenv("IMAP_PORT", 993))
        except ValueError:
            raise ValueError("IMAP_PORT must be a valid integer")

        config = {
            "imap_server": os.getenv("IMAP_SERVER"),
            "imap_port": imap_port,
            "imap_use_ssl": os.getenv("IMAP_USE_SSL", "true").lower() == "true",
            "email": os.getenv("EMAIL"),
            "password": os.getenv("PASSWORD"),
            "db_path": os.path.expanduser(os.getenv("DB_PATH", "emails.db"))
        }

        if not all([config["imap_server"], config["email"], config["password"]]):
            raise ValueError("IMAP_SERVER, EMAIL, and PASSWORD must be set in environment variables or .env file.")

        return config
    
    except Exception as e:
        raise RuntimeError(f"Failed to load configuration: {e}")