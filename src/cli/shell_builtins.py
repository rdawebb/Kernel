"""Shell built-in commands for Kernel interactive shell."""

import os
import shlex
import subprocess
from typing import Optional

from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .router import CommandRouter


class ShellBuiltins:
    """Handler for shell-specific built-in commands."""

    def __init__(self, router: CommandRouter, console: Optional[Console] = None):
        """Initialise shell builtins.

        Args:
            router: CommandRouter instance for listing commands
            console: Rich Console instance
        """
        self.router = router
        self.console = console or Console()

    def get_builtin_commands(self) -> dict[str, str]:
        """Get dict of built-in command names and descriptions.

        Returns:
            Dict mapping command names to descriptions
        """
        return {
            "commands": "list available commands",
            "help": "show this help message",
            "?": "show this help message",
            "exit": "exit the shell",
            "quit": "exit the shell",
            "reload": "reload configuration (and re-init router)",
            "clear": "clear the screen",
            "cls": "clear the screen",
            "shell <command>": "execute a shell command (e.g., shell ls -la)",
        }

    def is_builtin(self, command: str) -> bool:
        """Check if command is a shell built-in.

        Args:
            command: Command string

        Returns:
            True if command is a built-in
        """
        cmd = command.strip().split()[0] if command.strip() else ""
        return cmd in {
            "help",
            "?",
            "commands",
            "exit",
            "quit",
            "clear",
            "cls",
            "reload",
        } or command.strip().startswith("shell ")

    async def handle_builtin(self, command: str) -> tuple[bool, bool]:
        """Handle a shell built-in command.

        Args:
            command: Command string

        Returns:
            Tuple of (should_continue, was_handled)
            - should_continue: False if shell should exit
            - was_handled: True if command was a built-in
        """
        command = command.strip()

        # Shell command
        if command.startswith("shell "):
            cmd = command[len("shell ") :].strip()
            if cmd:
                try:
                    subprocess.run(shlex.split(cmd), shell=True, check=False)
                except Exception as e:
                    self.console.print(f"[red]Shell command failed: {e}[/red]")
            return True, True

        # Help commands
        if command in {"help", "?"}:
            self._print_help()
            return True, True

        # Commands list
        if command == "commands":
            self._print_commands()
            return True, True

        # Exit commands
        if command in {"exit", "quit"}:
            self.console.print(
                Panel(
                    Align.center("Exiting Kernel Mail App - [bold green]Goodbye![/]"),
                    border_style="dim cyan",
                    padding=(1, 2),
                )
            )
            return False, True

        # Clear screen
        if command in {"clear", "cls"}:
            os.system("cls" if os.name == "nt" else "clear")
            return True, True

        # Reload config
        if command == "reload":
            self.console.print(
                "[yellow]Note: Config reload requires router re-initialization[/yellow]"
            )
            self.console.print(
                "[yellow]Please restart the shell for config changes to take effect[/yellow]"
            )
            return True, True

        return True, False

    def _print_help(self) -> None:
        """Print shell help table."""
        table = Table(title="Kernel Mail App Commands", expand=True, show_lines=True)
        table.add_column("Command", style="cyan", no_wrap=True)
        table.add_column("Description", style="magenta")

        for cmd, desc in self.get_builtin_commands().items():
            table.add_row(cmd, desc)

        self.console.print(table)
        self.console.print(
            Panel(
                Align.center(
                    "Tip: type [bold]commands[/bold] to see available commands"
                ),
                border_style="cyan",
            )
        )

    def _print_commands(self) -> None:
        """Print available Kernel commands."""
        commands = self.router.get_available_commands()
        table = Table(title="Kernel Commands", expand=True, show_lines=True)
        table.add_column("Command", style="cyan", no_wrap=True)
        table.add_column("Description", style="magenta")

        for cmd, desc in commands.items():
            table.add_row(cmd, desc)

        self.console.print(table)
        self.console.print(
            Panel(
                Align.center(
                    "Tip: type [bold]<command> --help[/bold] or [bold]<command> -h[/bold] to see command usage\n"
                    "Tip: type [bold]help[/bold] or [bold]?[/bold] to return to shell help"
                ),
                border_style="cyan",
            )
        )
