"""Interactive shell for Kernel CLI mode."""

from __future__ import annotations

import asyncio
import os
import shlex
import sys
from time import perf_counter
from typing import Any, Dict, Optional

from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from src.core.database import EngineManager, get_config
from src.utils.config import ConfigManager
from src.utils.logging import get_logger
from src.utils.paths import SHELL_HISTORY_PATH, DATABASE_PATH

from .cli_parser import setup_argument_parser
from .lifecycle import LifecycleManager
from .router import CommandRouter
from .shell_builtins import ShellBuiltins

logger = get_logger(__name__)

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.history import FileHistory

    PKT_AVAILABLE = True

except ImportError:
    PKT_AVAILABLE = False
    logger.warning(
        "prompt_toolkit not available; falling back to basic input() for shell."
    )


def _namespace_to_dict(ns) -> Dict[str, Any]:
    """Convert argparse Namespace to dictionary."""
    return {k: getattr(ns, k) for k in vars(ns) if getattr(ns, k) is not None}


class KernelShell:
    """Interactive REPL shell for Kernel CLI."""

    PROMPT = "🍿 Kernel > "

    def __init__(self, *, console: Optional[Console] = None) -> None:
        """Initialise shell."""
        self.console = console or Console()

        with self.console.status("Loading Kernel...", spinner="dots"):
            self.config_manager = ConfigManager()
            self.router = CommandRouter(console=self.console)
            self.builtins = ShellBuiltins(self.router, console=self.console)
            self.parser = setup_argument_parser(exit_on_error=False)
            self.err_console = Console(stderr=True)
            self.timing_enabled = os.getenv("KERNEL_TIMING", "0") == "1"
            self.engine_manager = EngineManager(DATABASE_PATH, get_config())
            self.lifecycle = LifecycleManager(self.engine_manager)

        # Get all available commands (Kernel + built-ins)
        kernel_commands = self.router.get_available_commands()
        builtin_commands = self.builtins.get_builtin_commands()
        self.all_commands = set(kernel_commands.keys()).union(builtin_commands.keys())

        if PKT_AVAILABLE:
            history_file = SHELL_HISTORY_PATH
            self.session = PromptSession(
                history=FileHistory(history_file),
                auto_suggest=AutoSuggestFromHistory(),
                completer=WordCompleter(list(self.all_commands)),
            )
        else:
            self.session = None

    async def _dispatch_command(self, command: str) -> bool:
        """Dispatch command via router or handle built-in.

        Returns:
            False if shell should exit, True otherwise
        """
        command = command.strip()
        if not command:
            return True

        # Check if it's a shell built-in
        if self.builtins.is_builtin(command):
            should_continue, was_handled = await self.builtins.handle_builtin(command)
            return should_continue

        # Parse and route Kernel command
        t0 = perf_counter()

        try:
            argv = shlex.split(command)
            ns = self.parser.parse_args(argv)
            args_dict = _namespace_to_dict(ns)
            cmd_name = (
                ns.command if hasattr(ns, "command") else argv[0] if argv else None
            )
            if not cmd_name:
                self.console.print("[red]Could not determine command name.[/red]")
                return True

        except SystemExit:
            self.console.print(
                "[red]Invalid command syntax. Use '<command> --help' for usage.[/red]"
            )
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

        t_end = perf_counter()

        if self.timing_enabled:
            elapsed_ms = (t_end - t0) * 1000
            self.err_console.print(
                f"[dim]Command executed in {elapsed_ms:.1f} ms.[/dim]"
            )

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
                cmd_name = ns.command if hasattr(ns, "command") else sys.argv[1]
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

        self.console.print(
            Panel(
                Align.center(
                    Text.from_markup(
                        "[bold cyan]Welcome to the Kernel Mail App![/bold cyan]\n\n"
                        "Type [bold]help[/bold] or [bold]?[/bold] for a list of commands.\n"
                        "Type [bold]exit[/bold] or [bold]quit[/bold] to leave the shell.",
                        justify="center",
                    )
                ),
                border_style="dim cyan",
                padding=(1, 2),
            )
        )

        while True:
            try:
                if self.session:
                    try:
                        command = await asyncio.wait_for(
                            self.session.prompt_async(self.PROMPT), timeout=None
                        )
                    except asyncio.TimeoutError:
                        command = input(self.PROMPT)
                else:
                    command = input(self.PROMPT)

            except EOFError:
                self.console.print(
                    Panel(
                        Align.center(
                            "\nExiting Kernel Mail App - [bold green]Goodbye![/]"
                        ),
                        border_style="dim cyan",
                        padding=(1, 2),
                    )
                )
                break

            except KeyboardInterrupt:
                self.console.print("")
                continue

            should_continue = await self._dispatch_command(command)
            if not should_continue:
                break

        # Cleanup on exit
        await self.lifecycle.cleanup()
        return 0


def main() -> int:
    """Main entry point for Kernel Mail App.

    Returns:
        Exit code (0 for success, >0 for errors)
    """
    shell = KernelShell()

    try:
        exit_code = asyncio.run(shell.run())
        shell.lifecycle.force_exit(exit_code if exit_code is not None else 0)
        return exit_code if exit_code is not None else 0

    except KeyboardInterrupt:
        return shell.lifecycle.handle_interrupt()

    except Exception as e:
        return shell.lifecycle.handle_error(e)


if __name__ == "__main__":
    sys.exit(main())
