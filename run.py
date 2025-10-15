#!/usr/bin/env python3
"""
Launcher script for kernel CLI application.
This script allows running the application from the root directory.
"""
import sys
import os
from pathlib import Path
from src.cli import main

# Get the directory where this script is located
script_dir = Path(__file__).parent

# Try to find and use the virtual environment
venv_python = script_dir / ".venv" / "bin" / "python"
if venv_python.exists() and sys.executable != str(venv_python):
    # Re-execute with the virtual environment's Python
    os.execv(str(venv_python), [str(venv_python)] + sys.argv)

# Add src to Python path so we can import kernel
src_path = script_dir / "src"
sys.path.insert(0, str(src_path))

if __name__ == "__main__":
    main()
