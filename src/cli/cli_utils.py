"""Shared CLI utilities and helper functions

Note: Database initialization is now handled by the daemon.
This module provides utilities for local CLI operations using AttachmentManager.
All attachment handling is now centralized in src/core/attachments.py
"""
from ..core import storage_api
from ..core.attachments import AttachmentManager
from ..utils.log_manager import async_log_call, get_logger
from .commands.command_utils import _get_console

logger = get_logger(__name__)


def _print_and_log_downloaded_files(downloaded_files, email_id: int) -> None:
    """Log and display downloaded files."""
    for file_path in downloaded_files:
        logger.info(f"Downloaded attachment: {file_path}")
        _get_console().print(f"[green]Downloaded: {file_path}[/]")
    count = len(downloaded_files)
    message = f"Successfully downloaded {count} attachment(s) for email ID {email_id}."
    logger.info(message)
    _get_console().print(f"[green]{message}[/]")


@async_log_call
async def handle_download_action(cfg, email_id: int, args) -> None:
    """Download attachments for an email using AttachmentManager."""
    try:
        # Initialize attachment manager with config
        attachment_manager = AttachmentManager(cfg)
        
        # Get email data from storage
        email_data = storage_api.get_email("inbox", email_id)
        if not email_data:
            logger.error(f"Email ID {email_id} not found.")
            _get_console().print(f"[red]Email ID {email_id} not found.[/]")
            return
        
        # Determine attachment index: None (all), specific index, or 0 (first)
        has_all = hasattr(args, 'all')
        has_index = hasattr(args, 'index')
        if has_all and args.all:
            attachment_index = None
        elif has_index and args.index is not None:
            attachment_index = args.index
        else:
            attachment_index = 0

        # Download using AttachmentManager
        downloaded_files = attachment_manager.download_from_email_data(
            email_data,
            attachment_index=attachment_index
        )
        
        if downloaded_files:
            _print_and_log_downloaded_files(downloaded_files, email_id)
        else:
            logger.warning(f"No attachments found for email ID {email_id}.")
            _get_console().print(f"[yellow]No attachments found for email ID {email_id}.[/]")
    
    except Exception as e:
        logger.error(f"Failed to download attachments: {e}")
        _get_console().print(f"[red]Failed to download attachments: {e}[/]")


@async_log_call
async def handle_downloads_list(args, cfg) -> None:
    """List downloaded attachments with file sizes using AttachmentManager."""
    try:
        # Initialize attachment manager with config
        attachment_manager = AttachmentManager(cfg)
        
        # Get list of downloaded attachments
        downloaded_files = attachment_manager.list_downloaded_attachments()
        
        if not downloaded_files:
            logger.info("No downloaded attachments found.")
            _get_console().print("[yellow]No downloaded attachments found.[/]")
            return

        logger.info(f"Found {len(downloaded_files)} downloaded attachment(s)")
        _get_console().print(f"[green]Found {len(downloaded_files)} downloaded attachment(s):[/]")
        
        for file_path, file_size in downloaded_files:
            size_str = attachment_manager.format_file_size(file_size)
            _get_console().print(f"  [cyan]{file_path.name}[/] [dim]({size_str})[/]")

    except Exception as e:
        logger.error(f"Failed to list downloaded attachments: {e}")
        _get_console().print(f"[red]Failed to list downloaded attachments: {e}[/]")


@async_log_call
async def handle_open_attachment(args, cfg) -> None:
    """Open downloaded attachment with default application using AttachmentManager."""
    try:
        # Initialize attachment manager with config
        attachment_manager = AttachmentManager(cfg)
        
        # Open the attachment (validation handled by AttachmentManager)
        success = attachment_manager.open_attachment(args.filename)
        
        if success:
            _get_console().print(f"[bold cyan]Opened attachment '{args.filename}'[/]")
    
    except Exception as e:
        logger.error(f"Failed to open attachment: {e}")
        _get_console().print(f"[red]Failed to open attachment: {e}[/]")
