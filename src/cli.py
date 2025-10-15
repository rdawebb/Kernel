"""Command-line interface for Kernel - handles argument parsing and command execution"""

## TODO: refactor to remove redundant code, improve error handling and user feedback
## TODO: improve help messages and validation
## TODO: move some logic to separate modules to reduce size of main CLI file

import argparse
import os
import platform
import subprocess
from datetime import datetime
from rich.console import Console
from core import imap_client, storage_api
from ui import inbox_viewer, email_viewer, search_viewer, composer
from utils import config, logger
from utils.ui_helpers import confirm_action

console = Console()
logger = logger.get_logger()

def initialize_database():
    """Initialize the database - called from main() to avoid issues during imports"""
    try:
        storage_api.initialize_db()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        console.print(f"[red]Failed to initialize database: {e}[/]")
        exit(1)

def handle_download_action(cfg, email_id, args):
    """Handle attachment download logic"""
    try:
        if args.all:
            downloaded_files = imap_client.download_all_attachments(cfg, email_id, "./attachments")
            
            if downloaded_files:
                for file_path in downloaded_files:
                    logger.info(f"Downloaded: {file_path}")
                    console.print(f"[green]Downloaded: {file_path}[/]")
                logger.info(f"Successfully downloaded {len(downloaded_files)} attachment(s) for email ID {email_id}.")
                console.print(f"[green]Successfully downloaded {len(downloaded_files)} attachment(s) for email ID {email_id}.[/]")
            
            else:
                logger.warning(f"No attachments found for email ID {email_id}.")
                console.print(f"[yellow]No attachments found for email ID {email_id}.[/]")
        
        elif args.index is not None:
            file_path = imap_client.download_attachment_by_index(cfg, email_id, args.index, "./attachments")
            logger.info(f"Downloaded: {file_path}")
            console.print(f"[green]Downloaded: {file_path}[/]")
            logger.info(f"Successfully downloaded 1 attachment for email ID {email_id}.")
            console.print(f"[green]Successfully downloaded 1 attachment for email ID {email_id}.[/]")
        
        else:
            file_path = imap_client.download_attachment_by_index(cfg, email_id, 0, "./attachments")
            logger.info(f"Downloaded: {file_path}")
            console.print(f"[green]Downloaded: {file_path}[/]")
            logger.info(f"Successfully downloaded 1 attachment for email ID {email_id}.")
            console.print(f"[green]Successfully downloaded 1 attachment for email ID {email_id}.[/]")
    
    except Exception as e:
        logger.error(f"Failed to download attachments: {e}")
        console.print(f"[red]Failed to download attachments: {e}[/]")
        return

