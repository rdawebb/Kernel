"""Scheduler for periodic tasks like backups, email sending, and cleanup"""

## TODO: refactor to improve error handling and logging, check for redundant code
## TODO: refactor logging, use shared logger message format?

from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from tui_mail.core import storage_api
from tui_mail.core.imap_client import fetch_new_emails
from tui_mail.core.smtp_client import send_email
from tui_mail.utils.config import load_config
from tui_mail.utils.logger import get_logger

scheduler = BackgroundScheduler()
config = load_config()
logger = get_logger()

def automatic_backup():
    """Automatic database backup"""
    try:
        logger.info("Starting automatic database backup...")
        storage_api.backup_db()
        logger.info("Database backup completed successfully.")
    except Exception as e:
        logger.error(f"Error occurred during database backup: {e}")
        print("Sorry, something went wrong with the automatic database backup. Please check your settings or try again.")

def clear_deleted_emails():
    """Delete emails that have been in deleted folder for 30+ days"""
    try:
        deleted_emails = storage_api.get_deleted_emails()
        current_date = datetime.now().date()
        
        for email in deleted_emails:
            if email.get("deleted_at"):
                try:
                    deleted_date = datetime.strptime(email["deleted_at"], "%Y-%m-%d").date()
                    # Only delete emails older than 30 days to prevent accidental permanent deletion
                    if (current_date - deleted_date).days >= 30:
                        logger.info(f"Deleting email UID {email['uid']} from deleted_emails (older than 30 days)")
                        storage_api.delete_email_from_table("deleted_emails", email["uid"])
                except ValueError as e:
                    logger.error(f"Error parsing deleted_at date for email {email['uid']}: {e}")
                    print("Sorry, something went wrong while clearing deleted emails. Please check your settings or try again.")
                    continue

    except Exception as e:
        logger.error(f"Error clearing deleted emails: {e}")
        print("Sorry, something went wrong while clearing deleted emails. Please check your settings or try again.")

def send_scheduled_emails():
    """Send emails that are scheduled and ready to be sent"""
    try:
        pending_emails = storage_api.get_pending_emails()
        current_time = datetime.now()
        
        for email in pending_emails:
            if email.get("send_at"):
                try:
                    send_time = datetime.strptime(email["send_at"], "%Y-%m-%d %H:%M")
                    if current_time >= send_time:
                        logger.info(f"Sending scheduled email UID {email['uid']} to {email['recipient']}")

                        success = send_email(
                            to_email=email["recipient"],
                            subject=email["subject"],
                            body=email["body"]
                        )
                        
                        if success:
                            storage_api.update_email_status(email["uid"], "sent")
                            logger.info(f"Successfully sent email UID {email['uid']}")
                            print(f"Successfully sent scheduled email to {email['recipient']}")
                        else:
                            logger.error(f"Failed to send email UID {email['uid']}")
                            print(f"Failed to send scheduled email to {email['recipient']}")

                except ValueError as e:
                    logger.error(f"Error parsing send_at time for email {email['uid']}: {e}")
                    print(f"Sorry, something went wrong while sending scheduled email to {email['recipient']}. Please check your settings or try again.")
                    continue

                except Exception as e:
                    logger.error(f"Error sending email {email['uid']}: {e}")
                    print(f"Sorry, something went wrong while sending scheduled email to {email['recipient']}. Please check your settings or try again.")
                    continue

    except Exception as e:
        logger.error(f"Error in send_scheduled_emails: {e}")
        print("Sorry, something went wrong while sending scheduled emails. Please check your settings or try again.")

def check_for_new_emails():
    """Check for new emails in server every hour"""
    try:
        logger.info("Checking for new emails from server...")
        print("Checking for new emails from server...")
        new_emails = fetch_new_emails()
        if new_emails:
            logger.info(f"Downloaded {len(new_emails)} new emails from the server.")
            print(f"Downloaded {len(new_emails)} new emails from the server.")
        else:
            logger.info("No new emails found on server.")
            print("No new emails found on server.")
    except Exception as e:
        logger.error(f"Error checking for new emails: {e}")
        print("Sorry, something went wrong while checking for new emails. Please check your settings or try again.")

def start_scheduler():
    """Start the scheduler with all jobs"""

    automatic_backup_enabled = config.get("automatic_backup_enabled")
    automatic_backup_interval = config.get("automatic_backup_interval")

    clear_deleted_emails_enabled = config.get("clear_deleted_emails_enabled")
    clear_deleted_emails_interval = config.get("clear_deleted_emails_interval")

    send_scheduled_emails_enabled = config.get("send_scheduled_emails_enabled")
    send_scheduled_emails_interval = config.get("send_scheduled_emails_interval")

    check_for_new_emails_enabled = config.get("check_for_new_emails_enabled")
    check_for_new_emails_interval = config.get("check_for_new_emails_interval")

    enabled_jobs = []

    try:
        if automatic_backup_enabled:
            value, unit = automatic_backup_interval
            scheduler.add_job(
                automatic_backup, 
                'interval',
                **{unit: value},
                id='weekly_backup',
                replace_existing=True
            )
            enabled_jobs.append(('automatic_backup', automatic_backup_interval))

        if clear_deleted_emails_enabled:
            value, unit = clear_deleted_emails_interval
            scheduler.add_job(
                clear_deleted_emails,
                'interval',
                **{unit: value},
                id='clean_deleted_emails',
                replace_existing=True
            )
            enabled_jobs.append(('clear_deleted_emails', clear_deleted_emails_interval))

        # Check frequently to ensure timely delivery of scheduled emails
        if send_scheduled_emails_enabled:
            value, unit = send_scheduled_emails_interval
            scheduler.add_job(
                send_scheduled_emails,
                'interval',
                **{unit: value},
                id='send_scheduled_emails',
                replace_existing=True
            )
            enabled_jobs.append(('send_scheduled_emails', send_scheduled_emails_interval))

        if check_for_new_emails_enabled:
            value, unit = check_for_new_emails_interval
            scheduler.add_job(
                check_for_new_emails,
                'interval',
                **{unit: value},
                id='check_for_new_emails',
                replace_existing=True
            )
            enabled_jobs.append(('check_for_new_emails', check_for_new_emails_interval))

        scheduler.start()
        logger.info("Scheduler started with all jobs configured")
        logger.info(f"Enabled jobs: {enabled_jobs}")
        print("Scheduler started with all jobs configured")
        print(f"Enabled jobs: {enabled_jobs}")

    except Exception as e:
        logger.error(f"Error starting scheduler: {e}")
        print("Sorry, something went wrong while starting the scheduler. Please check your settings or try again.")

def stop_scheduler():
    """Stop the scheduler"""
    try:
        scheduler.shutdown()
        logger.info("Scheduler stopped")
        print("Scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}")
        print("Sorry, something went wrong while stopping the scheduler. Please check your settings or try again.")

# Call start_scheduler() when the application is ready