"""Script for running the Kernel shell application"""

import subprocess
import sys
from pathlib import Path


def get_venv_path() -> Path:
    """Get the virtual environment path"""
    return Path.cwd() / ".venv"


def venv_exists() -> bool:
    """Check if virtual environment exists"""
    venv_path = get_venv_path()
    if venv_path.exists() and (venv_path / "bin" / "python").exists():
        subprocess.run(["source", str(venv_path / "bin" / "activate")], shell=True)
        return True
    return False


def create_venv() -> None:
    """Create a new virtual environment using uv"""
    print("Creating virtual environment with uv...")
    result = subprocess.run(["uv", "venv", ".venv"], check=False)
    if result.returncode != 0:
        print("Failed to create virtual environment", file=sys.stderr)
        sys.exit(1)
    print("Virtual environment created successfully")


def install_dependencies() -> None:
    """Install dependencies using uv"""
    print("Installing dependencies with uv...")
    result = subprocess.run(["uv", "sync", "--all-extras"], check=False)
    if result.returncode != 0:
        print("Failed to install dependencies", file=sys.stderr)
        sys.exit(1)
    print("Dependencies installed successfully")


def run_shell() -> None:
    """Run the shell application"""
    print("Starting Kernel shell...")

    result = subprocess.run(["python", "-m", "src.cli.shell"], check=False)
    sys.exit(result.returncode)


def main() -> None:
    """Main entry point."""
    if not venv_exists():
        create_venv()

    install_dependencies()

    run_shell()


if __name__ == "__main__":
    main()
