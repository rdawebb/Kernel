"""Interactive shell for Kernel CLI mode."""

from __future__ import annotations

import asyncio
import os
import shlex
import subprocess
import sys
from typing import Any, Dict, Optional

from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .cli_parser import setup_argument_parser
from .router import CommandRouter
from src.utils.config import ConfigManager
from src.utils.logging import get_logger
from src.daemon.client import get_daemon_client

logger = get_logger(__name__)

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.validation import Validator, ValidationError
    PKT_AVAILABLE = True

except ImportError:
    PKT_AVAILABLE = False
    logger.warning("prompt_toolkit not available; falling back to basic input() for shell.")

built_in_commands = {
                "commands": "list available commands",
                "<command> [args]": "execute a Kernel command with arguments",
                "help": "show this help message",
                "?": "show this help message",
                "exit": "exit the shell",
                "quit": "exit the shell",
                "reload": "reload configuration (and re-init router)",
                "clear": "clear the screen",
                "cls": "clear the screen",
                "shell <command>": "execute a shell command (e.g., shell ls -la)",
            }

def _namespace_to_dict(ns) -> Dict[str, Any]:
    """Convert argparse Namespace to dictionary."""
    return {k: getattr(ns, k) for k in vars(ns) if getattr(ns, k) is not None}

class CommandValidator(Validator):
    """Validator for shell commands."""
    def __init__(self, all_commands: set) -> None:
        super().__init__()
        self.all_commands = all_commands

    def validate(self, document) -> None:
        """Validate command input."""
        text = document.text.strip()
        if not text:
            raise ValidationError("Command cannot be empty", cursor_position=0)
        
        cmd = text.split()[0]
        if cmd not in self.all_commands:
            raise ValidationError(f"Unknown command: {cmd}", cursor_position=0)


