"""Search results viewer - displays search results in a formatted table"""

from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console

from src.utils.console import get_console
from src.utils.log_manager import async_log_call, get_logger
from .table_viewer import display_email_table

logger = get_logger(__name__)


def _determine_display_options(table_name: str, 
                               emails: List[Dict[str, Any]]) -> Tuple[bool, bool]:
    """Determine which optional columns to show based on context"""
    show_source = (table_name.lower() == "all emails")

    if show_source:
        show_flagged = any(email.get("flagged") is not None for email in emails)
    else:
        show_flagged = (table_name.lower() == "inbox")

    return show_source, show_flagged

@async_log_call
async def display_search_results(emails: List[Dict[str, Any]], table_name: str, 
                                 keyword: str, console: Optional[Console] = None) -> None:
    """Display search results in a formatted table"""
    output_console = console or get_console()

    show_source, show_flagged = _determine_display_options(table_name, emails)

    title = f"Search Results for '{keyword}' in {table_name.title()}"

    await display_email_table(
        emails=emails,
        title=title,
        show_source=show_source,
        show_flagged=show_flagged,
        keyword=keyword,
        console=output_console
    )

    logger.debug(f"Displayed search results: {len(emails)} emails found for keyword '{keyword}' in {table_name}.")
    