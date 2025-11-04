"""Attachments command - list and manage email attachments"""

from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Tuple

from rich.console import Console

from src.core.attachments import AttachmentManager
from src.core.database import get_database
from src.ui import inbox_viewer
from src.utils.console import print_status
from src.utils.error_handling import DatabaseError, ValidationError
from src.utils.log_manager import async_log_call

from .base import BaseCommandHandler, CommandResult


## Helper Methods

def _get_attachment_manager(config_manager, daemon=None) -> AttachmentManager:
    """Get attachment manager with proper config."""
    if daemon and hasattr(daemon, 'config_manager'):
        return AttachmentManager(daemon.config_manager)
    return AttachmentManager(config_manager)


def _render_attachment_list(attachment_list: List[str]) -> str:
    """Render attachment list with Rich formatting."""
    output_buffer = StringIO()
    output_console = Console(
        file=output_buffer,
        force_terminal=True,
        width=120,
        legacy_windows=False
    )
    
    if attachment_list:
        for i, filename in enumerate(attachment_list):
            output_console.print(f"  [cyan]{i}[/]: {filename}")
    else:
        output_console.print("[yellow]No attachments found[/]")
    
    return output_buffer.getvalue()


def _render_downloaded_files(downloaded_files: List[Tuple[Path, int]]) -> str:
    """Render downloaded files list with Rich formatting."""
    output_buffer = StringIO()
    output_console = Console(
        file=output_buffer,
        force_terminal=True,
        width=120,
        legacy_windows=False
    )
    
    if downloaded_files:
        output_console.print(f"[green]Found {len(downloaded_files)} downloaded attachment(s):[/]")
        for file_path, size in downloaded_files:
            output_console.print(f"  • {file_path.name} ({size} bytes)")
    else:
        output_console.print("[yellow]No downloaded attachments found[/]")
    
    return output_buffer.getvalue()


