"""Compose command - compose and send emails"""
from rich.console import Console
from ...ui import composer
from ...utils.logger import get_logger
from .command_utils import log_error

console = Console()
logger = get_logger()


async def handle_compose(args, cfg):
    """Compose and send a new email"""
    try:
        result = composer.compose_email()
        if not result:
            logger.info("Email composition cancelled or failed.")
            console.print("[yellow]Email composition cancelled or failed.[/]")

    except Exception as e:
        log_error(f"Failed to compose/send email: {e}")
