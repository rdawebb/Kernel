"""Export command - export emails to CSV"""
from rich.console import Console
from ...core import storage_api
from ...utils.log_manager import get_logger, async_log_call, log_event
from .command_utils import print_status, print_success, print_error

console = Console()
logger = get_logger(__name__)


@async_log_call
async def handle_export(args, cfg_manager):
    """Export all email tables to CSV files"""
    try:
        print_status("Starting email export to CSV...")
        export_dir = args.path or "./exports"  # Default to exports directory
        exported_files = storage_api.export_db_to_csv(export_dir)

        if exported_files:
            message = f"Successfully exported {len(exported_files)} CSV file(s) to: {export_dir}"
            logger.info(message)
            print_success(message)
            for file_path in exported_files:
                console.print(f"  • {file_path}")
            log_event("export_completed", "Emails exported to CSV", count=len(exported_files), path=export_dir)
        else:
            logger.info(f"No tables found to export. Export directory created at: {export_dir}")
            console.print(f"[yellow]No tables found to export. Export directory created at: {export_dir}[/]")
    
    except Exception as e:
        logger.error(f"Failed to export emails: {e}")
        print_error(f"Failed to export emails: {e}")
