"""Base command class for CLI commands."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

from src.utils.console import get_console
from src.utils.error_handling import KernelError, ValidationError, safe_execute
from src.utils.log_manager import async_log_call, get_logger

logger = get_logger(__name__)


@dataclass
class EmailFilters:
    """Structure for email filtering criteria."""

    flagged: Optional[bool] = None
    unread: Optional[bool] = None
    with_attachments: Optional[bool] = False

    @classmethod
    def from_args(cls, args):
        """Create filters from command-line arguments."""

        flagged = None
        if getattr(args, "flagged", False):
            flagged = True
        elif getattr(args, "unflagged", False):
            flagged = False

        unread = None
        if getattr(args, "unread", False):
            unread = True
        elif getattr(args, "read", False):
            unread = False

        with_attachments = getattr(args, "with_attachments", False)

        return cls(
            flagged=flagged,
            unread=unread,
            with_attachments=with_attachments
        )
    
    def has_filters(self) -> bool:
        """Check if any filters are active."""
        
        return (
            self.flagged is not None or
            self.unread is not None or
            self.with_attachments
        )
    
    def to_dict(self) -> dict:
        """Convert filters to dictionary for querying."""
        
        result = {}
        if self.flagged is not None:
            result["flagged"] = self.flagged
        if self.unread is not None:
            result["unread"] = self.unread
        if self.with_attachments:
            result["with_attachments"] = True

        return result


@dataclass
class CommandResult:
    """Standard command result structure."""

    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
        }
        

class BaseCommandHandler(ABC):
    """Base class for all command handlers."""

    def __init__(self, config_manager=None):
        """Initialize command handler with optional config manager."""

        self.config_manager = config_manager
        self.console = get_console()
        self.logger = logger

    
    ## Abstract Methods

    @abstractmethod
    @async_log_call
    async def execute_cli(self, args, config_manager) -> None:
        """Execute the command in CLI mode (direct user interaction)."""
        pass

    @abstractmethod
    @async_log_call
    async def execute_daemon(self, daemon, args: Dict[str, Any]) -> CommandResult:
        """Execute the command in daemon mode (background processing)."""
        pass
    

    ## Validation Methods

    def validate_args(self, args: Dict[str, Any], *required_keys: str, 
                      allow_empty_strings: bool = False) -> None:
        """Validate that required arguments are present."""

        missing = []
        for key in required_keys:
            value = args.get(key)
            if value is None:
                missing.append(key)
            elif not allow_empty_strings and isinstance(value, str) and not value.strip():
                missing.append(key)

        if missing:
            raise ValidationError(
                f"Missing required arguments: {', '.join(missing)}",
                details={"missing_args": missing}
            )
        
    def validate_table(self, table: str) -> None:
        """Validate that the table name is allowed."""

        from src.core.database import SCHEMAS

        if table not in SCHEMAS:
            self.logger.warning(f"Invalid table validation: {table}", extra={"valid_tables": list(SCHEMAS.keys())})
            raise ValidationError(
                f"Invalid table name: {table}",
                details={"table": table, "valid_tables": list(SCHEMAS.keys())}
            )

    async def validate_email_exists(self, db: Any, table: str, email_id: str, 
                             include_body: bool = True) -> Dict[str, Any]:
        """Validate that an email with the given ID exists in the specified table."""

        if not db.email_exists(table, email_id):
            raise ValidationError(
                f"Email with ID {email_id} not found in {table}",
                details={"table": table, "email_id": email_id}
            )

        email = await db.get_email(table, email_id, include_body=include_body)
        if not email:
            raise ValidationError(
                f"Email with ID {email_id} could not be retrieved from {table}",
                details={"table": table, "email_id": email_id}
            )
        
        return email
    
    
    ## Common Result Methods

    def success_result(self, data: Any = None, **metadata) -> CommandResult:
        """Create a success CommandResult."""
        
        return CommandResult(success=True, data=data, metadata=metadata)
    
    def error_result(self, error: str, **metadata) -> CommandResult:
        """Create an error CommandResult."""
        
        return CommandResult(success=False, error=error, metadata=metadata)
    

    ## Daemon Rendering Helper

    def render_for_daemon(self, render_func: Callable, *args, **kwargs) -> str:
        """Render Rich output to a string for daemon use."""

        from io import StringIO
        from rich.console import Console

        buffer = StringIO()
        console = Console(
            file=buffer,
            force_terminal=True,
            width=120,
            legacy_windows=False,
            record=True
        )

        render_func(*args, console_obj=console, **kwargs)
        rendered_text = console.export_text(clear=True)
        
        self.logger.debug(f"Rendered output for daemon: {len(rendered_text)} characters")
        return rendered_text
    

    ## Error Handling Wrappers

    async def safe_execute_cli(self, args, config_manager) -> None:
        """Execute a CLI command with error handling."""

        from src.utils.console import print_error

        self.logger.debug(f"Executing CLI command: {self.__class__.__name__}")
        
        result = await safe_execute(
            self.execute_cli,
            args,
            config_manager,
            default=None,
            context=f"CLI command: {self.__class__.__name__}"
        )

        if result is None:
            print_error(f"Failed to execute CLI command: {self.__class__.__name__}")
            return
        
    async def safe_execute_daemon(self, daemon, args: Dict[str, Any]) -> CommandResult:
        """Execute a daemon command with error handling."""

        try:
            return await self.execute_daemon(daemon, args)
        
        except KernelError as e:
            self.logger.error(f"Command error: {e.message}", extra=e.details)
            return self.error_result(e.message, **e.details)
        
        except Exception as e:
            self.logger.exception(f"Unexpected error: {e}")
            return self.error_result(f"An unexpected error occurred: {str(e)}")
        

## Helper Function for Registration

def create_command_handlers(handler_class: type) -> Tuple:
    """Create CLI and daemon command handlers from a command handler class."""

    handler = handler_class(config_manager=None)

    async def cli_wrapper(args, config_manager):
        await handler.safe_execute_cli(args, config_manager)

    async def daemon_wrapper(daemon, args: Dict[str, Any]) -> Dict[str, Any]:
        result = await handler.safe_execute_daemon(daemon, args)
        return result.to_dict()
    
    return cli_wrapper, daemon_wrapper
