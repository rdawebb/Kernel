"""Script for running the Kernel shell application"""

import shutil
import subprocess
import sys
from pathlib import Path


def clear_python_cache() -> None:
    """Clear Python cache files (__pycache__ and .pyc files)."""
    src_path = Path.cwd() / "src"
    if src_path.exists():
        # Remove __pycache__ directories
        for cache_dir in src_path.rglob("__pycache__"):
            shutil.rmtree(cache_dir, ignore_errors=True)

        # Remove .pyc files
        for pyc_file in src_path.rglob("*.pyc"):
            pyc_file.unlink(missing_ok=True)


def get_venv_path() -> Path:
    """Get the virtual environment path"""
    return Path.cwd() / ".venv"


def venv_exists() -> bool:
    """Check if virtual environment exists"""
    venv_path = get_venv_path()
    return venv_path.exists() and (venv_path / "bin" / "python").exists()


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

    venv_path = get_venv_path()
    venv_python = venv_path / "bin" / "python"

    result = subprocess.run([str(venv_python), "-m", "src.cli.shell"], check=False)
    sys.exit(result.returncode)


def main() -> None:
    """Main entry point."""
    clear_python_cache()

    if not venv_exists():
        create_venv()

    install_dependencies()

    run_shell()


if __name__ == "__main__":
    main()
