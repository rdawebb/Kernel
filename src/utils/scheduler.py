"""Scheduler for periodic tasks like backups, email sending, and cleanup"""

from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from src.core import storage_api
from src.core.imap_client import fetch_new_emails
from src.core.smtp_client import send_email
from .config_manager import ConfigManager
from .log_manager import get_logger, log_call

DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M"

scheduler = BackgroundScheduler()
logger = get_logger(__name__)
config_manager = ConfigManager()


# ========================================
# Scheduled Job Functions
# ========================================

@log_call
def automatic_backup():
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
def clear_deleted_emails():
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
                    if (current_date - deleted_date).days >= 30:
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
def send_scheduled_emails():
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
def check_for_new_emails():
    """Check for new emails from server."""
    logger.info("Checking for new emails from server...")
    
    try:
        new_emails = fetch_new_emails()
        
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

def _get_config_value(key: str, default=None):
    """Safely retrieve config value with default fallback."""
    value = config_manager.get_config(key)
    if value is None:
        logger.warning(f"Config key '{key}' not found, using default: {default}")
        return default
    return value

def _validate_interval(job_name: str, interval_tuple) -> bool:
    """Validate interval tuple format (value, unit)."""
    if not isinstance(interval_tuple, tuple) or len(interval_tuple) != 2:
        logger.error(f"Invalid interval format for {job_name}: {interval_tuple}")
        return False
    
    value, unit = interval_tuple
    valid_units = ["seconds", "minutes", "hours", "days", "weeks"]
    
    if not isinstance(value, int) or value <= 0:
        logger.error(f"Invalid interval value for {job_name}: {value} (must be positive integer)")
        return False
    
    if unit not in valid_units:
        logger.error(f"Invalid interval unit for {job_name}: {unit} (must be one of {valid_units})")
        return False
    
    return True

def _add_job_if_enabled(job_func, job_name: str, job_id: str, enabled: bool, interval: tuple) -> bool:
    """Add job to scheduler if enabled and validated."""
    if not enabled:
        return False
    
    if not _validate_interval(job_name, interval):
        logger.warning(f"Skipping job {job_name} due to invalid interval configuration")
        return False
    
    try:
        value, unit = interval
        scheduler.add_job(
            job_func,
            'interval',
            **{unit: value},
            id=job_id,
            replace_existing=True
        )
        logger.info(f"Added job: {job_name} (interval: {value} {unit})")
        return True
    except Exception as e:
        logger.error(f"Failed to add job {job_name}: {e}")
        return False

@log_call
def start_scheduler():
    """Start scheduler with all configured jobs."""
    logger.info("Initializing scheduler with configured jobs...")
    
    # Load configuration with validation
    jobs_config = {
        "automatic_backup": {
            "enabled": _get_config_value("automatic_backup_enabled", False),
            "interval": _get_config_value("automatic_backup_interval", (1, "hours")),
            "func": automatic_backup,
            "id": "automatic_backup"
        },
        "clear_deleted_emails": {
            "enabled": _get_config_value("clear_deleted_emails_enabled", False),
            "interval": _get_config_value("clear_deleted_emails_interval", (1, "days")),
            "func": clear_deleted_emails,
            "id": "clear_deleted_emails"
        },
        "send_scheduled_emails": {
            "enabled": _get_config_value("send_scheduled_emails_enabled", False),
            "interval": _get_config_value("send_scheduled_emails_interval", (5, "minutes")),
            "func": send_scheduled_emails,
            "id": "send_scheduled_emails"
        },
        "check_for_new_emails": {
            "enabled": _get_config_value("check_for_new_emails_enabled", False),
            "interval": _get_config_value("check_for_new_emails_interval", (1, "hours")),
            "func": check_for_new_emails,
            "id": "check_for_new_emails"
        }
    }
    
    enabled_jobs = []
    
    try:
        # Add each job if it's enabled and validated
        for job_name, config_dict in jobs_config.items():
            if _add_job_if_enabled(
                config_dict["func"],
                job_name,
                config_dict["id"],
                config_dict["enabled"],
                config_dict["interval"]
            ):
                enabled_jobs.append((job_name, config_dict["interval"]))
        
        # Start the scheduler
        if not scheduler.running:
            scheduler.start()
            logger.info(f"Scheduler started with {len(enabled_jobs)} job(s)")
            print(f"Scheduler started with {len(enabled_jobs)} job(s) configured")
            if enabled_jobs:
                logger.info(f"Enabled jobs: {enabled_jobs}")
        else:
            logger.info("Scheduler is already running")
    
    except Exception as e:
        logger.error(f"Error starting scheduler: {e}")
        print("Sorry, something went wrong while starting the scheduler. Please check your settings or try again.")

@log_call
def stop_scheduler():
    """Stop scheduler gracefully."""
    try:
        if scheduler.running:
            scheduler.shutdown()
            logger.info("Scheduler stopped")
            print("Scheduler stopped")
        else:
            logger.info("Scheduler is not running")
    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}")
        print("Sorry, something went wrong while stopping the scheduler. Please check your settings or try again.")