from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from quiet_mail.core import storage
from quiet_mail.core.smtp_client import send_email

scheduler = BackgroundScheduler()

def automatic_backup():
    """Weekly automatic database backup"""
    try:
        print("Starting automatic database backup...")
        storage.backup_db()
        print("Database backup completed successfully.")
    except Exception as e:
        print(f"Error occurred during database backup: {e}")

def clear_deleted_emails():
    """Delete emails that have been in deleted folder for 30+ days"""
    try:
        deleted_emails = storage.get_deleted_emails()  # TODO: implement this function
        current_date = datetime.now().date()
        
        for email in deleted_emails:
            if email.get("deleted_at"):
                try:
                    deleted_date = datetime.strptime(email["deleted_at"], "%Y-%m-%d").date()
                    # Only delete emails older than 30 days to prevent accidental permanent deletion
                    if (current_date - deleted_date).days >= 30:
                        print(f"Deleting email UID {email['uid']} from deleted_emails (older than 30 days)")
                        storage.delete_email_from_table("deleted_emails", email["uid"])
                except ValueError as e:
                    print(f"Error parsing deleted_at date for email {email['uid']}: {e}")
    except Exception as e:
        print(f"Error clearing deleted emails: {e}")

def send_scheduled_emails():
    """Send emails that are scheduled and ready to be sent"""
    try:
        pending_emails = storage.get_pending_emails()  # TODO: implement this function
        current_time = datetime.now()
        
        for email in pending_emails:
            if email.get("send_at"):
                try:
                    send_time = datetime.strptime(email["send_at"], "%Y-%m-%d %H:%M")
                    if current_time >= send_time:
                        print(f"Sending scheduled email UID {email['uid']} to {email['recipient']}")
                        
                        success = send_email(
                            to_email=email["recipient"],
                            subject=email["subject"],
                            body=email["body"]
                        )
                        
                        if success:
                            storage.update_email_status(email["uid"], "sent")  # TODO: implement this function
                            print(f"Successfully sent email UID {email['uid']}")
                        else:
                            print(f"Failed to send email UID {email['uid']}")
                            
                except ValueError as e:
                    print(f"Error parsing send_at time for email {email['uid']}: {e}")
                except Exception as e:
                    print(f"Error sending email {email['uid']}: {e}")
    except Exception as e:
        print(f"Error in send_scheduled_emails: {e}")

def start_scheduler():
    """Start the scheduler with all jobs"""
    try:
        scheduler.add_job(
            automatic_backup, 
            CronTrigger(day_of_week='sun', hour=0, minute=0),
            id='weekly_backup',
            replace_existing=True
        )
        
        scheduler.add_job(
            clear_deleted_emails,
            CronTrigger(hour=2, minute=0),
            id='clean_deleted_emails',
            replace_existing=True
        )
        
        # Check frequently to ensure timely delivery of scheduled emails
        scheduler.add_job(
            send_scheduled_emails,
            'interval',
            minutes=5,
            id='send_scheduled_emails',
            replace_existing=True
        )
        
        scheduler.start()
        print("Scheduler started with all jobs configured")
        
    except Exception as e:
        print(f"Error starting scheduler: {e}")

def stop_scheduler():
    """Stop the scheduler"""
    try:
        scheduler.shutdown()
        print("Scheduler stopped")
    except Exception as e:
        print(f"Error stopping scheduler: {e}")

# Call start_scheduler() when the application is ready