class KernelShell:
    """Interactive REPL shell for Kernel CLI."""

    PROMPT = "Kernel > "

    def __init__(self, *, console: Optional[Console] = None) -> None:
        """Initialise shell."""
        self.console = console or Console()

        with self.console.status("Loading Kernel...", spinner="dots"):
            self.config_manager = ConfigManager()
            self.router = CommandRouter(console=self.console)
            self.kernel_commands = self.router.get_available_commands()
            self.parser = setup_argument_parser(exit_on_error=False)
            self.built_in_commands = built_in_commands
            self.all_commands = set(self.built_in_commands.keys()).union(
                self.kernel_commands.keys()
            )

        if PKT_AVAILABLE:
            history_file = os.path.expanduser("~/.kernel_cli_shell_history")
            self.session = PromptSession(
                history=FileHistory(history_file),
                auto_suggest=AutoSuggestFromHistory(),
                completer=WordCompleter(self.all_commands),
                validator=CommandValidator(self.all_commands),
                validate_while_typing=False
            )
        else:
            self.session = None

    def _print_help(self) -> None:
        """Print help table."""
        table = Table(title="Kernel Mail App Commands", expand=True, show_lines=True)
        table.add_column("Command", style="cyan", no_wrap=True)
        table.add_column("Description", style="magenta")
        for cmd, desc in self.built_in_commands.items():
            table.add_row(cmd, desc)

        self.console.print(table)
        self.console.print(Panel(
            Align.center("Tip: type [bold]commands[/bold] to see available commands"),
            border_style="cyan",
        ))

    def _print_commands(self) -> None:
        """Print available commands."""
        commands = self.kernel_commands
        table = Table(title="Kernel Commands", expand=True, show_lines=True)
        table.add_column("Command", style="cyan", no_wrap=True)
        table.add_column("Description", style="magenta")
        for cmd, desc in commands.items():
            table.add_row(cmd, desc)

        self.console.print(table)
        self.console.print(Panel(
            Align.center("Tip: type [bold]<command> --help[/bold] or [bold]<command> -h[/bold] to see command usage"),
            Align.center("Tip: type [bold]help[/bold] or [bold]?[/bold] to return to shell help"),
            border_style="cyan"
        ))

    async def _dispatch_command(self, command: str) -> bool:
        """Dispatch command via router.
        
        Returns:
            False if shell should exit, True otherwise
        """
        command = command.strip()
        if not command:
            return True
        
        if command.startswith("shell "):
            cmd = command[len("shell "):].strip()
            if cmd:
                try:
                    subprocess.run(shlex.split(cmd), shell=True, check=False)
                except Exception as e:
                    self.console.print(f"[red]Shell command failed: {e}[/red]")
            return True
        
        if command in {"help", "?"}:
            self._print_help()
            return True
        
        if command in {"exit", "quit"}:
            self.console.print(Panel(
                Align.center("Exiting Kernel Mail App - [bold green]Goodbye![/]"),
                border_style="dim cyan",
                padding=(1, 2)
            ))
            return False
        
        if command in {"clear", "cls"}:
            os.system('cls' if os.name == 'nt' else 'clear')
            return True
        
        if command == "reload":
            try:
                self.config_manager.reload()
                self.router = CommandRouter(console=self.console)
                self.console.print("[green]Configuration reloaded.[/green]")
                self.all_commands = set(self.router.get_available_commands().keys()).union(self.built_in_commands.keys())
                if self.session:
                    self.session.completer = WordCompleter(self.all_commands)
                    self.session.validator = CommandValidator(self.all_commands)

            except Exception as e:
                logger.error(f"Failed to reload configuration: {e}")
                self.console.print(f"[red]Failed to reload configuration: {e}[/red]")
            return True
        
        try:
            argv = shlex.split(command)
            ns = self.parser.parse_args(argv)
            args_dict = _namespace_to_dict(ns)
            cmd_name = ns.command if hasattr(ns, 'command') else argv[0] if argv else None
            if not cmd_name:
                self.console.print("[red]Could not determine command name.[/red]")
                return True
            
        except SystemExit:
            self.console.print("[red]Invalid command syntax. Use '<command> --help' for usage.[/red]")
            return True
        
        except Exception as e:
            logger.error(f"Error parsing command: {e}")
            self.console.print(f"[red]Error parsing command: {e}[/red]")
            return True
        
        try:
            await self.router.route(cmd_name, args_dict)

        except ValueError as e:
            logger.warning(f"Command error: {e}")
            self.console.print(f"[red]Error:[/red] {e}")

        except KeyboardInterrupt:
            logger.warning("Command cancelled by user")
            self.console.print("\n[yellow]Cancelled[/yellow]")

        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            self.console.print(f"[red]Command failed:[/red] {e}")
        
        return True

    async def run(self) -> int:
        """Run the interactive shell.
        
        Returns:
            Exit code (0 for success, >0 for errors)
        """
        if len(sys.argv) > 1:
            try:
                ns = self.parser.parse_args(sys.argv[1:])
                args_dict = _namespace_to_dict(ns)
                cmd_name = ns.command if hasattr(ns, 'command') else sys.argv[1]
                await self.router.route(cmd_name, args_dict)
                return 0
            
            except ValueError as e:
                logger.error(f"Command error: {e}")
                self.console.print(f"[red]Error:[/red] {e}")
                return 1
            
            except SystemExit as e:
                logger.error(f"Argument parsing error: {e}")
                self.console.print(f"[red]Error parsing command:[/red] {e}")
                return 2
            
            except Exception as e:
                logger.error(f"Command execution failed: {e}")
                self.console.print(f"[red]Command failed:[/red] {e}")
                return 1

        self.console.print(Panel(
            Align.center(
                Text.from_markup(
                    "[bold cyan]Welcome to the Kernel Mail App![/bold cyan]\n\n"
                    "Type [bold]help[/bold] or [bold]?[/bold] for a list of commands.\n"
                    "Type [bold]exit[/bold] or [bold]quit[/bold] to leave the shell.",
                    justify="center"
                )
            ),
            border_style="dim cyan",
            padding=(1, 2),
        ))
        
        while True:
            try:
                if self.session:
                    try:
                        command = await asyncio.wait_for(
                            self.session.prompt_async(self.PROMPT),
                            timeout=None
                        )
                    except asyncio.TimeoutError:
                        command = input(self.PROMPT)
                else:
                    command = input(self.PROMPT)
            
            except EOFError:
                self.console.print(Panel(
                    Align.center("\nExiting Kernel Mail App - [bold green]Goodbye![/]"),
                    border_style="dim cyan",
                    padding=(1, 2)
                ))
                break
            
            except KeyboardInterrupt:
                self.console.print("")
                continue
            
            should_continue = await self._dispatch_command(command)
            if not should_continue:
                break

        try:
            daemon_client = get_daemon_client()
            await daemon_client.stop_daemon()
        except Exception as e:
            logger.debug(f"Error stopping daemon: {e}")
        
        try:
            from src.core.database import get_database
            db = get_database(self.config_manager)
            await db.connection_manager.close()
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.debug(f"Error closing database: {e}")
        
        return 0
    
def main() -> int:
    """Main entry point for Kernel Mail App.
    
    Returns:
        Exit code (0 for success, >0 for errors)
    """
    shell = KernelShell()

    try:
        exit_code = asyncio.run(shell.run())
        
        try:
            os.system('stty sane 2>/dev/null')
        except Exception:
            pass
        
        try:
            os.system('pkill -f "email_daemon.py" 2>/dev/null')
        except Exception:
            pass
        
        import threading
        active_threads = threading.enumerate()
        non_daemon_threads = [t for t in active_threads if not t.daemon and t != threading.current_thread()]
        
        if non_daemon_threads:
            os._exit(exit_code if exit_code is not None else 0)
        else:
            sys.exit(exit_code if exit_code is not None else 0)
    
    except KeyboardInterrupt:
        logger.warning("Application interrupted by user")
        try:
            os.system('stty sane 2>/dev/null')
            os.system('pkill -f "email_daemon.py" 2>/dev/null')

        except Exception:
            pass
        os._exit(130)  # Standard SIGINT exit code
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        try:
            os.system('stty sane 2>/dev/null')
            os.system('pkill -f "email_daemon.py" 2>/dev/null')

        except Exception:
            pass

        os._exit(1)

    
if __name__ == "__main__":
    sys.exit(main())