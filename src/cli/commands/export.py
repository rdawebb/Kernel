"""Export command - export emails to CSV"""
from rich.console import Console
from ...core import storage_api
from ...utils.logger import get_logger
from .command_utils import log_error, log_success, print_status

console = Console()
logger = get_logger()


async def handle_export(args, cfg):
    """Export all email tables to CSV files"""
    try:
        print_status("Starting email export to CSV...")
        export_dir = args.path or "./exports"  # Default to exports directory
        exported_files = storage_api.export_db_to_csv(export_dir)

        if exported_files:
            log_success(f"Successfully exported {len(exported_files)} CSV file(s) to: {export_dir}")
            for file_path in exported_files:
                console.print(f"  • {file_path}")
        else:
            console.print(f"[yellow]No tables found to export. Export directory created at: {export_dir}[/]")
    
    except Exception as e:
        log_error(f"Failed to export emails: {e}")
