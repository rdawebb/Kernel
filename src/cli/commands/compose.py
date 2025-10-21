"""Compose command - compose and send emails"""
from rich.console import Console
from ...ui import composer
from ...utils.log_manager import get_logger, async_log_call, log_event

console = Console()
logger = get_logger(__name__)


@async_log_call
async def handle_compose(args, cfg_manager):
    """Compose and send a new email"""
    try:
        result = composer.compose_email()
        if not result:
            logger.info("Email composition cancelled or failed.")
            console.print("[yellow]Email composition cancelled or failed.[/]")
        else:
            log_event("email_composed", "Email composed and sent successfully")

    except Exception as e:
        logger.error(f"Failed to compose/send email: {e}")
        console.print(f"[red]Failed to compose/send email: {e}[/]")
