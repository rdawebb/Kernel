"""Argument parser configuration for Kernel CLI"""
import argparse
from typing import Any, Dict, List, Tuple

EMAIL_TABLES = ["inbox", "sent_emails", "drafts", "deleted_emails"]
SEARCH_TABLES = ["inbox", "sent", "drafts", "deleted"]

LIMIT_ARG = {"type": int, "default": 10, "help": "Number of items to display"}
TABLE_ARG = {"default": "inbox", "choices": EMAIL_TABLES, "help": "Table to search in (default: inbox)"}

COMMANDS_CONFIG: List[Tuple[str, str, List[Tuple[str, Dict[str, Any]]]]] = [
    ("attachments", "List emails with attachments", [
        ("--limit", LIMIT_ARG),
    ]),
    ("attachments-list", "List attachment filenames for a specific email", [
        ("id", {"help": "Email ID (from list command)"}),
    ]),
    ("backup", "Backup the database", [
        ("--path", {"help": "Custom backup path (optional, defaults to config)"}),
    ]),
    ("compose", "Compose and send a new email", []),
    ("delete", "Delete email in local database", [
        ("id", {"help": "Email ID (from list command)"}),
        ("--all", {"action": "store_true", "help": "Delete in local database and server"}),
    ]),
    ("delete-db", "Delete the local database", [
        ("--path", {"help": "Custom path to the database file (optional, defaults to config)"}),
        ("--confirm", {"action": "store_true", "help": "Confirm deletion of the database"}),
    ]),
    ("download", "Download email attachments", [
        ("id", {"help": "Email ID (from list command)"}),
        ("--table", TABLE_ARG),
        ("--all", {"action": "store_true", "help": "Download all attachments"}),
        ("--index", {"type": int, "help": "Index of the attachment to download (0-based)"}),
    ]),
    ("downloads-list", "List all downloaded attachments", []),
    ("export", "Export all email tables to CSV files", [
        ("--path", {"help": "Export directory path (default: ./exports)"}),
    ]),
    ("flag", "Flag or unflag an email by ID", [
        ("id", {"help": "Email ID (from list command)"}),
        ("--flag", {"action": "store_true", "help": "Flag the email"}),
        ("--unflag", {"action": "store_true", "help": "Unflag the email"}),
    ]),
    ("flagged", "List flagged emails", [
        ("--limit", LIMIT_ARG),
    ]),
    ("list", "List recent emails", [
        ("--limit", LIMIT_ARG),
    ]),
    ("move", "Move email to another folder", [
        ("id", {"help": "Email ID (from list command)"}),
        ("--source", {"help": "Current folder of the email"}),
        ("--target", {"help": "Target folder to move the email to"}),
    ]),
    ("open", "Open downloaded attachment", [
        ("filename", {"help": "Filename of the downloaded attachment to open (from downloads-list command)"}),
    ]),
    ("refresh", "Fetch new emails", [
        ("--limit", LIMIT_ARG),
        ("--all", {"action": "store_true", "help": "Fetch all emails from server"}),
    ]),
    ("search", "Search emails by keyword", [
        ("table_name", {"nargs": "?", "choices": SEARCH_TABLES, "help": "Table to search (not used with --all)"}),
        ("--all", {"action": "store_true", "help": "Search all emails"}),
        ("keyword", {"help": "Keyword to search in emails"}),
    ]),
    ("unflagged", "List unflagged emails", [
        ("--limit", LIMIT_ARG),
    ]),
    ("view", "View a specific email by ID", [
        ("id", {"help": "Email ID (from list command)"}),
        ("--table", TABLE_ARG),
    ]),
]

def setup_argument_parser() -> argparse.ArgumentParser:
    """Configure and return the argument parser with all CLI subcommands."""
    parser = argparse.ArgumentParser(
        prog="kernel",
        description="Minimal Email Client — fetch, view, send, and manage emails."
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    for command_name, command_help, arguments in COMMANDS_CONFIG:
        subparser = subparsers.add_parser(command_name, help=command_help)
        for arg_name, arg_config in arguments:
            subparser.add_argument(arg_name, **arg_config)

    return parser
