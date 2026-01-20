"""Argument parser configuration for Kernel CLI"""

import argparse

from .commands import (
    AttachmentsCommand,
    ComposeCommand,
    ConfigCommand,
    DatabaseCommand,
    EmailOperationsCommand,
    RefreshCommand,
    SearchCommand,
    create_folder_commands,
)


## Command Setup Functions


def setup_viewing_commands(subparsers) -> None:
    """Setup inbox, sent, drafts, and trash viewing commands with filters.

    Uses command pattern - each command defines its own arguments.
    """
    # Create temporary command instances to extract argument definitions
    for command in create_folder_commands():
        parser = subparsers.add_parser(
            command.name,
            help=command.description,
            description=command.description,
        )
        command.add_arguments(parser)


def setup_email_commands(subparsers) -> None:
    """Setup email-related commands (view, delete, move, flag, etc).

    Uses command pattern - EmailOperationsCommand defines its own subcommands.
    """
    command = EmailOperationsCommand()
    parser = subparsers.add_parser(
        command.name,
        help=command.description,
        description="Perform actions on individual emails by ID",
    )
    command.add_arguments(parser)


def setup_search_command(subparsers) -> None:
    """Setup the search command with filters.

    Uses command pattern - SearchCommand defines its own arguments.
    """
    command = SearchCommand()
    parser = subparsers.add_parser(
        command.name,
        help=command.description,
        description="Search for emails matching by keyword with optional filters",
    )
    command.add_arguments(parser)


def setup_attachment_commands(subparsers) -> None:
    """Setup attachment-related commands.

    Uses command pattern - AttachmentsCommand defines its own subcommands.
    """
    command = AttachmentsCommand()
    parser = subparsers.add_parser(
        command.name,
        help=command.description,
        description="Manage email attachments",
    )
    command.add_arguments(parser)


def setup_compose_commands(subparsers) -> None:
    """Setup compose command.

    Uses command pattern - ComposeCommand defines its own arguments.
    """
    command = ComposeCommand()
    parser = subparsers.add_parser(
        command.name,
        help=command.description,
        description="Compose and send a new email",
    )
    command.add_arguments(parser)


def setup_maintenance_commands(subparsers) -> None:
    """Setup maintenance commands (refresh, database).

    Uses command pattern for both commands.
    """
    # Refresh command
    refresh_cmd = RefreshCommand()
    refresh_parser = subparsers.add_parser(
        refresh_cmd.name,
        help=refresh_cmd.description,
        description="Download new emails from IMAP server",
    )
    refresh_cmd.add_arguments(refresh_parser)

    # Database command
    db_cmd = DatabaseCommand()
    db_parser = subparsers.add_parser(
        db_cmd.name,
        help=db_cmd.description,
        description="Database maintenance operations",
    )
    db_cmd.add_arguments(db_parser)


def setup_config_commands(subparsers) -> None:
    """Setup configuration management commands.

    Uses command pattern - ConfigCommand defines its own subcommands.
    """
    command = ConfigCommand()
    parser = subparsers.add_parser(
        command.name,
        help=command.description,
        description="Manage application configuration settings",
    )
    command.add_arguments(parser)


## Main Parser Setup


def setup_argument_parser(exit_on_error=True) -> argparse.ArgumentParser:
    """Setup the main argument parser for the Kernel CLI."""
    parser = argparse.ArgumentParser(
        prog="kernel",
        description="Minimal Email Client - fetch, view, send, and manage emails",
        epilog="Use 'kernel <command> --help' for command-specific help.",
        exit_on_error=exit_on_error,
    )

    parser.add_argument(
        "--version",
        action="version",
        version="Kernel 0.1.0",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    setup_viewing_commands(subparsers)
    setup_email_commands(subparsers)
    setup_search_command(subparsers)
    setup_attachment_commands(subparsers)
    setup_compose_commands(subparsers)
    setup_maintenance_commands(subparsers)
    setup_config_commands(subparsers)

    return parser
