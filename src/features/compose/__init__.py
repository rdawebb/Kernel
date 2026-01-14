"""Email composition feature module.

This module provides a complete email composition workflow with:
- Interactive input collection (prompt-toolkit)
- Rich display output
- Email validation
- Immediate sending or scheduling
- Draft saving

Public API:
    compose_email() - Main entry point for interactive composition
    CompositionWorkflow - Full workflow orchestration class (for testing/customization)

Example:
    >>> from src.features.compose import compose_email
    >>> success = await compose_email()

    >>> # Or with custom console:
    >>> from rich.console import Console
    >>> console = Console()
    >>> success = await compose_email(console=console)
"""

from .workflow import compose_email, CompositionWorkflow
from .input import CompositionInputManager

__all__ = [
    "compose_email",  # Main entry point
    "CompositionWorkflow",  # Full workflow class
    "CompositionDisplay",  # Display components
    "CompositionInputManager",  # Input collection
]
