from typing import Dict, Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.utils.console import get_console


class EmailPanel:
    """Display single email in panels.
    
    Used by: view feature.
    """
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or get_console()
    
    def display(self, email: Dict[str, Any]) -> None:
        """Display email with header and body panels."""
        # Header panel
        self.console.print(Panel(
            self._format_header(email),
            title=f"[bold]Email {email.get('uid')}[/bold]",
            border_style="cyan",
            padding=(1, 2)
        ))
        
        # Attachments panel (if present)
        if email.get('attachments'):
            self._display_attachments(email['attachments'])
        
        # Body panel
        body = email.get('body', '')
        if not body or not body.strip():
            body = "[italic dim]No content[/italic dim]"
        
        self.console.print(Panel(
            body,
            title="[bold]Body[/bold]",
            border_style="cyan dim",
            padding=(1, 2)
        ))
    
    def _format_header(self, email: Dict[str, Any]) -> str:
        """Format email header as markup string."""
        lines = [
            f"[bold]From:[/bold] {email.get('from', 'Unknown')}",
            f"[bold]To:[/bold] {email.get('to', 'Unknown')}",
            f"[bold]Date:[/bold] {email.get('date', '')} {email.get('time', '')}",
            f"[bold]Subject:[/bold] {email.get('subject', 'No Subject')}"
        ]
        return "\n".join(lines)
    
    def _display_attachments(self, attachments: str) -> None:
        """Display attachments list panel."""
        att_list = [a.strip() for a in attachments.split(',') if a.strip()]
        if att_list:
            self.console.print(Panel(
                f"[bold]Attachments:[/bold] {', '.join(att_list)}",
                border_style="magenta dim",
                padding=(0, 2)
            ))


class PreviewPanel:
    """Email preview panel for composition.
    
    Used by: compose feature.
    """
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or get_console()
    
    def display(self, email_data: Dict[str, Any]) -> None:
        """Display email preview before sending."""
        self.console.print("\n[bold yellow]Preview[/bold yellow]\n")
        
        # Create preview table (compact format)
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column(style="bold", width=10)
        table.add_column()
        
        table.add_row("From:", email_data.get('from', 'Not set'))
        table.add_row("To:", email_data.get('recipient', email_data.get('to', '')))
        table.add_row("Subject:", email_data.get('subject', ''))
        
        self.console.print(Panel(table, border_style="yellow", padding=(1, 2)))
        
        # Body preview
        body = email_data.get('body', '')
        if body:
            # Truncate long bodies
            if len(body) > 500:
                body = body[:497] + "..."
            
            self.console.print(Panel(
                Text(body),
                title="[bold]Body[/bold]",
                border_style="yellow dim",
                padding=(1, 2)
            ))
        else:
            self.console.print(Panel(
                "[italic dim]Empty body[/italic dim]",
                title="[bold]Body[/bold]",
                border_style="yellow dim",
                padding=(1, 2)
            ))


class StatusPanel:
    """Status display panel.
    
    Used by: all features for success/error messages.
    """
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or get_console()
    
    def show_success(self, message: str, title: Optional[str] = None) -> None:
        """Display success message in green panel."""
        self.console.print()
        self.console.print(Panel.fit(
            f"[bold green]✓ {message}[/bold green]",
            title=title,
            border_style="green",
            padding=(1, 2)
        ))
    
    def show_error(self, message: str, title: Optional[str] = None) -> None:
        """Display error message in red panel."""
        self.console.print()
        self.console.print(Panel.fit(
            f"[bold red]✗ {message}[/bold red]",
            title=title,
            border_style="red",
            padding=(1, 2)
        ))
    
    def show_warning(self, message: str, title: Optional[str] = None) -> None:
        """Display warning message in yellow panel."""
        self.console.print()
        self.console.print(Panel.fit(
            f"[bold yellow]⚠ {message}[/bold yellow]",
            title=title,
            border_style="yellow",
            padding=(1, 2)
        ))
    
    def show_info(self, message: str, title: Optional[str] = None) -> None:
        """Display info message in cyan panel."""
        self.console.print()
        self.console.print(Panel.fit(
            f"[cyan]{message}[/cyan]",
            title=title,
            border_style="cyan",
            padding=(1, 2)
        ))