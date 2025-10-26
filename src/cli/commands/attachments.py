"""Attachments commands - list and manage email attachments"""
from typing import Dict, Any
from io import StringIO
from rich.console import Console
from ...core import storage_api
from ...ui import inbox_viewer
from ...utils.log_manager import get_logger, async_log_call
from ...utils.attachment_utils import get_attachment_list
from .command_utils import print_error, print_success, print_status, clean_ansi_output, _get_console

logger = get_logger(__name__)


@async_log_call
async def handle_attachments(args, cfg_manager):
    """List emails with attachments"""
    print_status("Loading emails with attachments...")
    
    try:
        emails = storage_api.search_emails_with_attachments("inbox", limit=args.limit)
        if not emails:
            logger.warning("No emails with attachments found.")
            print_status("No emails with attachments found.", color="yellow")
            return
        inbox_viewer.display_inbox("Emails with Attachments", emails)
        message = f"Found {len(emails)} email(s) with attachments."
        logger.info(message)
        print_success(message)

    except Exception as e:
        logger.error(f"Failed to retrieve emails with attachments: {e}")
        print_error(f"Failed to retrieve emails with attachments: {e}")

@async_log_call
async def handle_attachments_list(args, cfg_manager):
    """List attachment filenames for a specific email"""
    if args.id is None:
        logger.error("Email ID is required to list attachments.")
        print_error("Email ID is required to list attachments.")
        return
    
    print_status(f"Loading attachment list for email {args.id}...")
    try:
        attachment_list = get_attachment_list(cfg_manager, args.id)
        
        if not attachment_list:
            logger.warning(f"No attachments found for email ID {args.id}.")
            print_status(f"No attachments found for email ID {args.id}.", color="yellow")
            return
        
        message = f"Found {len(attachment_list)} attachment(s):"
        logger.info(message)
        print_success(message)
        for i, filename in enumerate(attachment_list):
            _get_console().print(f"  [cyan]{i}[/]: {filename}")
            
    except Exception as e:
        logger.error(f"Failed to get attachment list: {e}")
        print_error(f"Failed to get attachment list: {e}")


async def handle_attachments_list_daemon(daemon, args: Dict[str, Any]) -> Dict[str, Any]:
    """Attachments list command - daemon compatible wrapper."""
    try:
        table = args.get('table', 'inbox')
        email_id = args.get('id')
        
        attachments = storage_api.get_email_attachments(table, email_id)
        
        buffer = StringIO()
        buffer_console = Console(
            file=buffer,
            force_terminal=True,  # Enable terminal mode for proper Rich rendering
            width=120,
            legacy_windows=False
        )
        
        if attachments:
            for i, filename in enumerate(attachments):
                buffer_console.print(f"  [cyan]{i}[/]: {filename}")
        else:
            buffer_console.print(f"[yellow]No attachments found for email ID {email_id}.[/]")
        
        # Get the rendered output with ANSI codes
        output = buffer.getvalue()
        output = clean_ansi_output(output)
        
        return {
            'success': True,
            'data': output,
            'error': None,
            'metadata': {'count': len(attachments)}
        }
    except Exception as e:
        logger.exception("Error in handle_attachments_list_daemon")
        return {
            'success': False,
            'data': None,
            'error': str(e),
            'metadata': {}
        }
