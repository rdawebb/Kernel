"""Download command - download email attachments"""
from rich.console import Console
from ...utils.log_manager import get_logger, async_log_call
from ..cli_utils import handle_download_action
from .command_utils import print_error, print_warning, print_status, get_email_with_validation

console = Console()
logger = get_logger(__name__)


@async_log_call
async def handle_download(args, cfg_manager):
    """Download email attachments"""
    if args.id is None:
        logger.error("Email ID is required for downloading attachments.")
        print_error("Email ID is required for downloading attachments.")
        return
    
    if not args.all and args.index is None:
        logger.error("Please specify either --all to download all attachments or --index to download a specific attachment.")
        print_error("Please specify either --all to download all attachments or --index to download a specific attachment.")
        return
    
    print_status(f"Downloading attachments for email {args.id} from {args.table}...")
    
    email_data = get_email_with_validation(args.table, args.id)
    if not email_data:
        return

    try:
        attachments_raw = email_data.get('attachments', '')
        if not attachments_raw or not attachments_raw.strip():
            logger.warning("No attachments found in database, checking server...")
            print_warning("No attachments found in database, checking server...")
            handle_download_action(cfg_manager, args.id, args)
            return

        attachments = [att.strip() for att in attachments_raw.split(',') if att.strip()]
        if not attachments:
            logger.warning(f"No valid attachments to download for email ID {args.id}.")
            print_warning(f"No valid attachments to download for email ID {args.id}.")
            return

        if args.index is not None and (args.index >= len(attachments) or args.index < 0):
            logger.error(f"Invalid attachment index {args.index}. Available attachments: 0-{len(attachments)-1}")
            print_error(f"Invalid attachment index {args.index}. Available attachments: 0-{len(attachments)-1}")
            return

        handle_download_action(cfg_manager, args.id, args)

    except Exception as e:
        logger.error(f"Failed to download attachments: {e}")
        print_error(f"Failed to download attachments: {e}")
