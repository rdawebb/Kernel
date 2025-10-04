import argparse
from rich.console import Console
from quiet_mail.core import imap_client, storage
from quiet_mail.ui import inbox_viewer, email_viewer, search_viewer
from quiet_mail.utils import config

console = Console()

try:
    storage.initialize_db()
except Exception as e:
    console.print(f"[red]Failed to initialize database: {e}[/]")
    exit(1)

def setup_argument_parser():
    """Configure and return the argument parser with all subcommands"""
    parser = argparse.ArgumentParser(
        prog="quiet_mail",
        description="Minimal Email Client — fetch, view, send, and manage emails."
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Command configurations: (name, help, arguments)
    commands_config = [
        ("list", "List recent emails", [
            ("--limit", {"type": int, "default": 10, "help": "Number of emails to display"}),
            ("--refresh", {"action": "store_true", "help": "Fetch and show fresh emails from server instead of local database (slow)"})
        ]),
        ("view", "View a specific email by ID", [
            ("id", {"help": "Email ID (from list command)"})
        ]),
        ("search", "Search emails by keyword", [
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
        ])
    ]

    # Create subparsers from configuration
    for command_name, command_help, arguments in commands_config:
        subparser = subparsers.add_parser(command_name, help=command_help)
        for arg_name, arg_config in arguments:
            subparser.add_argument(arg_name, **arg_config)

    return parser

def main():
    parser = setup_argument_parser()
    args = parser.parse_args()

    try:
        cfg = config.load_config()
    except Exception as e:
        console.print(f"[red]Configuration error: {e}[/]")
        return

    if args.command == "list":
        if args.refresh:
            # Slow: fetch fresh emails from IMAP server
            console.print("[bold cyan]Fetching inbox...[/]")
            try:
                emails = imap_client.fetch_inbox(cfg, limit=args.limit)

                # Save metadata and body separately for efficiency
                for e in emails:
                    storage.save_email_metadata(
                        e.get("uid"), 
                        e.get("from"), 
                        e.get("subject"), 
                        e.get("to"),
                        e.get("date"),
                        e.get("time")
                    )
                    if e.get("body"):
                        storage.save_email_body(e.get("uid"), e.get("body"))

                inbox_viewer.display_inbox(emails)
            except Exception as e:
                console.print(f"[red]Failed to fetch or display inbox: {e}[/]")
        else:
            # Fast: show emails from local database
            console.print("[bold cyan]Loading emails...[/]")
            try:
                emails = storage.get_inbox(limit=args.limit)
                inbox_viewer.display_inbox(emails)
            except Exception as e:
                console.print(f"[red]Failed to load emails: {e}[/]")

    elif args.command == "view":
        console.print(f"[bold cyan]Fetching email {args.id}...[/]")

        try:
            email_data = storage.get_email(args.id)
            if not email_data:
                console.print(f"[red]Email with ID {args.id} not found.[/]")
                return

            email_viewer.display_email(email_data)
        except Exception as e:
            console.print(f"[red]Failed to retrieve or display email: {e}[/]")

    elif args.command == "search":
        console.print(f"[bold cyan]Searching emails for '{args.keyword}'...[/]")
        
        try:
            search_results = storage.search_emails(args.keyword)
            search_viewer.display_search_results(search_results, args.keyword)
        except Exception as e:
            console.print(f"[red]Failed to search emails: {e}[/]")

    elif args.command in ["flagged", "unflagged"]:
        flagged_status = args.command == "flagged"
        status_text = "flagged" if flagged_status else "unflagged"
        console.print(f"[bold cyan]Loading {status_text} emails...[/]")
        
        try:
            emails = storage.search_emails_by_flag_status(flagged_status, limit=args.limit)
            search_viewer.display_search_results(emails, f"{status_text} emails")
        except Exception as e:
            console.print(f"[red]Failed to retrieve {status_text} emails: {e}[/]")

    elif args.command == "flag":
        if args.flag == args.unflag:
            console.print("[red]Please specify either --flag or --unflag.[/]")
            return

        try:
            email_data = storage.get_email(args.id)
            if not email_data:
                console.print(f"[red]Email with ID {args.id} not found.[/]")
                return

            flag_status = True if args.flag else False
            storage.mark_email_flagged(args.id, flag_status)
            action = "Flagged" if args.flag else "Unflagged"
            console.print(f"[green]{action} email ID {args.id} successfully.[/]")
        except Exception as e:
            console.print(f"[red]Failed to update flag status: {e}[/]")

if __name__ == "__main__":
    main()
