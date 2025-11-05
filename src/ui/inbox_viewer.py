"""Inbox viewer - displays emails in a formatted table"""

from typing import Any, Dict, List, Optional

from rich.console import Console

from src.utils.console import get_console
from src.utils.log_manager import async_log_call, get_logger
from .table_viewer import display_email_table

logger = get_logger(__name__)


@async_log_call
async def display_inbox(emails: List[Dict[str, Any]], table_name: str = "inbox",
                        console: Optional[Console] = None) -> None:
    """Display inbox emails in a formatted table"""
    output_console = console or get_console()

    show_flagged = (table_name.lower() == "inbox")

    await display_email_table(
        emails=emails,
        title=table_name.title(),
        show_source=False,
        show_flagged=show_flagged,
        console=output_console
    )

    logger.debug(f"Displayed {table_name} with {len(emails)} emails.")
