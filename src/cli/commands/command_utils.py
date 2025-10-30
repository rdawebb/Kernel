"""Shared utilities for CLI commands"""
import re
from src.utils.log_manager import get_logger

logger = get_logger(__name__)

# Lazy load console to avoid blocking on import
_console = None


def _get_console():
    """Get or create the console instance."""
    global _console
    if _console is None:
        from rich.console import Console
        _console = Console()
    return _console


def clean_ansi_output(text: str) -> str:
    """Remove problematic ANSI codes while preserving color codes.
    
    Removes escape sequences that aren't color/style codes.
    Keeps CSI codes ending with 'm' (SGR - Select Graphic Rendition).
    """
    # Remove OSC sequences (Operating System Command) - these are timing/metadata
    text = re.sub(r'\x1b\][^\x07]*\x07', '', text)  # OSC with BEL
    text = re.sub(r'\x1b\][^\x1b]*\x1b\\', '', text)  # OSC with ST
    
    # Remove other complex escape sequences
    text = re.sub(r'\x1b[PX^_].*?\x1b\\', '', text)  # DCS/SOS/APC/PM
    
    # Remove CSI sequences that aren't SGR color codes (end with 'm')
    # Match \x1b[ followed by digits/semicolons, ending with a letter that's NOT 'm'
    text = re.sub(r'\x1b\[[0-9;]*[a-ln-zA-LN-Z]', '', text)  # Remove non-SGR CSI codes
    
    # Remove bell characters
    text = re.sub(r'\x07', '', text)
    
    return text


def print_status(message: str, color: str = "cyan") -> None:
    """Print status message to console."""
    _get_console().print(f"[bold {color}]{message}[/]")


def print_success(message: str) -> None:
    """Print success message to console."""
    _get_console().print(f"[green]{message}[/]")


def print_error(message: str) -> None:
    """Print error message to console."""
    _get_console().print(f"[red]{message}[/]")


def print_warning(message: str) -> None:
    """Print warning message to console."""
    _get_console().print(f"[yellow]{message}[/]")


def check_email_exists(table: str, email_id: int, email_name: str = "Email") -> bool:
    """Check if email exists in table."""
    from ...core import storage_api
    
    if not storage_api.email_exists(table, email_id):
        message = f"{email_name} with ID {email_id} not found in '{table}'."
        logger.warning(message)
        print_warning(message)
        return False
    return True


def get_email_with_validation(table: str, email_id: int) -> dict:
    """Retrieve email from table with validation."""
    from ...core import storage_api
    
    if not check_email_exists(table, email_id):
        return None
    
    try:
        email_data = storage_api.get_email_from_table(table, email_id)
        if not email_data:
            message = f"Email with ID {email_id} could not be retrieved from '{table}'."
            logger.warning(message)
            print_warning(message)
            return None
        return email_data
    except Exception as e:
        logger.error(f"Failed to retrieve email: {e}")
        print_error(f"Failed to retrieve email: {e}")
        return None


def validate_required_args(**kwargs) -> bool:
    """Validate required arguments are provided."""
    for arg_name, arg_value in kwargs.items():
        if arg_value is None or (isinstance(arg_value, str) and not arg_value.strip()):
            message = f"Required argument '{arg_name}' is missing."
            logger.error(message)
            print_error(message)
            return False
    return True
