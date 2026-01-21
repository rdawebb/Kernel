"""Centralised security utilities for path and filename validation"""

import re
from pathlib import Path
from typing import Optional, Union


class PathSecurity:
    """Security utilities for file paths and filenames"""

    DANGEROUS_PATTERN = re.compile(
        r"\.\.(?:/|\\|$)"  # Parent directory traversal (.. followed by separator or end)
        r"|^/"  # Absolute path (Unix)
        r"|^\\"  # Absolute path (Windows)
        r"|^[A-Za-z]:"  # Drive letters (Windows)
        r"|~"  # Home directory expansion
        r"|\$"  # Variable expansion
        r"|`"  # Command substitution
        r"|\|"  # Pipe
        r"|;"  # Command separator
        r"|&"  # Background execution
        r"|[<>]"  # Redirection
        r"|[*?]"  # Wildcards
        r'|["\']'  # Quotes
    )

    SAFE_FILENAME_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+$")

    WINDOWS_RESERVED = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }

    @classmethod
    def sanitise_filename(cls, filename: str, max_length: int = 255) -> str:
        """sanitise a filename to remove dangerous characters and patterns."""

        if not filename or not filename.strip():
            raise ValueError("Filename cannot be empty")

        if cls.DANGEROUS_PATTERN.search(filename):
            raise ValueError("Filename contains dangerous patterns")

        # Extract just the filename (no path components)
        filename = Path(filename).name

        # Replace unsafe characters with underscores
        sanitised = re.sub(r"[^\w.\-]", "_", filename)

        # Collapse multiple underscores/spaces into single underscore
        sanitised = re.sub(r"_+", "_", sanitised)

        # Replace whitespace with underscores
        sanitised = re.sub(r"\s+", "_", sanitised)

        # Remove leading/trailing underscores and dots
        sanitised = sanitised.strip("_.")

        # Truncate if too long (preserve extension)
        if len(sanitised) > max_length:
            stem = Path(sanitised).stem
            suffix = Path(sanitised).suffix
            max_stem_length = max_length - len(suffix)
            sanitised = stem[:max_stem_length] + suffix

        # Final validation
        if not sanitised or sanitised in (".", ".."):
            raise ValueError("sanitised filename is invalid")

        name_upper = sanitised.upper()
        name_base = name_upper.split(".")[0]
        if name_base in cls.WINDOWS_RESERVED:
            raise ValueError(f"Filename '{sanitised}' is reserved on Windows")

        return sanitised

    @classmethod
    def validate_filename(cls, filename: str) -> bool:
        """Validate a filename without modifying it."""

        try:
            if not filename or filename.strip() in ("", ".", ".."):
                return False

            if cls.DANGEROUS_PATTERN.search(filename):
                return False

            if "/" in filename or "\\" in filename:
                return False

            name_upper = filename.upper()
            name_base = name_upper.split(".")[0]
            if name_base in cls.WINDOWS_RESERVED:
                return False

            return True

        except Exception:
            return False

    @classmethod
    def validate_path(cls, path: Union[str, Path], base_dir: Union[str, Path]) -> bool:
        """Validate a file path to ensure it is within a specified base directory."""

        try:
            if isinstance(path, str):
                path = Path(path)
            if isinstance(base_dir, str):
                base_dir = Path(base_dir)

            resolved_path = path.resolve()
            resolved_base = base_dir.resolve()

            resolved_path.relative_to(resolved_base)
            return True

        except (ValueError, RuntimeError, OSError):
            return False

    @classmethod
    def secure_join(cls, base_dir: Union[str, Path], *parts: str) -> Optional[Path]:
        """Safely join path components and validate result."""

        try:
            if isinstance(base_dir, str):
                base_dir = Path(base_dir)

            sanitised_parts = [cls.sanitise_filename(part) for part in parts]

            result_path = base_dir / Path(*sanitised_parts)

            if cls.validate_path(result_path, base_dir):
                return result_path.resolve()

            return None

        except (ValueError, OSError):
            return None
