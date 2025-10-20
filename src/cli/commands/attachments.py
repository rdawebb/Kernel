"""Attachments commands - list and manage email attachments"""
from rich.console import Console
from ...core import storage_api
from ...ui import inbox_viewer
from ...utils.logger import get_logger
from ...utils.attachment_utils import get_attachment_list
from .command_utils import log_error, log_success, print_status

console = Console()
logger = get_logger()


async def handle_attachments(args, cfg):
    """List emails with attachments"""
    print_status("Loading emails with attachments...")
    
    try:
        emails = storage_api.search_emails_with_attachments("inbox", limit=args.limit)
        if not emails:
            console.print("[yellow]No emails with attachments found.[/]")
            return
        inbox_viewer.display_inbox("inbox", emails)
        log_success(f"Found {len(emails)} email(s) with attachments.")

    except Exception as e:
        log_error(f"Failed to retrieve emails with attachments: {e}")

async def handle_attachments_list(args, cfg):
    """List attachment filenames for a specific email"""
    if args.id is None:
        log_error("Email ID is required to list attachments.")
        return
    
    print_status(f"Loading attachment list for email {args.id}...")
    try:
        attachment_list = get_attachment_list(cfg, args.id)
        
        if not attachment_list:
            console.print(f"[yellow]No attachments found for email ID {args.id}.[/]")
            return
        
        log_success(f"Found {len(attachment_list)} attachment(s):")
        for i, filename in enumerate(attachment_list):
            console.print(f"  [cyan]{i}[/]: {filename}")
            
    except Exception as e:
        log_error(f"Failed to get attachment list: {e}")
