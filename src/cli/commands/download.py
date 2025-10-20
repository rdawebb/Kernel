"""Download command - download email attachments"""
from rich.console import Console
from ...utils.logger import get_logger
from ..cli_utils import handle_download_action
from .command_utils import log_error, log_warning, print_status, get_email_with_validation

console = Console()
logger = get_logger()


async def handle_download(args, cfg):
    """Download email attachments"""
    if args.id is None:
        log_error("Email ID is required for downloading attachments.")
        return
    
    if not args.all and args.index is None:
        log_error("Please specify either --all to download all attachments or --index to download a specific attachment.")
        return
    
    print_status(f"Downloading attachments for email {args.id} from {args.table}...")
    
    email_data = get_email_with_validation(args.table, args.id)
    if not email_data:
        return

    try:
        attachments_raw = email_data.get('attachments', '')
        if not attachments_raw or not attachments_raw.strip():
            log_warning("No attachments found in database, checking server...")
            handle_download_action(cfg, args.id, args)
            return

        attachments = [att.strip() for att in attachments_raw.split(',') if att.strip()]
        if not attachments:
            log_warning(f"No valid attachments to download for email ID {args.id}.")
            return

        if args.index is not None and (args.index >= len(attachments) or args.index < 0):
            log_error(f"Invalid attachment index {args.index}. Available attachments: 0-{len(attachments)-1}")
            return

        handle_download_action(cfg, args.id, args)

    except Exception as e:
        log_error(f"Failed to download attachments: {e}")
