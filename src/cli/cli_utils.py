"""Shared CLI utilities and helper functions

Note: Database initialization is now handled by the daemon.
This module provides utilities for local CLI operations:
- File attachment handling
- Download listing
"""
import os
import platform
import stat
import subprocess
from pathlib import Path
from ..utils.log_manager import get_logger, async_log_call
from ..utils.attachment_utils import download_attachments
from .commands.command_utils import _get_console

logger = get_logger(__name__)

# Default attachments directory (can be overridden by config)
DEFAULT_ATTACHMENTS_DIR = Path.home() / ".kernel" / "attachments"

# Secure directory permissions: owner-only access
SECURE_DIR_PERMS = stat.S_IRWXU  # 0o700

def _is_valid_filename(filename: str) -> bool:
    """Check filename is safe (no path traversal)."""
    return os.path.sep not in filename and ".." not in filename

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
    """Download attachments for an email."""
    try:
        # Get attachments path from config or use default
        attachments_path = Path(cfg.database.attachments_path)
        
        # Ensure attachments directory exists with secure permissions
        try:
            attachments_path.mkdir(parents=True, exist_ok=True)
            # Set secure permissions: owner-only access
            os.chmod(str(attachments_path), SECURE_DIR_PERMS)
            logger.info(f"Attachments directory ensured at: {attachments_path}")
        except OSError as e:
            logger.error(f"Failed to create attachments directory: {e}")
            _get_console().print(f"[red]Failed to create attachments directory: {e}[/]")
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

        downloaded_files = download_attachments(
            cfg, 
            email_id, 
            attachment_index=attachment_index, 
            download_path=str(attachments_path)
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
    """List downloaded attachments with file sizes."""
    try:
        # Get attachments path from config or use default
        attachments_path = Path(cfg.database.attachments_path)
        
        if not attachments_path.exists():
            logger.warning("Attachments folder does not exist.")
            _get_console().print("[yellow]Attachments folder does not exist.[/]")
            return
            
        downloaded_files = list(attachments_path.iterdir())
        if not downloaded_files:
            logger.info("No downloaded attachments found in attachments folder.")
            _get_console().print("[yellow]No downloaded attachments found in attachments folder.[/]")
            return

        logger.info(f"Found {len(downloaded_files)} downloaded attachment(s)")
        _get_console().print(f"[green]Found {len(downloaded_files)} downloaded attachment(s):[/]")
        
        for file_path in downloaded_files:
            try:
                file_size = file_path.stat().st_size
                size_kb = file_size / 1024
                if size_kb < 1:
                    size_str = f"{file_size}B"
                elif size_kb < 1024:
                    size_str = f"{size_kb:.1f}KB"
                else:
                    size_str = f"{size_kb/1024:.1f}MB"
                _get_console().print(f"  [cyan]{file_path.name}[/] [dim]({size_str})[/]")
            except OSError:
                logger.warning(f"Failed to get size for file: {file_path.name}")
                _get_console().print(f"  [cyan]{file_path.name}[/] [dim](size unknown)[/]")

    except Exception as e:
        logger.error(f"Failed to list downloaded attachments: {e}")
        _get_console().print(f"[red]Failed to list downloaded attachments: {e}[/]")

@async_log_call
async def handle_open_attachment(args, cfg) -> None:
    """Open downloaded attachment with default application."""
    try:
        # Get attachments path from config or use default
        attachments_path = Path(cfg.database.attachments_path)
        
        if not attachments_path.exists():
            logger.error("Attachments folder does not exist.")
            _get_console().print("[red]Attachments folder does not exist.[/]")
            return
        
        # Validate filename to prevent path traversal attacks
        if not _is_valid_filename(args.filename):
            logger.error("Invalid filename provided for opening attachment.")
            _get_console().print("[red]Invalid filename. Please use only the filename from downloads list.[/]")
            return

        file_path = attachments_path / args.filename
        if not file_path.exists():
            logger.error(f"File '{args.filename}' not found in attachments folder.")
            _get_console().print(f"[red]File '{args.filename}' not found in attachments folder.[/]")
            return

        logger.info(f"Opening attachment '{args.filename}'...")
        _get_console().print(f"[bold cyan]Opening attachment '{args.filename}'...[/]")
        
        try:
            if platform.system() == "Darwin":
                subprocess.run(["open", str(file_path)], check=True)
            elif platform.system() == "Windows":
                os.startfile(str(file_path))
            else:
                subprocess.run(["xdg-open", str(file_path)], check=True)

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to open attachment: {e}")
            _get_console().print(f"[red]Failed to open attachment: {e}[/]")
            return
        
        except FileNotFoundError:
            logger.error(f"No application found to open the file '{args.filename}'.")
            _get_console().print(f"[red]No application found to open the file '{args.filename}'.[/]")
            return

    except Exception as e:
        logger.error(f"Failed to open attachment: {e}")
        _get_console().print(f"[red]Failed to open attachment: {e}[/]")
