"""Scheduled job functions for the background scheduler.

NOTE: These functions use legacy APIs and are scheduled for refactoring.
They are not currently used by the CLI and require migration to the new
EngineManager/EmailRepository architecture.
"""

from src.core.email.imap.client import IMAPClient, SyncMode
from src.utils.config import ConfigManager
from src.utils.errors import KernelError, NetworkError
from src.utils.logging import async_log_call, get_logger

DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M"
CLEANUP_DAYS_THRESHOLD = 30


logger = get_logger(__name__)
config_manager = ConfigManager()


@async_log_call
async def automatic_backup() -> None:
    """Backup the database automatically.

    NOTE: Requires refactoring to use new BackupService API.
    """
    logger.warning(
        "automatic_backup() is not yet refactored for new database architecture"
    )
    pass


@async_log_call
async def clear_deleted_emails() -> None:
    """Delete emails from deleted folder older than 30 days.

    NOTE: Requires refactoring to use new EmailRepository API.
    """
    logger.warning(
        "clear_deleted_emails() is not yet refactored for new database architecture"
    )
    pass


@async_log_call
async def send_scheduled_emails() -> None:
    """Send emails that are ready to be sent.

    NOTE: Requires refactoring to use new EmailRepository and SMTPClient APIs.
    """
    logger.warning(
        "send_scheduled_emails() is not yet refactored for new database architecture"
    )
    pass


@async_log_call
async def check_for_new_emails() -> None:
    """Check for new emails from server."""

    logger.info("Checking for new emails from server...")

    try:
        account_config = config_manager.get_account_config()
        imap_client = IMAPClient(account_config)

        new_count = await imap_client.fetch_new_emails(
            account_config, SyncMode.INCREMENTAL
        )

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
