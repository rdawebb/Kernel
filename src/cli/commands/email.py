"""Email command - email operations (view, delete, flag, unflag, move)"""

from datetime import datetime
from typing import Any, Dict

from src.core.database import get_database
from src.ui import email_viewer
from src.utils.console import print_status
from src.utils.error_handling import DatabaseError, ValidationError
from src.utils.log_manager import async_log_call
from src.utils.ui_helpers import confirm_action

from .base import BaseCommandHandler, CommandResult


class EmailCommandHandler(BaseCommandHandler):
    """Handler for email operations with subcommand routing."""

    @async_log_call
    async def execute_cli(self, args, config_manager) -> None:
        """Route to appropriate email operation (CLI mode)."""
        email_command = getattr(args, "email_command", None)

        if email_command == "view":
            return await self._view_cli(args, config_manager)
        elif email_command == "delete":
            return await self._delete_cli(args, config_manager)
        elif email_command == "flag":
            return await self._flag_cli(args, config_manager)
        elif email_command == "unflag":
            return await self._unflag_cli(args, config_manager)
        elif email_command == "move":
            return await self._move_cli(args, config_manager)
        else:
            raise ValidationError(
                f"Unknown email command: {email_command}",
                details={"email_command": email_command}
            )

    @async_log_call
    async def execute_daemon(self, daemon, args: Dict[str, Any]) -> CommandResult:
        """Route to appropriate email operation (daemon mode)."""
        email_command = args.get("email_command")

        if email_command == "view":
            return await self._view_daemon(daemon, args)
        elif email_command == "delete":
            return await self._delete_daemon(daemon, args)
        elif email_command == "flag":
            return await self._flag_daemon(daemon, args)
        elif email_command == "unflag":
            return await self._unflag_daemon(daemon, args)
        elif email_command == "move":
            return await self._move_daemon(daemon, args)
        else:
            return self.error_result(
                f"Unknown email command: {email_command}",
                email_command=email_command
            )


    # View operations

    async def _view_cli(self, args, config_manager) -> None:
        """View a specific email by ID (CLI mode)."""
        email_id = getattr(args, "id", None)
        table = getattr(args, "folder", "inbox")

        self.validate_args({"id": email_id, "folder": table}, "id", "folder")
        self.validate_table(table)
        
        await print_status(f"Fetching email {email_id} from {table}...")

        db = get_database(config_manager)

        try:
            email_data = await db.get_email(table, email_id, include_body=True)

            if not email_data:
                raise ValidationError(
                    f"Email with ID {email_id} not found in {table}",
                    details={"table": table, "email_id": email_id}
                )
            
            from src.ui import email_viewer
            await email_viewer.display_email(email_data)
            self.logger.info(f"Viewed email {email_id} from {table}")
            return True

        except (DatabaseError, ValidationError) as e:
            await print_status(f"[red]Error: {e}[/]")
            self.logger.error(f"Error during email view: {e}")
            return False

    async def _view_daemon(self, daemon, args: Dict[str, Any]) -> CommandResult:
        """View a specific email by ID (daemon mode)."""
        email_id = args.get("id")
        table = args.get("folder", "inbox")

        self.validate_args({"id": email_id, "folder": table}, "id", "folder")
        self.validate_table(table)

        try:
            email_data = await daemon.db.get_email(table, email_id, include_body=True)

            if not email_data:
                return self.error_result(
                    f"Email with ID {email_id} not found in {table}",
                    email_id=email_id,
                    table=table
                )

            output = self.render_for_daemon(
                await email_viewer.display_email,
                email_data
            )

            return self.success_result(
                data=output,
                email_id=email_data.get("uid"),
                table=table
            )

        except (DatabaseError, ValidationError) as e:
            return self.error_result(str(e))


    # Delete operations

    async def _delete_cli(self, args, config_manager) -> None:
        """Delete emails by ID from specified table (CLI mode)."""
        email_id = getattr(args, "id", None)
        permanent = getattr(args, "permanent", False)
        
        # Determine folder - if permanent delete is requested, assume trash
        table = "trash" if permanent else getattr(args, "folder", "inbox")
        
        self.validate_args({"id": email_id}, "id")
        self.validate_table(table)

        db = get_database(config_manager)

        try:
            if not await db.email_exists(table, email_id):
                raise ValidationError(
                    f"Email with ID {email_id} not found in {table}",
                    details={"table": table, "email_id": email_id}
                )
            
            if table == "trash" or permanent:
                if not await confirm_action("Permanently delete the email(s) from 'trash'? This action cannot be undone - (y/n): "):
                    await print_status("Deletion cancelled", color="yellow")
                    return False
                
                await db.delete_email("trash", email_id)
                await print_status(f"Permanently deleted email(s) with ID {email_id} from 'trash'.")
            else:
                if not await confirm_action(f"Delete email(s) {email_id} from '{table}'? - (y/n): "):
                    await print_status("Deletion cancelled", color="yellow")
                    return False

                await db.move_email(table, "trash", email_id, deleted_at=datetime.now())
                await print_status(f"Deleted email {email_id} from '{table}'.")

            self.logger.info(f"Deleted email {email_id} from {table}")
            return True

        except (DatabaseError, ValidationError) as e:
            await print_status(f"[red]Error: {e}[/]")
            self.logger.error(f"Error during email deletion: {e}")
            return False

    async def _delete_daemon(self, daemon, args: Dict[str, Any]) -> CommandResult:
        """Delete emails by ID from specified table (daemon mode)."""
        email_id = args.get("id")
        permanent = args.get("permanent", False)
        table = "trash" if permanent else args.get("folder", "inbox")

        self.validate_args({"id": email_id}, "id")
        self.validate_table(table)

        try:
            if not await daemon.db.email_exists(table, email_id):
                return self.error_result(
                    f"Email with ID {email_id} not found in {table}",
                    email_id=email_id,
                    table=table
                )
            
            if table == "trash" or permanent:
                await daemon.db.delete_email("trash", email_id)
                message = f"Permanently deleted email with ID {email_id} from 'trash'."
            else:
                await daemon.db.move_email(table, "trash", email_id, deleted_at=datetime.now())
                message = f"Deleted email with ID {email_id} from '{table}'."

            return self.success_result(
                data=message,
                email_id=email_id,
                table=table
            )

        except (DatabaseError, ValidationError) as e:
            return self.error_result(str(e))


    # Flag operations

    async def _flag_cli(self, args, config_manager) -> None:
        """Flag an email by ID (CLI mode)."""
        email_id = getattr(args, "id", None)

        self.validate_args({"id": email_id}, "id")

        db = get_database(config_manager)

        try:
            if not await db.email_exists("inbox", email_id):
                raise ValidationError(
                    f"Email with ID {email_id} not found in 'inbox'",
                    details={"table": "inbox", "email_id": email_id}
                )
            
            await db.update_field("inbox", email_id, "flagged", 1)
            await print_status(f"Flagged email with ID {email_id}.")
            self.logger.info(f"Flagged email {email_id} in inbox")
            return True

        except (DatabaseError, ValidationError) as e:
            await print_status(f"[red]Error: {e}[/]")
            self.logger.error(f"Error during email flagging: {e}")
            return False

    async def _flag_daemon(self, daemon, args: Dict[str, Any]) -> CommandResult:
        """Flag an email by ID (daemon mode)."""
        email_id = args.get("id")

        self.validate_args({"id": email_id}, "id")

        try:
            if not await daemon.db.email_exists("inbox", email_id):
                return self.error_result(
                    f"Email with ID {email_id} not found in 'inbox'",
                    email_id=email_id,
                    table="inbox"
                )

            await daemon.db.update_field("inbox", email_id, "flagged", 1)
            message = f"Flagged email with ID {email_id}."

            return self.success_result(
                data=message,
                email_id=email_id,
                action="flagged"
            )

        except (DatabaseError, ValidationError) as e:
            return self.error_result(str(e))


    # Unflag operations

    async def _unflag_cli(self, args, config_manager) -> None:
        """Unflag an email by ID (CLI mode)."""
        email_id = getattr(args, "id", None)

        self.validate_args({"id": email_id}, "id")

        db = get_database(config_manager)

        try:
            if not await db.email_exists("inbox", email_id):
                raise ValidationError(
                    f"Email with ID {email_id} not found in 'inbox'",
                    details={"table": "inbox", "email_id": email_id}
                )
            
            await db.update_field("inbox", email_id, "flagged", 0)
            await print_status(f"Unflagged email with ID {email_id}.")
            self.logger.info(f"Unflagged email {email_id} in inbox")
            return True

        except (DatabaseError, ValidationError) as e:
            await print_status(f"[red]Error: {e}[/]")
            self.logger.error(f"Error during email unflagging: {e}")
            return False

    async def _unflag_daemon(self, daemon, args: Dict[str, Any]) -> CommandResult:
        """Unflag an email by ID (daemon mode)."""
        email_id = args.get("id")

        self.validate_args({"id": email_id}, "id")

        try:
            if not await daemon.db.email_exists("inbox", email_id):
                return self.error_result(
                    f"Email with ID {email_id} not found in 'inbox'",
                    email_id=email_id,
                    table="inbox"
                )

            await daemon.db.update_field("inbox", email_id, "flagged", 0)
            message = f"Unflagged email with ID {email_id}."

            return self.success_result(
                data=message,
                email_id=email_id,
                action="unflagged"
            )

        except (DatabaseError, ValidationError) as e:
            return self.error_result(str(e))


    # Move operations

    async def _move_cli(self, args, config_manager) -> None:
        """Move email from source to destination folder (CLI mode)."""
        email_id = getattr(args, "id", None)
        source_table = getattr(args, "source", "inbox")
        dest_table = getattr(args, "destination", "trash")

        self.validate_args({"id": email_id, "source": source_table, "destination": dest_table}, "id", "source", "destination")
        self.validate_table(source_table)
        self.validate_table(dest_table)

        if source_table == dest_table:
            raise ValidationError(
                "Source and destination folders must be different",
                details={"source": source_table, "destination": dest_table}
            )

        await print_status(f"Moving email {email_id} from {source_table} to {dest_table}...")

        db = get_database(config_manager)

        try:
            if not await db.email_exists(source_table, email_id):
                raise ValidationError(
                    f"Email with ID {email_id} not found in {source_table}",
                    details={"table": source_table, "email_id": email_id}
                )
            
            await db.move_email(source_table, dest_table, email_id)
            await print_status(f"Moved email {email_id} from '{source_table}' to '{dest_table}'.")
            self.logger.info(f"Moved email {email_id} from {source_table} to {dest_table}")
            return True

        except (DatabaseError, ValidationError) as e:
            await print_status(f"[red]Error: {e}[/]")
            self.logger.error(f"Error during email moving: {e}")
            return False

    async def _move_daemon(self, daemon, args: Dict[str, Any]) -> CommandResult:
        """Move email from source to destination folder (daemon mode)."""
        email_id = args.get("id")
        source_table = args.get("source", "inbox")
        dest_table = args.get("destination", "trash")

        self.validate_args({"id": email_id, "source": source_table, "destination": dest_table}, "id", "source", "destination")
        self.validate_table(source_table)
        self.validate_table(dest_table)

        if source_table == dest_table:
            return self.error_result(
                "Source and destination folders must be different",
                source=source_table,
                destination=dest_table
            )

        try:
            if not await daemon.db.email_exists(source_table, email_id):
                return self.error_result(
                    f"Email with ID {email_id} not found in {source_table}",
                    email_id=email_id,
                    source=source_table
                )

            await daemon.db.move_email(source_table, dest_table, email_id)
            message = f"Moved email with ID {email_id} from '{source_table}' to '{dest_table}'."

            return self.success_result(
                data=message,
                email_id=email_id,
                source=source_table,
                destination=dest_table
            )

        except (DatabaseError, ValidationError) as e:
            return self.error_result(str(e))
