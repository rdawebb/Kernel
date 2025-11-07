"""View display coordinator (uses shared UI components)."""

from typing import Any, Dict, List, Optional
from rich.console import Console

from src.ui.components import EmailPanel, EmailTable, StatusMessage


class ViewDisplay:
    """Coordinates display for view feature."""
    
    def __init__(self, console: Optional[Console] = None):
        self.table = EmailTable(console)
        self.panel = EmailPanel(console)
        self.message = StatusMessage(console)
    
    def display_single(self, email: Dict[str, Any]) -> None:
        """Display single email (delegates to EmailPanel)."""
        self.panel.display(email)
    
    def display_list(
        self,
        emails: List[Dict[str, Any]],
        folder: str,
        show_flagged: bool = False
    ) -> None:
        """Display email list (delegates to EmailTable)."""
        self.table.display(
            emails=emails,
            title=folder.title(),
            show_flagged=show_flagged,
            show_source=False
        )
    
    def show_error(self, message: str) -> None:
        """Show error (delegates to StatusMessage)."""
        self.message.error(message)