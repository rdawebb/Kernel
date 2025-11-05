"""Refresh command - fetch new emails from server"""

from typing import Any, Dict

from src.core.database import get_database
from src.core.imap_client import IMAPClient, SyncMode
from src.ui import inbox_viewer
from src.utils.console import print_status
from src.utils.error_handling import NetworkError, IMAPError
from src.utils.log_manager import async_log_call
from src.utils.ui_helpers import confirm_action

from .base import BaseCommandHandler, CommandResult


class RefreshCommandHandler(BaseCommandHandler):
    """Handler for the 'refresh' command to fetch new emails from the server."""

    @async_log_call
    async def execute_cli(self, args, config_manager) -> None:
        """Fetch new emails from the server (CLI mode)."""
        fetch_all = getattr(args, "all", False)
        limit = getattr(args, "limit", 50)

        sync_mode = SyncMode.FULL if fetch_all else SyncMode.INCREMENTAL

        if fetch_all:
            await print_status("Warning: Fetching all emails may take a long time and use significant bandwidth.")
            if not await confirm_action("Continue with full sync? (y/n): "):
                await print_status("Refresh cancelled", color="yellow")
                self.logger.info("User cancelled full sync")
                return False
            
        await print_status("Fetching new emails from server...")

        try:
            imap_client = IMAPClient(config_manager)
            fetched_count = await imap_client.fetch_new_emails(sync_mode)

            if fetched_count > 0:
                await print_status(f"Fetched {fetched_count} new email(s).", color="green")
            else:
                await print_status("No new emails found.", color="yellow")

            await print_status("Loading inbox...")
            db = get_database(config_manager)
            emails = await db.get_emails("inbox", limit=limit)

            if emails:
                await inbox_viewer.display_inbox(emails)
            else:
                await print_status("Inbox is empty.", color="cyan")

            self.logger.info(f"Refresh completed, fetched {fetched_count} new emails")
            return True

        except NetworkError as e:
            await print_status(f"Network error during refresh: {e.message}", color="red")
            self.logger.error(f"Network error during refresh: {e.message}")
            return False

        except IMAPError as e:
            await print_status(f"IMAP error during refresh: {e.message}", color="red")
            self.logger.error(f"IMAP error during refresh: {e.message}")
            return False

        except Exception as e:
            await print_status(f"Unexpected error during refresh: {str(e)}", color="red")
            self.logger.error(f"Unexpected error during refresh: {e}")
            return False

    @async_log_call
    async def execute_daemon(self, daemon, args: Dict[str, Any]) -> CommandResult:
        """Fetch new emails from the server (daemon mode)."""
        fetch_all = args.get("all", False)
        sync_mode = SyncMode.FULL if fetch_all else SyncMode.INCREMENTAL

        try:
            imap_client = IMAPClient(self.config_manager)
            
            fetched_count = await imap_client.fetch_new_emails(sync_mode)

            if fetched_count > 0:
                message = f"Fetched {fetched_count} new email(s) from server."
            else:
                message = "No new emails found on server."

            return self.success_result(
                data=message,
                fetched_count=fetched_count,
                sync_mode=sync_mode.value,
                imap_server=daemon.config.account.imap_server
            )
        
        except NetworkError as e:
            return self.error_result(
                f"Network error: {e.message}",
                error_type="network",
                details=e.details
            )
        
        except IMAPError as e:
            return self.error_result(
                f"IMAP error: {e.message}",
                error_type="imap",
                details=e.details
            )
        
        except Exception as e:
            return self.error_result(
                f"Unexpected error: {str(e)}",
                error_type="unknown",
            )

        