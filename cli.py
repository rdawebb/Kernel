import argparse
from rich.console import Console
from core import imap_client, storage
from ui import inbox_viewer, email_viewer
from utils import config

console = Console()

try:
    storage.initialize_db()
except Exception as e:
    console.print(f"[red]Failed to initialize database: {e}[/]")
    exit(1)

def main():
    parser = argparse.ArgumentParser(
        prog="quiet_mail",
        description="Minimal Email Client — fetch, view, send, and manage emails."
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List recent emails")
    list_parser.add_argument("--limit", type=int, default=10,
                             help="Number of emails to display")

    view_parser = subparsers.add_parser("view", help="View a specific email by ID")
    view_parser.add_argument("id", help="Email ID (from list command)")

    args = parser.parse_args()

    try:
        cfg = config.load_config()
    except Exception as e:
        console.print(f"[red]Configuration error: {e}[/]")
        return

    if args.command == "list":
        console.print("[bold cyan]Fetching inbox...[/]")
        try:
            emails = imap_client.fetch_inbox(cfg, limit=args.limit)

            # Save metadata and body separately for efficiency
            for e in emails:
                storage.save_email_metadata(
                    e.get("uid"), 
                    e.get("from"), 
                    e.get("subject"), 
                    e.get("date"),
                    e.get("time")
                )
                if e.get("body"):
                    storage.save_email_body(e.get("uid"), e.get("body"))

            inbox_viewer.display_inbox(emails)
        except Exception as e:
            console.print(f"[red]Failed to fetch or display inbox: {e}[/]")

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

if __name__ == "__main__":
    main()
