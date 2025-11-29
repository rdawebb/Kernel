"""User prompt components."""

from typing import Optional

from rich.console import Console
from rich.prompt import Confirm, Prompt

from src.utils.console import get_console


class ConfirmPrompt:
    """Confirmation prompt component.

    Used by: manage (delete/move), compose (send confirmation).
    """

    def __init__(self, console: Optional[Console] = None):
        self.console = console or get_console()

    def ask(self, message: str, default: bool = False) -> bool:
        """Ask yes/no confirmation.

        Args:
            message: Confirmation message
            default: Default value if user presses Enter

        Returns:
            True if confirmed, False otherwise
        """
        try:
            return Confirm.ask(message, default=default, console=self.console)
        except (KeyboardInterrupt, EOFError):
            return False


class InputPrompt:
    """Text input prompt component.

    Used by: features that need simple text input.
    """

    def __init__(self, console: Optional[Console] = None):
        self.console = console or get_console()

    def ask(
        self, message: str, default: str = "", password: bool = False
    ) -> Optional[str]:
        """Ask for text input.

        Args:
            message: Prompt message
            default: Default value
            password: Hide input (for passwords)

        Returns:
            User input or None if cancelled
        """
        try:
            return Prompt.ask(
                message,
                default=default if default else None,
                password=password,
                console=self.console,
            )
        except (KeyboardInterrupt, EOFError):
            return None
