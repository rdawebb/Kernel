"""Centralized path definitions for the Kernel application.

This module provides a single source of truth for all application paths,
preventing duplication and making path configuration easier to maintain.
"""

from pathlib import Path

# Base application directory
KERNEL_DIR = Path.home() / ".kernel"

# Subdirectories
DATA_DIR = KERNEL_DIR / "data"
LOGS_DIR = KERNEL_DIR / "logs"
SECRETS_DIR = KERNEL_DIR / "secrets"
ATTACHMENTS_DIR = KERNEL_DIR / "attachments"
EXPORTS_DIR = KERNEL_DIR / "exports"
BACKUPS_DIR = DATA_DIR / "backups"

# Specific files
DATABASE_PATH = KERNEL_DIR / "kernel.db"
DAEMON_SOCKET_PATH = KERNEL_DIR / "daemon.sock"
DAEMON_TOKEN_PATH = KERNEL_DIR / "daemon.token"
DAEMON_PID_PATH = KERNEL_DIR / "daemon.pid"
MASTER_KEY_PATH = SECRETS_DIR / ".master.key"
CREDENTIALS_PATH = SECRETS_DIR / "credentials.enc"
BACKUP_DB_PATH = BACKUPS_DIR / "kernel_backup.db"
SHELL_HISTORY_PATH = KERNEL_DIR / "shell_history.txt"
