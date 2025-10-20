"""Search results viewer - displays search results in a formatted table"""

from src.ui.table_viewer import display_email_table


def display_search_results(table_name, emails, keyword):
    """Display search results in a formatted table with dynamic columns based on source
    
    Args:
        table_name: Name of the table being searched (e.g., "inbox", "all emails")
        emails: List of email dictionaries matching the search
        keyword: Search keyword for display and empty state message
    """
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
        title=f"Search Results for '{keyword}' in {table_name}",
        show_source=show_source,
        show_flagged=show_flagged,
        keyword=keyword
    )