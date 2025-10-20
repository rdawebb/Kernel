"""Shared utilities for CLI commands"""
from rich.console import Console
from ...utils.logger import get_logger

console = Console()
logger = get_logger()


def log_and_print(message: str, log_level: str = "info") -> None:
    """Log and print messages with appropriate console colors."""
    log_func = getattr(logger, log_level)
    log_func(message)
    
    if log_level == "error":
        console.print(f"[red]{message}[/]")
    elif log_level == "warning":
        console.print(f"[yellow]{message}[/]")
    elif log_level == "success":
        console.print(f"[green]{message}[/]")
    else:
        console.print(f"[green]{message}[/]")

def log_info(message: str) -> None:
    """Log and print info message."""
    log_and_print(message, "info")

def log_warning(message: str) -> None:
    """Log and print warning message."""
    log_and_print(message, "warning")

def log_error(message: str) -> None:
    """Log and print error message."""
    log_and_print(message, "error")

def log_success(message: str) -> None:
    """Log and print success message."""
    logger.info(message)
    console.print(f"[green]{message}[/]")

def print_status(message: str, color: str = "cyan") -> None:
    """Print status message without logging."""
    console.print(f"[bold {color}]{message}[/]")

def check_email_exists(table: str, email_id: int, email_name: str = "Email") -> bool:
    """Check if email exists in table."""
    from ...core import storage_api
    
    if not storage_api.email_exists(table, email_id):
        message = f"{email_name} with ID {email_id} not found in '{table}'."
        log_warning(message)
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
            log_warning(f"Email with ID {email_id} could not be retrieved from '{table}'.")
            return None
        return email_data
    except Exception as e:
        log_error(f"Failed to retrieve email: {e}")
        return None

def validate_required_args(**kwargs) -> bool:
    """Validate required arguments are provided."""
    for arg_name, arg_value in kwargs.items():
        if arg_value is None or (isinstance(arg_value, str) and not arg_value.strip()):
            log_error(f"Required argument '{arg_name}' is missing.")
            return False
    return True
