"""Scheduler for periodic tasks like backups, email sending, and cleanup"""

from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from src.core import storage_api
from src.core.imap_client import fetch_new_emails
from src.core.smtp_client import send_email
from src.utils.config import load_config
from src.utils.logger import get_logger

DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M"

scheduler = BackgroundScheduler()
config = load_config()
logger = get_logger()


def handle_job_error(job_name: str):
    """Decorator for standardized error handling and logging in scheduled jobs."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"[{job_name}] {type(e).__name__}: {e}")
                print(f"Sorry, something went wrong with {job_name}. Please check your settings or try again.")
        return wrapper
    return decorator


def log_job_start(message: str):
    """Log and print job start message."""
    logger.info(message)
    print(message)


def log_job_completion(message: str):
    """Log and print job completion message."""
    logger.info(message)
    print(message)


# ========================================
# Scheduled Job Functions
# ========================================

@handle_job_error("automatic_backup")
def automatic_backup():
    """Backup the database automatically."""
    log_job_start("Starting automatic database backup...")
    storage_api.backup_db()
    log_job_completion("Database backup completed successfully.")


@handle_job_error("clear_deleted_emails")
def clear_deleted_emails():
    """Delete emails from deleted folder older than 30 days."""
    log_job_start("Starting cleanup of old deleted emails...")
    
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
        log_job_completion(f"Cleanup completed: {deleted_count} old emails permanently deleted.")
    else:
        log_job_completion("Cleanup completed: no old emails to delete.")


@handle_job_error("send_scheduled_emails")
def send_scheduled_emails():
    """Send emails that are ready to be sent."""
    log_job_start("Checking for scheduled emails ready to send...")
    
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
        log_job_completion(f"Scheduled email processing completed: {sent_count} sent, {failed_count} failed.")
    else:
        log_job_completion("No scheduled emails ready to send.")


@handle_job_error("check_for_new_emails")
def check_for_new_emails():
    """Check for new emails from server."""
    log_job_start("Checking for new emails from server...")
    
    new_emails = fetch_new_emails()
    
    if new_emails:
        log_job_completion(f"Downloaded {len(new_emails)} new emails from the server.")
    else:
        log_job_completion("No new emails found on server.")

def _get_config_value(key: str, default=None):
    """Safely retrieve config value with default fallback."""
    value = config.get(key)
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
            log_job_completion(f"Scheduler started with {len(enabled_jobs)} job(s) configured")
            if enabled_jobs:
                logger.info(f"Enabled jobs: {enabled_jobs}")
        else:
            logger.info("Scheduler is already running")
    
    except Exception as e:
        logger.error(f"Error starting scheduler: {e}")
        print("Sorry, something went wrong while starting the scheduler. Please check your settings or try again.")


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