class AttachmentsCommandHandler(BaseCommandHandler):
    """Handler for the 'attachments' command with subcommand routing."""

    @async_log_call
    async def execute_cli(self, args, config_manager) -> None:
        """Route to appropriate subcommand handler (CLI mode)."""
        
        subcommand = getattr(args, "attachment_command", None)

        try:
            if subcommand == "list" or subcommand is None:
                # Default: list emails with attachments
                await self._list_emails_cli(args, config_manager)
            elif subcommand == "download":
                await self._download_attachments_cli(args, config_manager)
            elif subcommand == "downloads":
                await self._list_downloads_cli(args, config_manager)
            elif subcommand == "open":
                await self._open_attachment_cli(args, config_manager)
            else:
                raise ValidationError(
                    f"Unknown attachments subcommand: {subcommand}",
                    details={"subcommand": subcommand}
                )
        except (DatabaseError, ValidationError):
            raise

    @async_log_call
    async def execute_daemon(self, daemon, args: Dict[str, Any]) -> CommandResult:
        """Route to appropriate subcommand handler (daemon mode)."""
        
        subcommand = args.get("attachment_command", None)

        try:
            if subcommand == "list" or subcommand is None:
                return await self._list_emails_daemon(daemon, args)
            elif subcommand == "download":
                return await self._download_attachments_daemon(daemon, args)
            elif subcommand == "downloads":
                return await self._list_downloads_daemon(daemon, args)
            elif subcommand == "open":
                return await self._open_attachment_daemon(daemon, args)
            else:
                return self.error_result(
                    f"Unknown attachments subcommand: {subcommand}",
                    subcommand=subcommand
                )
        except (DatabaseError, ValidationError) as e:
            return self.error_result(str(e))


    ## CLI Subcommand Handlers

    async def _list_emails_cli(self, args, config_manager) -> None:
        """List emails with attachments (CLI)."""
        
        limit = getattr(args, "limit", 10)
        print_status("Loading emails with attachments...")

        db = get_database(config_manager)

        try:
            emails = await db.search_with_attachments("inbox", limit=limit)

            if not emails:
                print_status("No emails with attachments found.", color="yellow")
                self.logger.info("No emails with attachments found")
                return

            inbox_viewer.display_inbox("Emails with Attachments", emails)
            print_status(f"Found {len(emails)} email(s) with attachments.")
            self.logger.info(f"Listed {len(emails)} emails with attachments")

        except DatabaseError:
            raise

    async def _download_attachments_cli(self, args, config_manager) -> None:
        """Download email attachments (CLI)."""
        
        email_id = getattr(args, "id", None)
        download_all = getattr(args, "all", False)
        attachment_index = getattr(args, "index", None)

        self.validate_args({"id": email_id}, "id")

        if not download_all and attachment_index is None:
            raise ValidationError(
                "Please specify either --all to download all attachments or --index to download a specific attachment",
                details={"all": download_all, "index": attachment_index}
            )

        print_status(f"Downloading attachments for email {email_id}...")

        try:
            db = get_database(config_manager)
            email_data = await db.get_email("inbox", email_id, include_body=True)

            if not email_data:
                raise ValidationError(
                    f"Email with ID {email_id} not found",
                    details={"email_id": email_id}
                )

            attachment_manager = _get_attachment_manager(config_manager)
            
            if download_all:
                downloaded_files = attachment_manager.download_from_email_data(email_data)
            else:
                downloaded_files = attachment_manager.download_from_email_data(email_data, attachment_index=attachment_index)

            if not downloaded_files:
                print_status(f"No attachments found for email {email_id}", color="yellow")
                self.logger.info(f"No attachments to download for email {email_id}")
                return

            print_status(f"Successfully downloaded {len(downloaded_files)} attachment(s):")
            for file_path in downloaded_files:
                print_status(f"  • {file_path}")
            
            self.logger.info(f"Downloaded {len(downloaded_files)} attachment(s) for email {email_id}")

        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(
                f"Failed to download attachments: {e}",
                details={"email_id": email_id}
            )

    async def _list_downloads_cli(self, args, config_manager) -> None:
        """List all downloaded attachments (CLI)."""
        
        print_status("Loading downloaded attachments...")

        try:
            attachment_manager = _get_attachment_manager(config_manager)
            downloaded_files = attachment_manager.list_downloaded_attachments()

            if not downloaded_files:
                print_status("No downloaded attachments found.", color="yellow")
                self.logger.info("No downloaded attachments found")
                return

            print_status(f"Found {len(downloaded_files)} downloaded attachment(s):")
            for file_path, size in downloaded_files:
                print_status(f"  • {file_path.name} ({size} bytes)")

            self.logger.info(f"Listed {len(downloaded_files)} downloaded attachments")

        except Exception as e:
            raise ValidationError(
                f"Failed to list downloaded attachments: {e}",
                details={}
            )

    async def _open_attachment_cli(self, args, config_manager) -> None:
        """Open a downloaded attachment (CLI)."""
        
        filename = getattr(args, "filename", None)
        self.validate_args({"filename": filename}, "filename")

        print_status(f"Opening attachment: {filename}...")

        try:
            attachment_manager = _get_attachment_manager(config_manager)
            attachment_manager.open_attachment(filename)
            print_status(f"Opened attachment: {filename}")
            self.logger.info(f"Opened attachment: {filename}")

        except Exception as e:
            raise ValidationError(
                f"Failed to open attachment: {e}",
                details={"filename": filename}
            )


    ## Daemon Subcommand Handlers

    async def _list_emails_daemon(self, daemon, args: Dict[str, Any]) -> CommandResult:
        """List emails with attachments (daemon)."""

        limit = args.get("limit", 10)

        try:
            emails = await daemon.db.search_with_attachments("inbox", limit=limit)

            output_buffer = StringIO()
            output_console = Console(
                file=output_buffer,
                force_terminal=True,
                width=120,
                legacy_windows=False
            )

            if emails:
                output_console.print(f"[green]Found {len(emails)} email(s) with attachments:[/]")
                for email in emails:
                    output_console.print(f"  • {email.get('subject', 'No subject')} - {email.get('from', 'Unknown')}")
            else:
                output_console.print("[yellow]No emails with attachments found[/]")

            output = output_buffer.getvalue()

            return self.success_result(
                data=output,
                count=len(emails),
                folder="inbox"
            )

        except DatabaseError as e:
            return self.error_result(str(e))

    async def _download_attachments_daemon(self, daemon, args: Dict[str, Any]) -> CommandResult:
        """Download email attachments (daemon)."""

        email_id = args.get("id")
        download_all = args.get("all", False)
        attachment_index = args.get("index", None)

        self.validate_args({"id": email_id}, "id")

        if not download_all and attachment_index is None:
            return self.error_result(
                "Please specify either 'all' to download all attachments or 'index' to download a specific attachment",
                all=download_all,
                index=attachment_index
            )

        try:
            email_data = await daemon.db.get_email("inbox", email_id, include_body=True)

            if not email_data:
                return self.error_result(
                    f"Email with ID {email_id} not found",
                    email_id=email_id
                )

            attachment_manager = _get_attachment_manager(None, daemon)
            
            if download_all:
                downloaded_files = attachment_manager.download_from_email_data(email_data)
            else:
                downloaded_files = attachment_manager.download_from_email_data(email_data, attachment_index=attachment_index)

            if not downloaded_files:
                return self.error_result(
                    f"No attachments found for email {email_id}",
                    email_id=email_id
                )

            file_paths = [str(f) for f in downloaded_files]
            message = f"Successfully downloaded {len(downloaded_files)} attachment(s) from email {email_id}"

            return self.success_result(
                data=message,
                email_id=email_id,
                attachment_count=len(downloaded_files),
                downloaded_files=file_paths,
                download_all=download_all,
                index=attachment_index
            )

        except ValidationError as e:
            return self.error_result(str(e))

    async def _list_downloads_daemon(self, daemon, args: Dict[str, Any]) -> CommandResult:
        """List all downloaded attachments (daemon)."""

        try:
            attachment_manager = _get_attachment_manager(None, daemon)
            downloaded_files = attachment_manager.list_downloaded_attachments()
            output = _render_downloaded_files(downloaded_files)

            return self.success_result(
                data=output,
                count=len(downloaded_files)
            )

        except Exception as e:
            return self.error_result(str(e))

    async def _open_attachment_daemon(self, daemon, args: Dict[str, Any]) -> CommandResult:
        """Open a downloaded attachment (daemon)."""

        filename = args.get("filename")
        self.validate_args({"filename": filename}, "filename")

        try:
            attachment_manager = _get_attachment_manager(None, daemon)
            attachment_manager.open_attachment(filename)
            message = f"Opened attachment: {filename}"

            return self.success_result(
                data=message,
                filename=filename
            )

        except Exception as e:
            return self.error_result(str(e))
