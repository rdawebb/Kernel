"""Scheduled job functions for the background scheduler."""

from datetime import datetime
from src.core import storage_api
from src.core.imap_client import fetch_new_emails
from src.core.smtp_client import send_email
from .config_manager import ConfigManager
from .log_manager import get_logger, log_call

# Constants
DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M"
CLEANUP_DAYS_THRESHOLD = 30

# Module-level instances
logger = get_logger(__name__)
config_manager = ConfigManager()


@log_call
def automatic_backup() -> None:
    """Backup the database automatically."""
    logger.info("Starting automatic database backup...")
    try:
        storage_api.backup_db()
        logger.info("Database backup completed successfully.")
        print("Database backup completed successfully.")
    except Exception as e:
        logger.error(f"automatic_backup error: {type(e).__name__}: {e}")
        print("Sorry, something went wrong with automatic backup. Please check your settings or try again.")

@log_call
def clear_deleted_emails() -> None:
    """Delete emails from deleted folder older than 30 days."""
    logger.info("Starting cleanup of old deleted emails...")
    
    try:
        deleted_emails = storage_api.get_deleted_emails()
        current_date = datetime.now().date()
        deleted_count = 0
        
        for email in deleted_emails:
            if email.get("deleted_at"):
                try:
                    deleted_date = datetime.strptime(email["deleted_at"], DATE_FORMAT).date()
                    # Only delete emails older than 30 days to prevent accidental permanent deletion
                    if (current_date - deleted_date).days >= CLEANUP_DAYS_THRESHOLD:
                        storage_api.delete_email_from_table("deleted_emails", email["uid"])
                        deleted_count += 1
                except ValueError as e:
                    logger.warning(f"Could not parse deleted_at date for email {email['uid']}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Cleanup completed: {deleted_count} old emails permanently deleted.")
            print(f"Cleanup completed: {deleted_count} old emails permanently deleted.")
        else:
            logger.info("Cleanup completed: no old emails to delete.")
            print("Cleanup completed: no old emails to delete.")
    except Exception as e:
        logger.error(f"clear_deleted_emails error: {type(e).__name__}: {e}")
        print("Sorry, something went wrong with cleanup. Please check your settings or try again.")

@log_call
def send_scheduled_emails() -> None:
    """Send emails that are ready to be sent."""
    logger.info("Checking for scheduled emails ready to send...")
    
    try:
        pending_emails = storage_api.get_pending_emails()
        current_time = datetime.now()
        sent_count = 0
        failed_count = 0
        
        for email in pending_emails:
            if not email.get("send_at"):
                continue
                
            try:
                send_time = datetime.strptime(email["send_at"], DATETIME_FORMAT)
                
                if current_time >= send_time:
                    logger.info(f"Sending scheduled email UID {email['uid']} to {email['recipient']}")
                    
                    success = send_email(
                        to_email=email["recipient"],
                        subject=email["subject"],
                        body=email["body"]
                    )
                    
                    if success:
                        storage_api.update_email_status(email["uid"], "sent")
                        sent_count += 1
                        logger.info(f"Successfully sent email UID {email['uid']} to {email['recipient']}")
                    else:
                        failed_count += 1
                        logger.error(f"Failed to send email UID {email['uid']} to {email['recipient']}")
                    
            except ValueError as e:
                logger.warning(f"Could not parse send_at time for email {email['uid']}: {e}")
                failed_count += 1
        
        if sent_count > 0 or failed_count > 0:
            msg = f"Scheduled email processing completed: {sent_count} sent, {failed_count} failed."
            logger.info(msg)
            print(msg)
        else:
            logger.info("No scheduled emails ready to send.")
            print("No scheduled emails ready to send.")
    except Exception as e:
        logger.error(f"send_scheduled_emails error: {type(e).__name__}: {e}")
        print("Sorry, something went wrong with scheduled emails. Please check your settings or try again.")

@log_call
def check_for_new_emails() -> None:
    """Check for new emails from server."""
    logger.info("Checking for new emails from server...")
    
    try:
        from src.core.imap_client import SyncMode
        account_config = config_manager.get_account_config()
        new_emails = fetch_new_emails(account_config, SyncMode.INCREMENTAL)
        
        if new_emails:
            msg = f"Downloaded {len(new_emails)} new emails from the server."
            logger.info(msg)
            print(msg)
        else:
            logger.info("No new emails found on server.")
            print("No new emails found on server.")
    except Exception as e:
        logger.error(f"check_for_new_emails error: {type(e).__name__}: {e}")
        print("Sorry, something went wrong while checking for new emails. Please check your settings or try again.")
