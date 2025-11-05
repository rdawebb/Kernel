"""Search command - search emails by keyword"""

from typing import Any, Dict

from src.core.database import get_database
from src.ui import search_viewer
from src.utils.console import print_status
from src.utils.error_handling import DatabaseError, ValidationError
from src.utils.log_manager import async_log_call

from .base import BaseCommandHandler, CommandResult


class SearchCommandHandler(BaseCommandHandler):
    """Handler for the 'search' command to search emails by keyword."""

    @async_log_call
    async def execute_cli(self, args, config_manager) -> None:
        """Search emails by keyword in specified table or all tables (CLI mode)."""
        
        keyword = getattr(args, "keyword", None)
        search_all = getattr(args, "all", False)
        table = getattr(args, "folder", "inbox")
        limit = getattr(args, "limit", 50)
        
        self.validate_args({"keyword": keyword}, "keyword")
        
        if not search_all:
            self.validate_table(table)

        db = get_database(config_manager)

        try:
            if search_all:
                await print_status(f"Searching all folders for '{keyword}'...")
                results = await db.search_all_tables(keyword, limit=limit)
                await search_viewer.display_search_results(results, "all emails", keyword)
                self.logger.info(f"Searched all folders for '{keyword}', found {len(results)} results")
            else:
                await print_status(f"Searching folder '{table}' for '{keyword}'...")
                results = await db.search(table, keyword, limit=limit)
                await search_viewer.display_search_results(results, table, keyword)
                self.logger.info(f"Searched folder '{table}' for '{keyword}', found {len(results)} results")
            
            return True

        except (DatabaseError, ValidationError) as e:
            await print_status(f"[red]Error: {e}[/]")
            self.logger.error(f"Error during search: {e}")
            return False

    @async_log_call
    async def execute_daemon(self, daemon, args: Dict[str, Any]) -> CommandResult:
        """Search emails by keyword in specified table or all tables (daemon mode)."""

        keyword = args.get("keyword")
        search_all = args.get("all", False)
        table = args.get("folder", "inbox")
        limit = args.get("limit", 50)

        self.validate_args({"keyword": keyword}, "keyword")
        
        if not search_all:
            self.validate_table(table)

        try:
            if search_all:
                results = await daemon.db.search_all_tables(keyword, limit=limit)
                title = "all emails"
            else:
                results = await daemon.db.search(table, keyword, limit=limit)
                title = table

            output = self.render_for_daemon(
                await search_viewer.display_search_results,
                title,
                results,
                keyword
            )

            return self.success_result(
                data=output,
                count=len(results),
                keyword=keyword,
                search_scope="all" if search_all else table
            )

        except (DatabaseError, ValidationError) as e:
            return self.error_result(str(e))
