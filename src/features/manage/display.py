"""Email management display coordinator (uses shared UI components)."""

from typing import Any, Dict, Optional
from rich.console import Console

from src.ui.components import ConfirmPrompt, StatusMessage, StatusPanel


class ManageDisplay:
    """Coordinates display for email management feature."""
    
    def __init__(self, console: Optional[Console] = None):
        self.confirm = ConfirmPrompt(console)
        self.message = StatusMessage(console)
        self.panel = StatusPanel(console)
        self.console = console or self.message.console
    
    
    # Confirmation prompts
    
    async def confirm_delete(
        self, 
        email: Dict[str, Any], 
        permanent: bool = False
    ) -> bool:
        """Ask user to confirm email deletion.
        
        Args:
            email: Email data (from DB query)
            permanent: If True, ask about permanent deletion
            
        Returns:
            True if user confirms, False otherwise
        """
        subject = email.get('subject', 'No Subject')[:50]
        from_addr = email.get('from', 'Unknown')
        
        if permanent:
            prompt = f"Permanently delete email from {from_addr} ('{subject}')?"
        else:
            prompt = f"Move email from {from_addr} ('{subject}') to trash?"
        
        return self.confirm.ask(prompt, default=False)
    
    async def confirm_move(
        self,
        email: Dict[str, Any],
        from_folder: str,
        to_folder: str
    ) -> bool:
        """Ask user to confirm moving email between folders.
        
        Args:
            email: Email data (from DB query)
            from_folder: Source folder
            to_folder: Destination folder
            
        Returns:
            True if user confirms, False otherwise
        """
        subject = email.get('subject', 'No Subject')[:50]
        prompt = f"Move email '{subject}' from {from_folder} to {to_folder}?"
        return self.confirm.ask(prompt, default=False)
    

    # Status messages
    
    def show_deleted(self, email_id: str, permanent: bool = False) -> None:
        """Show successful deletion.
        
        Args:
            email_id: Email UID
            permanent: If True, was permanently deleted; else moved to trash
        """
        if permanent:
            self.panel.show_success(f"Email {email_id} permanently deleted")
        else:
            self.panel.show_success(f"Email {email_id} moved to trash")
    
    def show_moved(
        self, 
        email_id: str, 
        from_folder: str, 
        to_folder: str
    ) -> None:
        """Show successful move operation.
        
        Args:
            email_id: Email UID
            from_folder: Source folder
            to_folder: Destination folder
        """
        self.panel.show_success(f"Email {email_id} moved from {from_folder} to {to_folder}")
    
    def show_flagged(self, email_id: str, flagged: bool = True) -> None:
        """Show successful flag/unflag operation.
        
        Args:
            email_id: Email UID
            flagged: True if flagged, False if unflagged
        """
        action = "flagged" if flagged else "unflagged"
        self.panel.show_success(f"Email {email_id} {action}")
    
    def show_cancelled(self) -> None:
        """Show operation cancellation."""
        self.message.warning("Operation cancelled")
    
    def show_error(self, message: str) -> None:
        """Show error message.
        
        Args:
            message: Error description
        """
        self.panel.show_error(message)