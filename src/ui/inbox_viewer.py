"""Inbox viewer - displays emails in a formatted table"""

from src.ui.table_viewer import display_email_table


def display_inbox(table_name, emails):
    """Display inbox emails in a formatted table with optional flagged indicator
    
    Args:
        table_name: Name of the table/view (e.g., "inbox", "drafts")
        emails: List of email dictionaries to display
    """
    display_email_table(
        emails,
        title=table_name.capitalize(),
        show_source=False,
        show_flagged=(table_name == "inbox")
    )