"""Search results viewer - displays search results in a formatted table"""

from ..utils.log_manager import get_logger, log_call
from .table_viewer import display_email_table

logger = get_logger(__name__)

@log_call
def display_search_results(table_name, emails, keyword, console_obj=None):
    """Display search results in a formatted table with dynamic columns based on source"""
    show_source = (table_name == "all emails")
    
    # Determine if flagged column should be shown
    show_flagged = False
    if show_source:
        # Show flagged if any email in results has flagged status
        show_flagged = any(email.get("flagged") is not None for email in emails)
    else:
        # Show flagged for inbox search
        show_flagged = (table_name == "inbox")
    
    display_email_table(
        emails,
        title=f"Search Results for '{keyword}' in {table_name.capitalize()}",
        show_source=show_source,
        show_flagged=show_flagged,
        keyword=keyword,
        console_obj=console_obj
    )