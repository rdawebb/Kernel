"""Argument parser configuration for Kernel CLI"""

import argparse


## Argument Adding Utilities

def add_filter_arguments(parser: argparse.ArgumentParser) -> None:
    """Add common filter arguments to the parser."""
    
    filter_group = parser.add_argument_group("filters", "Filter displayed emails")

    filter_group.add_argument(
        "--flagged",
        action="store_true",
        help="Show only flagged emails"
    )
    filter_group.add_argument(
        "--unflagged",
        action="store_true",
        help="Show only unflagged emails"
    )
    filter_group.add_argument(
        "--unread",
        action="store_true",
        help="Show only unread emails"
    )
    filter_group.add_argument(
        "--read",
        action="store_true",
        help="Show only read emails"
    )
    filter_group.add_argument(
        "--with-attachments",
        action="store_true",
        help="Show only emails with attachments"
    )

def add_limit_argument(parser: argparse.ArgumentParser, default: int = 10) -> None:
    """Add limit argument for the number of emails to display."""

    parser.add_argument(
        "--limit",
        type=int,
        default=default,
        help=f"Number of emails to display (default: {default})"
    )

def add_folder_argument(parser: argparse.ArgumentParser) -> None:
    """Add folder argument for displaying emails in a specific folder."""

    parser.add_argument(
        "--folder",
        default="inbox",
        choices=["inbox", "sent", "drafts", "trash"],
        help="Email folder (default: inbox)"
    )


## Command Setup Functions

def setup_viewing_commands(subparsers) -> None:
    """Setup inbox, sent, drafts, and trash viewing commands with filters."""

    inbox_parser = subparsers.add_parser(
        "inbox",
        help="View emails in the inbox",
        description="Display emails from the inbox with optional filters"
    )
    add_limit_argument(inbox_parser, default=10)
    add_filter_arguments(inbox_parser)

    sent_parser = subparsers.add_parser(
        "sent",
        help="View sent emails",
        description="Display sent emails with optional filters"
    )
    add_limit_argument(sent_parser, default=10)
    add_filter_arguments(sent_parser)

    drafts_parser = subparsers.add_parser(
        "drafts",
        help="View draft emails",
        description="Display draft emails"
    )
    add_limit_argument(drafts_parser, default=10)
    add_filter_arguments(drafts_parser)

    trash_parser = subparsers.add_parser(
        "trash",
        help="View deleted emails",
        description="Display emails in trash"
    )
    add_limit_argument(trash_parser, default=10)
    add_filter_arguments(trash_parser)

def setup_email_commands(subparsers) -> None:
    """Setup email-related commands (view, delete, move, flag, etc)."""

    email_parser = subparsers.add_parser(
        "email",
        help="Email operations",
        description="Perform actions on individual emails by ID"
    )

    email_subparsers = email_parser.add_subparsers(
        dest="email_command",
        required=True,
        help="Email operation to perform"
    )

    view_parser = email_subparsers.add_parser(
        "view",
        help="View email details",
    )
    view_parser.add_argument("id", help="Email ID")
    add_folder_argument(view_parser)

    delete_parser = email_subparsers.add_parser(
        "delete",
        help="Delete an email",
    )
    delete_parser.add_argument("id", help="Email ID")
    delete_parser.add_argument(
        "--permanent",
        action="store_true",
        help="Permanently delete email (if in trash)"
    )

    flag_parser = email_subparsers.add_parser(
        "flag",
        help="Flag an email",
    )
    flag_parser.add_argument("id", help="Email ID")

    unflag_parser = email_subparsers.add_parser(
        "unflag",
        help="Unflag an email",
    )
    unflag_parser.add_argument("id", help="Email ID")

    move_parser = email_subparsers.add_parser(
        "move",
        help="Move an email to another folder",
    )
    move_parser.add_argument("id", help="Email ID")
    move_parser.add_argument(
        "--to",
        dest="destination",
        required=True,
        choices=["inbox", "sent", "drafts", "trash"],
        help="Destination folder"
    )
    move_parser.add_argument(
        "--from",
        dest="source",
        default="inbox",
        choices=["inbox", "sent", "drafts", "trash"],
        help="Source folder (default: inbox)"
    )

def setup_search_command(subparsers) -> None:
    """Setup the search command with filters."""

    search_parser = subparsers.add_parser(
        "search",
        help="Search emails",
        description="Search for emails matching by keyword with optional filters"
    )
    search_parser.add_argument(
        "keyword",
        help="Keyword to search for"
    )
    search_parser.add_argument(
        "--in",
        dest="folder",
        default="inbox",
        choices=["inbox", "sent", "drafts", "trash"],
        help="Folder to search in (default: inbox)"
    )
    search_parser.add_argument(
        "--all",
        action="store_true",
        help="Search in all folders"
    )
    add_limit_argument(search_parser, default=50)
    add_filter_arguments(search_parser)

