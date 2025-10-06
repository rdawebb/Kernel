from rich.console import Console

console = Console()

def confirm_action(message):
    """Ask user for confirmation with y/N prompt"""
    response = console.input(f"{message} (y/N): ").strip().lower()
    return response in ['y', 'yes']
