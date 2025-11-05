"""Database command - database operations (backup, export, delete, info)"""

from pathlib import Path
from typing import Any, Dict

from src.core.database import get_database
from src.utils.console import print_status
from src.utils.error_handling import DatabaseError, ValidationError
from src.utils.log_manager import async_log_call
from src.utils.ui_helpers import confirm_action

from .base import BaseCommandHandler, CommandResult


class DatabaseCommandHandler(BaseCommandHandler):
    """Handler for database operations with subcommand routing."""

    @async_log_call
    async def execute_cli(self, args, config_manager) -> bool:
        """Route to appropriate database operation (CLI mode)."""
        db_command = getattr(args, "db_command", None)

        try:
            if db_command == "backup":
                return await self._backup_cli(args, config_manager)
            elif db_command == "export":
                return await self._export_cli(args, config_manager)
            elif db_command == "delete":
                return await self._delete_cli(args, config_manager)
            elif db_command == "info":
                return await self._info_cli(args, config_manager)
            else:
                await print_status(f"Unknown database command: {db_command}")
                return False
        except (DatabaseError, ValidationError) as e:
            await print_status(f"Database command failed: {e}")
            return False

    @async_log_call
    async def execute_daemon(self, daemon, args: Dict[str, Any]) -> CommandResult:
        """Route to appropriate database operation (daemon mode)."""
        db_command = args.get("db_command")

        if db_command == "backup":
            return await self._backup_daemon(daemon, args)
        elif db_command == "export":
            return await self._export_daemon(daemon, args)
        elif db_command == "delete":
            return await self._delete_daemon(daemon, args)
        elif db_command == "info":
            return await self._info_daemon(daemon, args)
        else:
            return self.error_result(
                f"Unknown database command: {db_command}",
                db_command=db_command
            )


    # Backup operations

    async def _backup_cli(self, args, config_manager) -> None:
        """Backup the database to a file (CLI mode)."""  
        backup_path = getattr(args, "path", None)

        await print_status("Starting database backup...")

        db = get_database(config_manager)

        try:
            if backup_path:
                backup_file = await db.backup(Path(backup_path))
            else:
                backup_file = await db.backup()

            await print_status(f"Database backed up successfully to: {backup_file}")
            self.logger.info(f"Database backup completed to {backup_file}")
            return True

        except (DatabaseError, ValidationError) as e:
            self.logger.error(f"Database backup failed: {e}")
            return False

    async def _backup_daemon(self, daemon, args: Dict[str, Any]) -> CommandResult:
        """Backup the database to a file (daemon mode)."""
        backup_path = args.get("path", None)

        try:
            if backup_path:
                backup_file = await daemon.db.backup(Path(backup_path))
            else:
                backup_file = await daemon.db.backup()

            message = f"Database backed up successfully to: {backup_file}"

            return self.success_result(
                data=message,
                backup_path=str(backup_file)
            )

        except (DatabaseError, ValidationError) as e:
            return self.error_result(str(e))


    # Export operations

    async def _export_cli(self, args, config_manager) -> None:
        """Export all email tables to CSV files (CLI mode)."""
        export_path = getattr(args, "path", "./exports")
        tables = getattr(args, "tables", None)

        if not export_path:
            raise ValidationError(
                "Export path is required",
                details={"path": export_path}
            )

        await print_status("Starting email export to CSV...")

        db = get_database(config_manager)

        try:
            export_dir = Path(export_path)
            exported_files = await db.export_to_csv(export_dir, tables=tables)

            if exported_files:
                await print_status(f"Successfully exported {len(exported_files)} CSV file(s) to: {export_dir}")
                for file_path in exported_files:
                    await print_status(f"  • {file_path}")
                self.logger.info(f"Exported {len(exported_files)} CSV file(s) to {export_dir}")
            else:
                await print_status(f"No tables found to export. Export directory created at: {export_dir}")
                self.logger.info(f"No tables to export. Export directory: {export_dir}")
            
            return True

        except (DatabaseError, ValidationError) as e:
            await print_status(f"Email export failed: {e}")
            self.logger.error(f"Email export failed: {e}")
            return False

    async def _export_daemon(self, daemon, args: Dict[str, Any]) -> CommandResult:
        """Export all email tables to CSV files (daemon mode)."""
        export_path = args.get("path", "./exports")
        tables = args.get("tables", None)

        if not export_path:
            return self.error_result(
                "Export path is required",
                path=export_path
            )

        try:
            export_dir = Path(export_path)
            exported_files = await daemon.db.export_to_csv(export_dir, tables=tables)

            file_list = [str(f) for f in exported_files]
            message = f"Exported {len(exported_files)} CSV file(s) to {export_dir}"

            return self.success_result(
                data=message,
                files=file_list,
                count=len(exported_files),
                export_path=str(export_dir)
            )

        except (DatabaseError, ValidationError) as e:
            return self.error_result(str(e))


    # Delete operations

    async def _delete_cli(self, args, config_manager) -> None:
        """Delete the local database (CLI mode)."""
        
        confirm_flag = getattr(args, "confirm", False)

        if not confirm_flag:
            raise ValidationError(
                "Deletion requires --confirm flag to proceed",
                details={"confirm": confirm_flag}
            )

        db = get_database(config_manager)

        try:
            db_path = await db.get_db_path()

            if not db_path.exists():
                raise ValidationError(
                    f"Database file '{db_path}' does not exist",
                    details={"path": str(db_path)}
                )
            
            # Offer to backup before deletion
            if await confirm_action("Would you like to back up the database before deletion?"):
                try:
                    backup_file = await db.backup()
                    await print_status(f"Database backed up successfully to: {backup_file}")
                    self.logger.info(f"Database backup completed to {backup_file}")
                except DatabaseError as e:
                    await print_status(f"Failed to backup database: {e}")
                    self.logger.error(f"Failed to backup database: {e}")
                    return False
            
            # First confirmation
            if not await confirm_action(f"Are you sure you want to delete the database file at '{db_path}'? This action cannot be undone."):
                await print_status("Database deletion cancelled")
                self.logger.info("Database deletion cancelled by user")
                return False

            # Second confirmation for extra safety
            if not await confirm_action("This is your last chance to cancel. Proceed with deletion?"):
                await print_status("Database deletion cancelled")
                self.logger.info("Database deletion cancelled by user")
                return False

            await db.delete_database()
            await print_status(f"Database file '{db_path}' deleted successfully.")
            self.logger.info(f"Database deleted: {db_path}")
            return True

        except (DatabaseError, ValidationError) as e:
            await print_status(f"Database deletion failed: {e}")
            self.logger.error(f"Database deletion failed: {e}")
            return False

    async def _delete_daemon(self, daemon, args: Dict[str, Any]) -> CommandResult:
        """Delete the local database (daemon mode)."""
        confirm_flag = args.get("confirm", False)

        if not confirm_flag:
            return self.error_result(
                "Deletion requires --confirm flag to proceed",
                confirm=confirm_flag
            )

        try:
            db_path = await daemon.db.get_db_path()

            if not db_path.exists():
                return self.error_result(
                    f"Database file '{db_path}' does not exist",
                    path=str(db_path)
                )

            # Check if backup requested
            backup_flag = args.get("backup", False)
            backup_file = None

            if backup_flag:
                try:
                    backup_file = await daemon.db.backup()
                    self.logger.info(f"Database backup completed to {backup_file}")
                except DatabaseError as e:
                    return self.error_result(
                        f"Failed to backup database: {e}",
                        path=str(db_path)
                    )

            await daemon.db.delete_database()
            message = f"Database file '{db_path}' deleted successfully."

            return self.success_result(
                data=message,
                database_path=str(db_path),
                backup_path=str(backup_file) if backup_file else None
            )

        except (DatabaseError, ValidationError) as e:
            return self.error_result(str(e))


    # Info operations (placeholder)

    async def _info_cli(self, args, config_manager) -> bool:
        """Display information about the database (CLI mode)."""
        await print_status("Database info command not yet implemented")
        return True

    async def _info_daemon(self, daemon, args: Dict[str, Any]) -> CommandResult:
        """Display database information (daemon mode)."""

        # TODO: Implement database info display
        # Ideas: database size, number of emails, tables, last backup, etc.

        return self.success_result(
            data="Database info command not yet implemented",
            implemented=False
        )
