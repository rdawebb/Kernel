"""Inbox viewer - displays emails in a formatted table"""

from .table_viewer import display_email_table
from ..utils.log_manager import get_logger, log_call

logger = get_logger(__name__)

@log_call
def display_inbox(table_name, emails):
    """Display inbox emails in a formatted table with optional flagged indicator"""
    
    display_email_table(
        emails,
        title=table_name.capitalize(),
        show_source=False,
        show_flagged=(table_name == "inbox")
    )