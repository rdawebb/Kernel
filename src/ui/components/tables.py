"""Email table display component."""

from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.table import Table

from src.utils.console import get_console


class EmailTable:
    """Reusable email table component.

    Used by: view, search, attachments list, etc.
    """

    def __init__(self, console: Optional[Console] = None):
        self.console = console or get_console()

    def display(
        self,
        emails: List[Dict[str, Any]],
        title: str = "Emails",
        show_flagged: bool = False,
        show_source: bool = False,
        show_attachments: bool = True,
        columns: Optional[List[str]] = None,
    ) -> None:
        """Display emails as formatted table.

        Args:
            emails: List of email dictionaries
            title: Table title
            show_flagged: Include flagged indicator column
            show_source: Include source folder column
            show_attachments: Include attachment indicator column
            columns: Custom column list (overrides defaults)
        """
        if not emails:
            self.console.print("[yellow]No emails to display[/yellow]")
            return

        table = Table(title=title)

        # Add columns
        if columns:
            self._add_custom_columns(table, columns)
        else:
            self._add_default_columns(
                table, show_flagged, show_source, show_attachments
            )

        # Add rows
        for email in emails:
            row = self._build_row(
                email, show_flagged, show_source, show_attachments, columns
            )
            table.add_row(*row)

        self.console.print(table)

    def _add_default_columns(
        self,
        table: Table,
        show_flagged: bool,
        show_source: bool,
        show_attachments: bool,
    ):
        """Add default table columns."""
        table.add_column("ID", style="cyan", justify="right", no_wrap=True)
        table.add_column("From", style="magenta", min_width=20)
        table.add_column("Subject", style="green", min_width=20)
        table.add_column("Date", style="yellow", justify="right")
        table.add_column("Time", style="yellow", justify="right")

        if show_attachments:
            table.add_column("", style="blue", width=3, justify="center")  # 📎
        if show_source:
            table.add_column("Folder", style="white", min_width=10)
        if show_flagged:
            table.add_column("", style="red", width=3, justify="center")  # 🚩

    def _add_custom_columns(self, table: Table, columns: List[str]):
        """Add custom columns based on list."""
        for col in columns:
            if col == "id":
                table.add_column("ID", style="cyan", justify="right")
            elif col == "from":
                table.add_column("From", style="magenta")
            elif col == "subject":
                table.add_column("Subject", style="green")
            elif col == "date":
                table.add_column("Date", style="yellow")
            elif col == "time":
                table.add_column("Time", style="yellow")
            elif col == "attachments":
                table.add_column("", style="blue", width=3)
            elif col == "source":
                table.add_column("Folder", style="white")
            elif col == "flagged":
                table.add_column("", style="red", width=3)

    def _build_row(
        self,
        email: Dict[str, Any],
        show_flagged: bool,
        show_source: bool,
        show_attachments: bool,
        custom_columns: Optional[List[str]] = None,
    ) -> List[str]:
        """Build table row from email data."""
        if custom_columns:
            return self._build_custom_row(email, custom_columns)

        # Default row
        row = [
            str(email.get("uid", "N/A")),
            self._truncate(email.get("from", "Unknown"), 25),
            self._truncate(email.get("subject", "No Subject"), 30),
            email.get("date", ""),
            email.get("time", ""),
        ]

        if show_attachments:
            has_attachments = bool(email.get("attachments", "").strip())
            row.append("📎" if has_attachments else "")

        if show_source:
            source = email.get("source_table", "unknown")
            row.append(self._format_source(source))

        if show_flagged:
            row.append("🚩" if email.get("flagged") else "")

        return row

    def _build_custom_row(self, email: Dict[str, Any], columns: List[str]) -> List[str]:
        """Build custom row based on column list."""
        row = []
        for col in columns:
            if col == "id":
                row.append(str(email.get("uid", "N/A")))
            elif col == "from":
                row.append(self._truncate(email.get("from", "Unknown"), 25))
            elif col == "subject":
                row.append(self._truncate(email.get("subject", "No Subject"), 30))
            elif col == "date":
                row.append(email.get("date", ""))
            elif col == "time":
                row.append(email.get("time", ""))
            elif col == "attachments":
                has_att = bool(email.get("attachments", "").strip())
                row.append("📎" if has_att else "")
            elif col == "source":
                row.append(self._format_source(email.get("source_table", "unknown")))
            elif col == "flagged":
                row.append("🚩" if email.get("flagged") else "")
        return row

    @staticmethod
    def _truncate(text: str, max_length: int) -> str:
        """Truncate text with ellipsis."""
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."

    @staticmethod
    def _format_source(source: str) -> str:
        """Format source table name for display."""
        source_map = {
            "inbox": "Inbox",
            "sent": "Sent",
            "sent_emails": "Sent",
            "drafts": "Drafts",
            "trash": "Trash",
            "deleted_emails": "Deleted",
        }
        return source_map.get(source, source.title())
