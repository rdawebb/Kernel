"""Shared CLI utilities and helper functions"""
import os
import platform
import subprocess
from pathlib import Path

from rich.console import Console
from ..core import storage_api
from ..utils.logger import get_logger
from ..utils.attachment_utils import download_attachments

console = Console()
logger = get_logger()

ATTACHMENTS_DIR = Path("./attachments")


def initialize_database():
    """Initialize the database (called at startup)."""
    try:
        storage_api.initialize_db()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        console.print(f"[red]Failed to initialize database: {e}[/]")
        exit(1)

def _is_valid_filename(filename: str) -> bool:
    """Check filename is safe (no path traversal)."""
    return os.path.sep not in filename and ".." not in filename

def _print_and_log_downloaded_files(downloaded_files, email_id: int) -> None:
    """Log and display downloaded files."""
    for file_path in downloaded_files:
        logger.info(f"Downloaded: {file_path}")
        console.print(f"[green]Downloaded: {file_path}[/]")
    count = len(downloaded_files)
    message = f"Successfully downloaded {count} attachment(s) for email ID {email_id}."
    logger.info(message)
    console.print(f"[green]{message}[/]")

def handle_download_action(cfg, email_id: int, args) -> None:
    """Download attachments for an email."""
    try:
        # Determine attachment index: None (all), specific index, or 0 (first)
        if hasattr(args, 'all') and args.all:
            attachment_index = None
        elif hasattr(args, 'index') and args.index is not None:
            attachment_index = args.index
        else:
            attachment_index = 0

        downloaded_files = download_attachments(
            cfg, 
            email_id, 
            attachment_index=attachment_index, 
            download_path=str(ATTACHMENTS_DIR)
        )
        
        if downloaded_files:
            _print_and_log_downloaded_files(downloaded_files, email_id)
        else:
            logger.warning(f"No attachments found for email ID {email_id}.")
            console.print(f"[yellow]No attachments found for email ID {email_id}.[/]")
    
    except Exception as e:
        logger.error(f"Failed to download attachments: {e}")
        console.print(f"[red]Failed to download attachments: {e}[/]")

async def handle_downloads_list(args, cfg) -> None:
    """List downloaded attachments with file sizes."""
    try:
        if not ATTACHMENTS_DIR.exists():
            logger.error("Attachments folder does not exist.")
            console.print("[yellow]Attachments folder does not exist.[/]")
            return
            
        downloaded_files = list(ATTACHMENTS_DIR.iterdir())
        if not downloaded_files:
            logger.info("No downloaded attachments found in attachments folder.")
            console.print("[yellow]No downloaded attachments found in attachments folder.[/]")
            return

        logger.info(f"Found {len(downloaded_files)} downloaded attachment(s)")
        console.print(f"[green]Found {len(downloaded_files)} downloaded attachment(s):[/]")
        
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
                console.print(f"  [cyan]{file_path.name}[/] [dim]({size_str})[/]")
            except OSError:
                logger.warning(f"Failed to get size for file: {file_path.name}")
                console.print(f"  [cyan]{file_path.name}[/] [dim](size unknown)[/]")

    except Exception as e:
        logger.error(f"Failed to list downloaded attachments: {e}")
        console.print(f"[red]Failed to list downloaded attachments: {e}[/]")

async def handle_open_attachment(args, cfg) -> None:
    """Open downloaded attachment with default application."""
    try:
        if not ATTACHMENTS_DIR.exists():
            logger.error("Attachments folder does not exist.")
            console.print("[red]Attachments folder does not exist.[/]")
            return
        
        # Validate filename to prevent path traversal attacks
        if not _is_valid_filename(args.filename):
            logger.error("Invalid filename provided for opening attachment.")
            console.print("[red]Invalid filename. Please use only the filename from downloads list.[/]")
            return

        file_path = ATTACHMENTS_DIR / args.filename
        if not file_path.exists():
            logger.error(f"File '{args.filename}' not found in attachments folder.")
            console.print(f"[red]File '{args.filename}' not found in attachments folder.[/]")
            return

        logger.info(f"Opening attachment '{args.filename}'...")
        console.print(f"[bold cyan]Opening attachment '{args.filename}'...[/]")
        
        try:
            if platform.system() == "Darwin":
                subprocess.run(["open", str(file_path)], check=True)
            elif platform.system() == "Windows":
                os.startfile(str(file_path))
            else:
                subprocess.run(["xdg-open", str(file_path)], check=True)

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to open attachment: {e}")
            console.print(f"[red]Failed to open attachment: {e}[/]")
            return
        
        except FileNotFoundError:
            logger.error(f"No application found to open the file '{args.filename}'.")
            console.print(f"[red]No application found to open the file '{args.filename}'.[/]")
            return

    except Exception as e:
        logger.error(f"Failed to open attachment: {e}")
        console.print(f"[red]Failed to open attachment: {e}[/]")
