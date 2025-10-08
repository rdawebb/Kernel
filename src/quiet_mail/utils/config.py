import os
import re
from dotenv import load_dotenv

def load_config():
    """Load email configuration from environment variables with validation and defaults"""
    try:
        load_dotenv()

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
            "backup_path": os.path.expanduser(os.getenv("BACKUP_PATH", "backup.db")),
            "export_path": os.path.expanduser(os.getenv("EXPORT_PATH", "./exports")),
            "automatic_backup_enabled": os.getenv("AUTOMATIC_BACKUP_ENABLED", "false").lower() == "true",
            "automatic_backup_interval": automatic_backup_interval,
            "clear_deleted_emails_enabled": os.getenv("CLEAR_DELETED_EMAILS_ENABLED", "false").lower() == "true",
            "clear_deleted_emails_interval": clear_deleted_emails_interval,
            "send_scheduled_emails_enabled": os.getenv("SEND_SCHEDULED_EMAILS_ENABLED", "false").lower() == "true",
            "send_scheduled_emails_interval": send_scheduled_emails_interval,
            "check_for_new_emails_enabled": os.getenv("CHECK_FOR_NEW_EMAILS_ENABLED", "false").lower() == "true",
            "check_for_new_emails_interval": check_for_new_emails_interval,
        }

        if not all([config["imap_server"], config["smtp_server"], config["email"], config["password"]]):
            raise ValueError("IMAP_SERVER, SMTP_SERVER, EMAIL, and PASSWORD must be set in environment variables or .env file.")

        return config
    
    except Exception as e:
        raise RuntimeError(f"Failed to load configuration: {e}")
    
def parse_interval_string(env_key, default_value):
    """Parse interval string like '30m', '2h', '1d' into (value, unit) tuple"""
    interval_str = os.getenv(env_key, default_value).strip().lower()
    
    unit_map = {
        'm': 'minutes',
        'h': 'hours', 
        'd': 'days',
        'w': 'weeks'
    }
    
    # Try to parse the environment variable first
    match = re.match(r'^(\d+)([mhdw])$', interval_str)
    
    if not match:
        # If env var is invalid and different from default, try default
        if env_key and interval_str != default_value:
            print(f"Invalid format for {env_key}: '{interval_str}' - using default: {default_value}")
            match = re.match(r'^(\d+)([mhdw])$', default_value)
            if not match:
                raise ValueError(f"Default value '{default_value}' is also invalid for {env_key}")
        else:
            raise ValueError(f"Invalid format for {env_key or 'interval'}: '{interval_str}' - expected format like '30m', '2h', or '1d'")
    
    value = int(match.group(1))
    unit = match.group(2)
    
    if unit not in unit_map:
        raise ValueError(f"{env_key or 'interval'} has invalid unit: {unit}. Use 'm' for minutes, 'h' for hours, 'd' for days, 'w' for weeks.")
    
    return value, unit_map[unit]

automatic_backup_interval = parse_interval_string("AUTOMATIC_BACKUP_INTERVAL", "7d")
clear_deleted_emails_interval = parse_interval_string("CLEAR_DELETED_EMAILS_INTERVAL", "1d")
send_scheduled_emails_interval = parse_interval_string("SEND_SCHEDULED_EMAILS_INTERVAL", "5m")
check_for_new_emails_interval = parse_interval_string("CHECK_FOR_NEW_EMAILS_INTERVAL", "30m")