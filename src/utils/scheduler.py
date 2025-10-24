"""Scheduler for periodic tasks like backups, email sending, and cleanup"""

from apscheduler.schedulers.background import BackgroundScheduler
from .config_manager import ConfigManager
from .log_manager import get_logger, log_call
from .jobs import automatic_backup, check_for_new_emails

# Constants
VALID_INTERVAL_UNITS = ["seconds", "minutes", "hours", "days", "weeks"]

# Module-level instances
scheduler = BackgroundScheduler()
logger = get_logger(__name__)
config_manager = ConfigManager()


def _validate_interval(job_name: str, interval_tuple: tuple) -> bool:
    """Validate interval tuple format (value, unit)."""

    if not isinstance(interval_tuple, tuple) or len(interval_tuple) != 2:
        logger.error(f"Invalid interval format for {job_name}: {interval_tuple}")
        return False
    
    value, unit = interval_tuple
    
    if not isinstance(value, int) or value <= 0:
        logger.error(f"Invalid interval value for {job_name}: {value} (must be positive integer)")
        return False
    
    if unit not in VALID_INTERVAL_UNITS:
        logger.error(f"Invalid interval unit for {job_name}: {unit} (must be one of {VALID_INTERVAL_UNITS})")
        return False
    
    return True

def _add_job_if_enabled(job_func: callable, job_name: str, job_id: str, enabled: bool, interval: tuple) -> bool:
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

def _build_jobs_registry() -> dict:
    """Build registry of scheduled jobs from config."""

    features = config_manager.config.features
    
    return {
        "automatic_backup": {
            "enabled": features.auto_backup,
            "interval": (features.auto_backup_interval, "minutes"),
            "func": automatic_backup,
            "id": "automatic_backup"
        },
        "auto_sync": {
            "enabled": features.auto_sync,
            "interval": (features.auto_sync_interval, "minutes"),
            "func": check_for_new_emails,
            "id": "auto_sync"
        }
    }

@log_call
def start_scheduler() -> None:
    """Start scheduler with all configured jobs."""
    logger.info("Initializing scheduler with configured jobs...")
    
    jobs_config = _build_jobs_registry()
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
def stop_scheduler() -> None:
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