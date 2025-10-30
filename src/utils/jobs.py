"""Scheduled job functions for the background scheduler."""

from datetime import datetime
from src.core.database import get_database
from src.core.imap_client import IMAPClient, SyncMode
from src.core.smtp_client import SMTPClient
from src.utils.config_manager import ConfigManager
from src.utils.error_handling import (
    NetworkError,
    DatabaseError,
    KernelError,
    ValidationError,
)
from src.utils.log_manager import get_logger, log_call


DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M"
CLEANUP_DAYS_THRESHOLD = 30


logger = get_logger(__name__)
config_manager = ConfigManager()


@log_call
def automatic_backup() -> None:
    """Backup the database automatically."""
    logger.info("Starting automatic database backup...")
    try:
        db = get_database(config_manager)
        backup_path = db.backup()
        logger.info(f"Database backup completed successfully: {backup_path}")
        print(f"Database backup completed successfully: {backup_path}")
    except DatabaseError:
        raise
    except KernelError:
        raise
    except Exception as e:
        raise DatabaseError("Unexpected error during database backup") from e


@log_call
def clear_deleted_emails() -> None:
    """Delete emails from deleted folder older than 30 days."""
    logger.info("Starting cleanup of old deleted emails...")
    
    try:
        db = get_database(config_manager)
        deleted_emails = db.get_emails("deleted_emails", limit=9999)
        current_date = datetime.now().date()
        deleted_count = 0
        
        for email in deleted_emails:
            if email.get("deleted_at"):
                try:
                    deleted_date = datetime.strptime(email["deleted_at"], DATE_FORMAT).date()

                    if (current_date - deleted_date).days >= CLEANUP_DAYS_THRESHOLD:
                        db.delete_email("deleted_emails", email["uid"])
                        deleted_count += 1

                except ValueError as e:
                    raise ValidationError(f"Could not parse deleted_at date for email {email['uid']}: {str(e)}") from e
        
        if deleted_count > 0:
            logger.info(f"Cleanup completed: {deleted_count} old emails permanently deleted.")
            print(f"Cleanup completed: {deleted_count} old emails permanently deleted.")
        else:
            logger.info("Cleanup completed: no old emails to delete.")
            print("Cleanup completed: no old emails to delete.")

    except DatabaseError:
        raise
    except KernelError:
        raise
    except Exception as e:
        raise DatabaseError("Unexpected error during email cleanup") from e

@log_call
def send_scheduled_emails() -> None:
    """Send emails that are ready to be sent."""
    logger.info("Checking for scheduled emails ready to send...")
    
    try:
        db = get_database(config_manager)
        pending_emails = db.get_pending_emails()
        current_time = datetime.now()
        sent_count = 0
        failed_count = 0
        
        account_config = config_manager.get_account_config()
        smtp_client = SMTPClient(
            host=account_config["smtp_server"],
            port=account_config["smtp_port"],
            username=account_config["username"],
            password=account_config.get("password", ""),
            use_tls=account_config.get("use_tls", True)
        )

        for email in pending_emails:
            if not email.get("send_at"):
                continue
                
            try:
                send_time = datetime.strptime(email["send_at"], DATETIME_FORMAT)
                
                if current_time >= send_time:
                    logger.info(f"Sending scheduled email UID {email['uid']} to {email['recipient']}")

                    success = smtp_client.send_email(
                        to_email=email["recipient"],
                        subject=email["subject"],
                        body=email["body"]
                    )
                    
                    if success:
                        db.update_field("sent_emails", email["uid"], "status", "sent")
                        sent_count += 1
                        logger.info(f"Successfully sent email UID {email['uid']} to {email['recipient']}")
                    else:
                        failed_count += 1
                        logger.error(f"Failed to send email UID {email['uid']} to {email['recipient']}")
                    
            except ValueError as e:
                raise ValidationError(f"Could not parse send_at time for email {email['uid']}: {str(e)}") from e

        smtp_client.close
        
        if sent_count > 0 or failed_count > 0:
            msg = f"Scheduled email processing completed: {sent_count} sent, {failed_count} failed."
            logger.info(msg)
            print(msg)
        else:
            logger.info("No scheduled emails ready to send.")
            print("No scheduled emails ready to send.")

    except (DatabaseError, NetworkError):
        raise
    except KernelError:
        raise
    except Exception as e:
        raise NetworkError("Unexpected error during scheduled email processing") from e

@log_call
def check_for_new_emails() -> None:
    """Check for new emails from server."""
    logger.info("Checking for new emails from server...")
    
    try:
        account_config = config_manager.get_account_config()
        imap_client = IMAPClient(account_config)

        new_count = imap_client.fetch_new_emails(account_config, SyncMode.INCREMENTAL)

        if new_count > 0:
            msg = f"Downloaded {new_count} new email(s) from the server."
            logger.info(msg)
            print(msg)
        else:
            logger.info("No new emails found on server.")
            print("No new emails found on server.")

    except NetworkError:
        raise
    except KernelError:
        raise
    except Exception as e:
        raise NetworkError("Unexpected error while checking for new emails") from e