def setup_attachment_commands(subparsers) -> None:
    """Setup attachment-related commands."""

    attachments_parser = subparsers.add_parser(
        "attachments",
        help="Attachment operations",
        description="Manage email attachments"
    )

    attachments_subparsers = attachments_parser.add_subparsers(
        dest="attachment_command",
        help="Attachment operation to perform"
    )

    # Default to 'list' if no subcommand is provided
    add_limit_argument(attachments_parser, default=10)
    add_filter_arguments(attachments_parser)

    list_parser = attachments_subparsers.add_parser(
        "list",
        help="List emails with attachments",
    )
    list_parser.add_argument("id", help="Email ID")

    download_parser = attachments_subparsers.add_parser(
        "download",
        help="Download attachments from an email",
    )
    download_parser.add_argument("id", help="Email ID")
    download_parser.add_argument(
        "--all",
        action="store_true",
        help="Download all attachments"
    )
    download_parser.add_argument(
        "--index",
        type=int,
        help="Download attachment by index (0-based)"
    )

    downloads_parser = attachments_subparsers.add_parser(
        "downloads",
        help="List all downloaded attachments"
    )

    open_parser = attachments_subparsers.add_parser(
        "open",
        help="Open a downloaded attachment"
    )
    open_parser.add_argument("filename", help="Filename to open")

def setup_compose_commands(subparsers) -> None:
    """Setup compose command."""

    compose_parser = subparsers.add_parser(
        "compose",
        help="Compose a new email",
        description="Compose and send a new email"
    )

    # Optional direct composition arguments

    compose_parser.add_argument(
        "--to",
        help="Recipient email addresses (comma-separated)"
    )
    compose_parser.add_argument(
        "--subject",
        help="Email subject"
    )
    compose_parser.add_argument(
        "--body",
        help="Email body content"
    )
    compose_parser.add_argument(
        "--cc",
        action="append",
        help="CC recipient email addresses (comma-separated)"
    )
    compose_parser.add_argument(
        "--bcc",
        action="append",
        help="BCC recipient email addresses (comma-separated)"
    )

def setup_maintenance_commands(subparsers) -> None:
    """Setup maintenance commands (refresh, backup, etc)."""

    refresh_parser = subparsers.add_parser(
        "refresh",
        help="Fetch new emails from server",
        description="Download new emails from IMAP server"
    )
    refresh_parser.add_argument(
        "--all",
        action="store_true",
        help="Fetch all emails, not just new ones"
    )
    add_limit_argument(refresh_parser, default=50)

    db_parser = subparsers.add_parser(
        "database",
        help="Database operations",
    )

    db_subparsers = db_parser.add_subparsers(
        dest="db_command",
        required=True,
        help="Database operation to perform"
    )

    backup_parser = db_subparsers.add_parser(
        "backup",
        help="Backup the database",
    )
    backup_parser.add_argument(
        "--path",
        help="Custom backup file path"
    )

    export_parser = db_subparsers.add_parser(
        "export",
        help="Export emails to CSV",
    )
    export_parser.add_argument(
        "--path",
        default="./exports",
        help="Export directory (default: ./exports)"
    )

    delete_parser = db_subparsers.add_parser(
        "delete",
        help="Delete the local database"
    )
    delete_parser.add_argument(
        "--confirm",
        action="store_true",
        required=True,
        help="Confirm database deletion (required)"
    )

    info_parser = db_subparsers.add_parser(
        "info",
        help="Show database information"
    )

def setup_config_commands(subparsers) -> None:
    """Setup configuration management commands."""

    config_parser = subparsers.add_parser(
        "config",
        help="Configuration management",
        description="Manage application configuration settings"
    )

    config_subparsers = config_parser.add_subparsers(
        dest="config_command",
        required=True,
        help="Configuration operation to perform"
    )

    list_parser = config_subparsers.add_parser(
        "list",
        help="List current settings"
    )

    get_parser = config_subparsers.add_parser(
        "get",
        help="Get a setting value"
    )
    get_parser.add_argument("key", help="Config key to get")

    set_parser = config_subparsers.add_parser(
        "set",
        help="Set a setting value"
    )
    set_parser.add_argument("key", help="Config key to set")
    set_parser.add_argument("value", help="New value for the config key")

    reset_parser = config_subparsers.add_parser(
        "reset",
        help="Reset settings to default"
    )
    reset_parser.add_argument(
        "--key",
        nargs="?",
        help="Specific config key to reset (omit to reset all)"
    )


## Main Parser Setup

def setup_argument_parser() -> argparse.ArgumentParser:
    """Setup the main argument parser for the Kernel CLI."""

    parser = argparse.ArgumentParser(
        prog="kernel",
        description="Minimal Email Client - fetch, view, send, and manage emails",
        epilog="Use 'kernel <command> --help' for command-specific help."
    )

    parser.add_argument(
        "--version",
        action="version",
        version="Kernel 0.1.0",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        help="Command to execute"
    )

    setup_viewing_commands(subparsers)
    setup_email_commands(subparsers)
    setup_search_command(subparsers)
    setup_attachment_commands(subparsers)
    setup_compose_commands(subparsers)
    setup_maintenance_commands(subparsers)
    setup_config_commands(subparsers)

    return parser
