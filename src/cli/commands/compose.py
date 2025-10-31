"""Compose command - create and send new emails"""
from typing import Any, Dict

from ...ui.composer import Composer
from ...utils.log_manager import async_log_call, get_logger, log_event
from .command_utils import print_error, print_status

logger = get_logger(__name__)


@async_log_call
async def handle_compose(args, cfg_manager):
    """Compose and send a new email"""
    try:
        composer = Composer()
        result = composer.compose_email()
        if not result:
            logger.info("Email composition cancelled or failed.")
            print_status("Email composition cancelled or failed.", color="yellow")
        else:
            log_event("email_composed", "Email composed and sent successfully")

    except Exception as e:
        logger.error(f"Failed to compose/send email: {e}")
        print_error(f"Failed to compose/send email: {e}")


async def handle_compose_daemon(daemon, args: Dict[str, Any]) -> Dict[str, Any]:
    """Compose command - daemon compatible wrapper."""
    try:
        return {
            'success': True,
            'data': {
                'to': args.get('to', ''),
                'subject': args.get('subject', ''),
                'body': args.get('body', ''),
            },
            'error': None,
            'metadata': {'mode': 'compose'}
        }
    except Exception as e:
        logger.exception("Error in handle_compose_daemon")
        return {
            'success': False,
            'data': None,
            'error': str(e),
            'metadata': {}
        }