def setup_argument_parser():
    """Configure and return the argument parser with all subcommands"""
    parser = argparse.ArgumentParser(
        prog="tui_mail",
        description="Minimal Email Client — fetch, view, send, and manage emails."
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    commands_config = [
        ("list", "List recent emails", [
            ("--limit", {"type": int, "default": 10, "help": "Number of emails to display"}),
        ]),
        ("refresh", "Fetch new emails", [
            ("--limit", {"type": int, "default": 10, "help": "Number of emails to display"}),
            ("--all", {"action": "store_true", "help": "Fetch all emails from server"})
        ]),
        ("view", "View a specific email by ID", [
            ("id", {"help": "Email ID (from list command)"}),
            ("--table", {"default": "inbox", "choices": ["inbox", "sent_emails", "drafts", "deleted_emails"], "help": "Table to search in (default: inbox)"})
        ]),
        ("search", "Search emails by keyword", [
            ("table_name", {"nargs": "?", "choices": ["inbox", "sent", "drafts", "deleted"], "help": "Table to search (not used with --all)"}),
            ("--all", {"action": "store_true", "help": "Search all emails"}),
            ("keyword", {"help": "Keyword to search in emails"})
        ]),
        ("flagged", "List flagged emails", [
            ("--limit", {"type": int, "default": 10, "help": "Number of emails to display"})
        ]),
        ("unflagged", "List unflagged emails", [
            ("--limit", {"type": int, "default": 10, "help": "Number of emails to display"})
        ]),
        ("flag", "Flag or unflag an email by ID", [
            ("id", {"help": "Email ID (from list command)"}),
            ("--flag", {"action": "store_true", "help": "Flag the email"}),
            ("--unflag", {"action": "store_true", "help": "Unflag the email"})
        ]),
        ("attachments", "List emails with attachments", [
            ("--limit", {"type": int, "default": 10, "help": "Number of attachments to display"})
        ]),
        ("attachments-list", "List attachment filenames for a specific email", [
            ("id", {"help": "Email ID (from list command)"})
        ]),
        ("download", "Download email attachments", [
            ("id", {"help": "Email ID (from list command)"}),
            ("--table", {"default": "inbox", "choices": ["inbox", "sent_emails", "drafts", "deleted_emails"], "help": "Table to search in (default: inbox)"}),
            ("--all", {"action": "store_true", "help": "Download all attachments"}),
            ("--index", {"type": int, "help": "Index of the attachment to download (0-based)"})
        ]),
        ("downloads-list", "List all downloaded attachments", []),
        ("open", "Open downloaded attachment", [
            ("filename", {"help": "Filename of the downloaded attachment to open (from downloads-list command)"})
        ]),
        ("delete", "Delete email in local database", [
            ("id", {"help": "Email ID (from list command)"}),
            ("--all", {"action": "store_true", "help": "Delete in local database and server"}),
        ]),
        ("compose", "Compose and send a new email", []),
        ("move", "Move email to another folder", [
            ("id", {"help": "Email ID (from list command)"}),
            ("--source", {"help": "Current folder of the email"}),
            ("--target", {"help": "Target folder to move the email to"})
        ]),
        ("backup", "Backup the database", [
            ("--path", {"help": "Custom backup path (optional, defaults to config)"})
        ]),
        ("delete-db", "Delete the local database", [
            ("--path", {"help": "Custom path to the database file (optional, defaults to config)"}),
            ("--confirm", {"action": "store_true", "help": "Confirm deletion of the database"})
        ]),
        ("export", "Export all email tables to CSV files", [
            ("--path", {"help": "Export directory path (default: ./exports)"})
        ])
    ]

    for command_name, command_help, arguments in commands_config:
        subparser = subparsers.add_parser(command_name, help=command_help)
        for arg_name, arg_config in arguments:
            subparser.add_argument(arg_name, **arg_config)

    return parser

def main():
    initialize_database()
    
    parser = setup_argument_parser()
    args = parser.parse_args()

    try:
        cfg = config.load_config()

    except Exception as e:
        logger.error(f"Configuration error: {e}")
        console.print(f"[red]Configuration error: {e}[/]")
        return

    if args.command == "list":
        logger.info("Listing emails...")
        console.print("[bold cyan]Loading emails...[/]")
        try:
            emails = storage_api.get_inbox(limit=args.limit)
            inbox_viewer.display_inbox("inbox", emails)

        except Exception as e:
            logger.error(f"Failed to load emails: {e}")
            console.print(f"[red]Failed to load emails: {e}[/]")
            return

    elif args.command == "refresh":
        try:
            if args.all:
                console.print("[yellow]Warning: Fetching all emails can be slow and may hit server limits.[/]")
                if not confirm_action("Are you sure you want to fetch all emails?"):
                    console.print("[yellow]Fetch cancelled.[/]")
                    return
                logger.info("Fetching all emails from server...")
                console.print("[bold cyan]Fetching all emails from server...[/]")
                fetched_count = imap_client.fetch_new_emails(cfg, fetch_all=True)
                
            else:
                logger.info("Fetching new emails from server...")
                console.print("[bold cyan]Fetching new emails from server...[/]")
                fetched_count = imap_client.fetch_new_emails(cfg, fetch_all=False)

            logger.info(f"Fetched {fetched_count} new email(s) from server.")
            console.print(f"[green]Fetched {fetched_count} new email(s) from server.[/]")
            logger.info("Loading emails...")
            console.print("[bold cyan]Loading emails...[/]")
            emails = storage_api.get_inbox(limit=args.limit)
            inbox_viewer.display_inbox("inbox", emails)

        except Exception as e:
            logger.error(f"Failed to fetch or load emails: {e}")
            console.print(f"[red]Failed to fetch or load emails: {e}[/]")
            return

    elif args.command == "view":
        console.print(f"[bold cyan]Fetching email {args.id} from {args.table}...[/]")
        email_data = storage_api.get_email_from_table(args.table, args.id)

        if not email_data:
            logger.warning(f"Email with ID {args.id} not found in '{args.table}'.")
            console.print(f"[red]Email with ID {args.id} not found in '{args.table}'.[/]")
            return

        try:
            email_viewer.display_email(email_data)
        except Exception as e:
            logger.error(f"Failed to display email: {e}")
            console.print(f"[red]Failed to display email: {e}[/]")
            return

    elif args.command == "search":
        try:
            if not args.all and not args.table_name:
                logger.error("Must specify either table_name or --all flag for search.")
                console.print("[red]Error: Must specify either table_name or --all flag[/]")
                return
            
            if args.all:
                logger.info(f"Searching all emails for '{args.keyword}'...")
                console.print(f"[bold cyan]Searching all emails for '{args.keyword}'...[/]")
                search_results = storage_api.search_all_emails(args.keyword)
                search_viewer.display_search_results("all emails", search_results, args.keyword)
                logger.info(f"Search results for all emails containing '{args.keyword}': {search_results}")

            else:
                logger.info(f"Searching {args.table_name} for '{args.keyword}'...")
                console.print(f"[bold cyan]Searching {args.table_name} for '{args.keyword}'...[/]")
                search_results = storage_api.search_emails(args.table_name, args.keyword)
                search_viewer.display_search_results(args.table_name, search_results, args.keyword)
                logger.info(f"Search results for {args.table_name} containing '{args.keyword}': {search_results}")

        except Exception as e:
            logger.error(f"Failed to search emails: {e}")
            console.print(f"[red]Failed to search emails: {e}[/]")
            return

    elif args.command in ["flagged", "unflagged"]:
        flagged_status = args.command == "flagged"
        status_text = "flagged" if flagged_status else "unflagged"
        logger.info(f"Retrieving {status_text} emails...")
        console.print(f"[bold cyan]Loading {status_text} emails...[/]")
        
        try:
            emails = storage_api.search_emails_by_flag_status(flagged_status, limit=args.limit)
            search_viewer.display_search_results("inbox", emails, f"{status_text} emails")
            logger.info(f"Retrieved {len(emails)} {status_text} email(s).")

        except Exception as e:
            logger.error(f"Failed to retrieve {status_text} emails: {e}")
            console.print(f"[red]Failed to retrieve {status_text} emails: {e}[/]")
            return

    elif args.command == "flag":
        if args.flag == args.unflag:
            console.print("[red]Please specify either --flag or --unflag.[/]")
            return

        email_data = storage_api.get_email_from_table("inbox", args.id)
        if not email_data:
            logger.warning(f"Email with ID {args.id} not found in inbox.")
            console.print(f"[red]Email with ID {args.id} not found in inbox.[/]")
            return
            
        try:
            flag_status = True if args.flag else False
            storage_api.mark_email_flagged(args.id, flag_status)
            action = "Flagged" if args.flag else "Unflagged"
            logger.info(f"{action} email ID {args.id} successfully.")
            console.print(f"[green]{action} email ID {args.id} successfully.[/]")

        except Exception as e:
            logger.error(f"Failed to update flag status: {e}")
            console.print(f"[red]Failed to update flag status: {e}[/]")
            return

    elif args.command == "attachments":
        logger.info("Listing emails with attachments...")
        console.print("[bold cyan]Loading emails with attachments...[/]")
        
        try:
            emails = storage_api.search_emails_with_attachments("inbox", limit=args.limit)
            if not emails:
                logger.info("No emails with attachments found.")
                console.print("[yellow]No emails with attachments found.[/]")
                return
            inbox_viewer.display_inbox("inbox", emails)
            logger.info(f"Found {len(emails)} email(s) with attachments.")

        except Exception as e:
            logger.error(f"Failed to retrieve emails with attachments: {e}")
            console.print(f"[red]Failed to retrieve emails with attachments: {e}[/]")
            return

    elif args.command == "attachments-list":
        if args.id is None:
            logger.error("Email ID is required to list attachments.")
            console.print("[red]Email ID is required to list attachments.[/]")
            return
        
        logger.info(f"Listing attachments for email ID {args.id}...")
        console.print(f"[bold cyan]Loading attachment list for email {args.id}...[/]")
        try:
            attachment_list = imap_client.get_attachment_list(cfg, args.id)
            logger.info(f"Found {len(attachment_list)} attachment(s) for email ID {args.id}: {attachment_list}")
            
            if not attachment_list:
                logger.warning(f"No attachments found for email ID {args.id}.")
                console.print(f"[yellow]No attachments found for email ID {args.id}.[/]")
                return
            
            logger.info(f"Attachment list for email ID {args.id}: {attachment_list}")
            console.print(f"[green]Found {len(attachment_list)} attachment(s):[/]")
            for i, filename in enumerate(attachment_list):
                console.print(f"  [cyan]{i}[/]: {filename}")
                
        except Exception as e:
            logger.error(f"Failed to get attachment list: {e}")
            console.print(f"[red]Failed to get attachment list: {e}[/]")
            return

    elif args.command == "download":
        if args.id is None:
            logger.error("Email ID is required for downloading attachments.")
            console.print("[red]Email ID is required for downloading attachments.[/]")
            return
        
        if not args.all and args.index is None:
            logger.error("Must specify either --all or --index to download attachments.")
            console.print("[red]Please specify either --all to download all attachments or --index to download a specific attachment.[/]")
            return
        
        logger.info(f"Downloading attachments for email ID {args.id} from {args.table}...")
        console.print(f"[bold cyan]Downloading attachments for email {args.id} from {args.table}...[/]")
        
        email_data = storage_api.get_email_from_table(args.table, args.id)
        if not email_data:
            logger.warning(f"Email with ID {args.id} not found in '{args.table}'.")
            console.print(f"[red]Email with ID {args.id} not found in '{args.table}'.[/]")
            return

        try:
            attachments_raw = email_data.get('attachments', '')
            if not attachments_raw or not attachments_raw.strip():
                logger.info(f"No attachments found in database for email ID {args.id}, checking server...")
                console.print("[yellow]No attachments found in database, checking server...[/]")
                
                if args.all and not confirm_action(f"Are you sure you want to download attachments for email ID {args.id}?"):
                    logger.info("Download cancelled by user.")
                    console.print("[yellow]Download cancelled.[/]")
                    return
                
                handle_download_action(cfg, args.id, args)
                return

            attachments = [att.strip() for att in attachments_raw.split(',') if att.strip()]
            if not attachments:
                logger.info(f"No valid attachments to download for email ID {args.id}.")
                console.print(f"[yellow]No valid attachments to download for email ID {args.id}.[/]")
                return

            if args.index is not None and (args.index >= len(attachments) or args.index < 0):
                logger.error(f"Invalid attachment index {args.index}. Available attachments: 0-{len(attachments)-1}")
                console.print(f"[red]Invalid attachment index {args.index}. Available attachments: 0-{len(attachments)-1}[/]")
                return

            handle_download_action(cfg, args.id, args)

        except Exception as e:
            logger.error(f"Failed to download attachments: {e}")
            console.print(f"[red]Failed to download attachments: {e}[/]")
            return

    elif args.command == "downloads-list":
        try:
            attachments_path = "./attachments"
            if not os.path.exists(attachments_path):
                logger.error("Attachments folder does not exist.")
                console.print("[yellow]Attachments folder does not exist.[/]")
                return
                
            downloaded_files = os.listdir(attachments_path)
            if not downloaded_files:
                logger.info("No downloaded attachments found in attachments folder.")
                console.print("[yellow]No downloaded attachments found in attachments folder.[/]")
                return

            logger.info(f"Found {len(downloaded_files)} downloaded attachment(s): {downloaded_files}")
            console.print(f"[green]Found {len(downloaded_files)} downloaded attachment(s):[/]")
            for filename in downloaded_files:
                try:
                    file_path = os.path.join(attachments_path, filename)
                    file_size = os.path.getsize(file_path)
                    size_kb = file_size / 1024
                    if size_kb < 1:
                        size_str = f"{file_size}B"
                    elif size_kb < 1024:
                        size_str = f"{size_kb:.1f}KB"
                    else:
                        size_str = f"{size_kb/1024:.1f}MB"
                    console.print(f"  [cyan]{filename}[/] [dim]({size_str})[/]")
                except OSError:
                    logger.warning(f"Failed to get size for file: {filename}")
                    console.print(f"  [cyan]{filename}[/] [dim](size unknown)[/]")

        except Exception as e:
            logger.error(f"Failed to list downloaded attachments: {e}")
            console.print(f"[red]Failed to list downloaded attachments: {e}[/]")
            return

    elif args.command == "open":
        try:
            attachments_path = "./attachments"
            if not os.path.exists(attachments_path):
                logger.error("Attachments folder does not exist.")
                console.print("[red]Attachments folder does not exist.[/]")
                return
            
            # Prevent path traversal attacks by rejecting filenames with path separators
            if os.path.sep in args.filename or ".." in args.filename:
                logger.error("Invalid filename provided for opening attachment.")
                console.print("[red]Invalid filename. Please use only the filename from downloads list.[/]")
                return

            file_path = os.path.join(attachments_path, args.filename)
            if not os.path.exists(file_path):
                logger.error(f"File '{args.filename}' not found in attachments folder.")
                console.print(f"[red]File '{args.filename}' not found in attachments folder.[/]")
                return

            logger.info(f"Opening attachment '{args.filename}'...")
            console.print(f"[bold cyan]Opening attachment '{args.filename}'...[/]")
            try:
                if platform.system() == "Darwin":
                    subprocess.run(["open", file_path], check=True)
                elif platform.system() == "Windows":
                    os.startfile(file_path)
                else:
                    subprocess.run(["xdg-open", file_path], check=True)

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
            return

    elif args.command == "delete":
        if args.id is None:
            logger.error("Email ID is required for deletion.")
            console.print("[red]Email ID is required for deletion.[/]")
            return

        if not storage_api.email_exists("deleted_emails", args.id):

            if not confirm_action(f"Are you sure you want to delete email ID {args.id}?"):
                logger.info("Email deletion cancelled by user.")
                console.print("[yellow]Deletion cancelled.[/]")
                return

            email_data = storage_api.get_email_from_table("inbox", args.id)
            if not email_data:
                logger.warning(f"Email with ID {args.id} not found in inbox.")
                console.print(f"[red]Email with ID {args.id} not found in inbox.[/]")
                return
                
            try:
                email_data["deleted_at"] = datetime.now().strftime("%Y-%m-%d")
                
                if args.all:
                    # Delete from both local database and server
                    storage_api.save_deleted_email(email_data)
                    storage_api.delete_email(args.id)
                    imap_client.delete_email(cfg, args.id)
                    logger.info(f"Deleted email ID {args.id} from local database and server.")
                    console.print(f"[green]Deleted email ID {args.id} from local database and server.[/]")

                else:
                    # Only delete from local database, keep on server
                    storage_api.save_deleted_email(email_data)
                    storage_api.delete_email(args.id)
                    logger.info(f"Deleted email ID {args.id} from local database.")
                    console.print(f"[green]Deleted email ID {args.id} from local database.[/]")

            except Exception as e:
                logger.error(f"Failed to delete email: {e}")
                console.print(f"[red]Failed to delete email: {e}[/]")
                return

        else:
            if not confirm_action("Are you sure you want to permanently delete this email? This action cannot be undone."):
                logger.info("Permanent deletion cancelled by user.")
                console.print("[yellow]Permanent deletion cancelled.[/]")
                return
            
            try:
                storage_api.delete_email_from_table("deleted_emails", args.id)
                logger.info(f"Permanently deleted email ID {args.id} from 'deleted' table.")
                console.print(f"[green]Permanently deleted email ID {args.id} from 'deleted' table.[/]")

            except Exception as e:
                logger.error(f"Failed to permanently delete email: {e}")
                console.print(f"[red]Failed to permanently delete email: {e}[/]")
                return

    elif args.command == "compose":
        try:
            result = composer.compose_email()
            if not result:
                logger.info("Email composition cancelled or failed.")
                console.print("[yellow]Email composition cancelled or failed.[/yellow]")

        except Exception as e:
            logger.error(f"Failed to compose/send email: {e}")
            console.print(f"[red]Failed to compose/send email: {e}[/]")
            return

    elif args.command == "move":
        if not args.source or not args.target:
            logger.error("Both --source and --target folders must be specified.")
            console.print("[red]Both --source and --target folders must be specified.[/]")
            return

        if not storage_api.email_exists(args.source, args.id):
            logger.warning(f"Email ID {args.id} not found in source folder '{args.source}'.")
            console.print(f"[red]Email ID {args.id} not found in source folder '{args.source}'.[/]")
            return

        email_data = storage_api.get_email_from_table(args.source, args.id)
        if not email_data:
            logger.warning(f"Email with ID {args.id} not found in '{args.source}'.")
            console.print(f"[red]Email with ID {args.id} not found in '{args.source}'.[/]")
            return
        
        try:
            valid_tables = ["inbox", "sent_emails", "drafts", "deleted_emails"]
            if args.source not in valid_tables or args.target not in valid_tables:
                logger.error(f"Invalid source or target folder. Valid options: {', '.join(valid_tables)}")
                console.print(f"[red]Invalid source or target folder. Valid options: {', '.join(valid_tables)}[/]")
                return
            
            if args.source == args.target:
                logger.error("Source and target folders must be different.")
                console.print("[red]Source and target folders must be different.[/]")
                return

            storage_api.move_email_between_tables(args.source, args.target, args.id)
            logger.info(f"Moved email ID {args.id} from '{args.source}' to '{args.target}' successfully.")
            console.print(f"[green]Moved email ID {args.id} from '{args.source}' to '{args.target}' successfully.[/]")
        
        except Exception as e:
            logger.error(f"Failed to move email: {e}")
            console.print(f"[red]Failed to move email: {e}[/]")
            return

    elif args.command == "backup":
        try:
            logger.info("Starting database backup...")
            console.print("[bold cyan]Starting database backup...[/]")
            backup_path = storage_api.backup_db(args.path)
            logger.info(f"Database backed up successfully to: {backup_path}")
            console.print(f"[green]Database backed up successfully to: {backup_path}[/]")
        
        except Exception as e:
            logger.error(f"Failed to backup database: {e}")
            console.print(f"[red]Failed to backup database: {e}[/]")
            return

    elif args.command == "delete-db":
        try:
            db_path = args.path if args.path else storage_api.get_db_path()
            if not os.path.exists(db_path):
                logger.error(f"Database file '{db_path}' does not exist.")
                console.print(f"[red]Database file '{db_path}' does not exist.[/]")
                return
            
            if not args.confirm:
                logger.error("Deletion requires --confirm flag to proceed.")
                console.print("[red]Deletion requires --confirm flag to proceed.[/]")
                return
            
            if confirm_action("Would you like to back up the database before deletion?"):
                try:
                    backup_path = storage_api.backup_db()
                    logger.info(f"Database backed up successfully to: {backup_path}")
                    console.print(f"[green]Database backed up successfully to: {backup_path}[/]")
                except Exception as e:
                    logger.error(f"Failed to backup database: {e}")
                    console.print(f"[red]Failed to backup database: {e}[/]")
                    return
            
            if not confirm_action(f"Are you sure you want to delete the database file at '{db_path}'? This action cannot be undone."):
                logger.info("Database deletion cancelled.")
                console.print("[yellow]Database deletion cancelled.[/]")
                return

            # Second confirmation for extra safety on destructive operation
            if not confirm_action("This is your last chance to cancel. Proceed with deletion?"):
                logger.info("Database deletion cancelled.")
                console.print("[yellow]Database deletion cancelled.[/]")
                return

            storage_api.delete_db()
            logger.info(f"Database file '{db_path}' deleted successfully.")
            console.print(f"[green]Database file '{db_path}' deleted successfully.[/]")
        
        except Exception as e:
            logger.error(f"Failed to delete database: {e}")
            console.print(f"[red]Failed to delete database: {e}[/]")
            return

    elif args.command == "export":
        try:
            logger.info("Starting email export to CSV...")
            console.print("[bold cyan]Starting email export to CSV...[/]")
            export_dir = args.path or "./exports"  # Default to exports directory
            exported_files = storage_api.export_db_to_csv(export_dir)

            if exported_files:
                logger.info(f"Successfully exported {len(exported_files)} CSV file(s) to: {export_dir}")
                console.print(f"[green]Successfully exported {len(exported_files)} CSV file(s) to: {export_dir}[/]")
                for file_path in exported_files:
                    console.print(f"  • {file_path}")
            else:
                logger.warning("No tables found to export.")
                console.print(f"[yellow]No tables found to export. Export directory created at: {export_dir}[/]")
        
        except Exception as e:
            logger.error(f"Failed to export emails: {e}")
            console.print(f"[red]Failed to export emails: {e}[/]")
            return

if __name__ == "__main__":
    main()
