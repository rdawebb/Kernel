"""Viewing command - display emails from different folders (inbox, sent, drafts, trash)"""

from typing import Any, Dict

from src.core.database import get_database
from src.utils.console import print_status
from src.utils.error_handling import DatabaseError, ValidationError
from src.utils.log_manager import async_log_call

from .base import BaseCommandHandler, CommandResult


class ViewingCommandHandler(BaseCommandHandler):
    """Handler for viewing commands with folder-based routing."""

    # Map commands to their corresponding folder names
    COMMAND_TO_FOLDER = {
        "inbox": "inbox",
        "sent": "sent",
        "drafts": "drafts",
        "trash": "trash"
    }

    @async_log_call
    async def execute_cli(self, args, config_manager) -> None:
        """Display emails from a folder (CLI mode)."""
        
        # Get the command to determine which folder to display
        command = getattr(args, "command", None)
        
        if command not in self.COMMAND_TO_FOLDER:
            raise ValidationError(
                f"Unknown viewing command: {command}",
                details={"command": command, "valid_commands": list(self.COMMAND_TO_FOLDER.keys())}
            )
        
        folder = self.COMMAND_TO_FOLDER[command]
        
        print_status(f"Loading {folder} emails...")

        db = get_database(config_manager)

        limit = getattr(args, "limit", 10)
        
        # Filter arguments
        flagged = getattr(args, "flagged", False)
        unflagged = getattr(args, "unflagged", False)
        unread = getattr(args, "unread", False)
        read = getattr(args, "read", False)
        with_attachments = getattr(args, "with_attachments", False)

        self.validate_table(folder)
        self.validate_args({"folder": folder, "limit": limit}, "folder", "limit")

        try:
            # Build filter dict
            filters = {}
            if flagged:
                filters["is_flagged"] = True
            if unflagged:
                filters["is_flagged"] = False
            if unread:
                filters["is_read"] = False
            if read:
                filters["is_read"] = True
            if with_attachments:
                filters["has_attachments"] = True

            if filters:
                emails = await db.get_filtered_emails(folder, limit=limit, **filters)
            else:
                emails = await db.get_emails(folder, limit=limit, include_body=False)

        except DatabaseError:
            raise

        from src.ui import inbox_viewer
        inbox_viewer.display_inbox(emails, folder)

        self.logger.info(f"Listed {len(emails)} emails from {folder}")

    @async_log_call
    async def execute_daemon(self, daemon, args: Dict[str, Any]) -> CommandResult:
        """Display emails from a folder (daemon mode)."""

        # Get the command to determine which folder to display
        command = args.get("command")
        
        if command not in self.COMMAND_TO_FOLDER:
            return self.error_result(
                f"Unknown viewing command: {command}",
                command=command,
                valid_commands=list(self.COMMAND_TO_FOLDER.keys())
            )
        
        folder = self.COMMAND_TO_FOLDER[command]
        
        limit = args.get("limit", 50)
        
        # Filter arguments
        flagged = args.get("flagged", False)
        unflagged = args.get("unflagged", False)
        unread = args.get("unread", False)
        read = args.get("read", False)
        with_attachments = args.get("with_attachments", False)

        self.validate_table(folder)
        self.validate_args({"folder": folder, "limit": limit}, "folder", "limit")

        try:
            # Build filter dict
            filters = {}
            if flagged:
                filters["is_flagged"] = True
            if unflagged:
                filters["is_flagged"] = False
            if unread:
                filters["is_read"] = False
            if read:
                filters["is_read"] = True
            if with_attachments:
                filters["has_attachments"] = True

            if filters:
                emails = await daemon.db.get_filtered_emails(folder, limit=limit, **filters)
            else:
                emails = await daemon.db.get_emails(folder, limit=limit, include_body=False)

        except DatabaseError:
            raise

        from src.ui import table_viewer

        output = self.render_for_daemon(
            table_viewer.display_email_table,
            emails,
            title=folder.replace("_", " ").title()
        )

        return self.success_result(
            data=output,
            count=len(emails),
            folder=folder
        )
