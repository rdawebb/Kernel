#!/usr/bin/env python3
"""
Backup and restore utility for Kernel email database.

Usage:
    # Create backup (compressed by default)
    python scripts/backup_db.py backup

    # Create uncompressed backup
    python scripts/backup_db.py backup --no-compress

    # Export to CSV
    python scripts/backup_db.py export --output-dir ./exports

    # Restore from backup
    python scripts/backup_db.py restore --backup-file ./backups/kernel_backup_20240115_120000.db.gz

    # Cleanup old backups
    python scripts/backup_db.py cleanup --keep 5

    # Verify backup
    python scripts/backup_db.py verify --backup-file ./backups/kernel_backup_20240115_120000.db
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
)

from src.core.database import (
    EngineManager,
    EmailRepository,
    BackupService,
)
from src.utils.paths import DATABASE_PATH


console = Console()


async def backup_database(
    db_path: Path,
    output_path: Optional[Path] = None,
    compress: bool = True,
) -> int:
    """Create database backup."""
    console.print(f"[cyan]Creating backup of {db_path}...[/cyan]")

    engine_mgr = EngineManager(db_path)
    repo = EmailRepository(engine_mgr)
    service = BackupService(db_path, repo)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            "Backing up database...",
            total=100,
        )

        def update_progress(current, total):
            progress.update(task, completed=int(current / total * 100))

        result = await service.create_backup(
            backup_path=output_path,
            compress=compress,
            progress=update_progress,
        )

    await engine_mgr.close()

    if result.success:
        console.print("[green]✓ Backup created successfully![/green]")
        console.print(f"  Location: {result.backup_path}")
        console.print(f"  Size: {result.size_mb} MB")
        console.print(f"  Compressed: {'Yes' if result.compressed else 'No'}")
        console.print(f"  Duration: {result.duration_seconds:.2f}s")
        return 0
    else:
        console.print(f"[red]✗ Backup failed: {result.error}[/red]")
        return 1


async def export_to_csv(
    db_path: Path,
    output_dir: Path,
    folders: Optional[list] = None,
) -> int:
    """Export database to CSV files."""
    console.print(f"[cyan]Exporting {db_path} to CSV...[/cyan]")

    engine_mgr = EngineManager(db_path)
    repo = EmailRepository(engine_mgr)
    service = BackupService(db_path, repo)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Exporting...", total=None)

        def update_progress(folder, current, total):
            progress.update(
                task,
                description=f"Exporting {folder}: {current}/{total}",
            )

        result = await service.export_to_csv(
            export_dir=output_dir,
            folders=folders,
            progress=update_progress,
        )

    await engine_mgr.close()

    if result.success:
        console.print("[green]✓ Export completed successfully![/green]")
        console.print(f"  Files: {len(result.exported_files)}")
        console.print(f"  Total emails: {result.total_emails}")
        console.print(f"  Duration: {result.duration_seconds:.2f}s")
        for file in result.exported_files:
            console.print(f"    - {file}")
        return 0
    else:
        console.print("[yellow]⚠ Export completed with errors:[/yellow]")
        for folder, error in result.errors:
            console.print(f"  - {folder}: {error}")
        return 1


async def restore_database(
    backup_path: Path,
    target_path: Optional[Path] = None,
) -> int:
    """Restore database from backup."""
    console.print(f"[cyan]Restoring from {backup_path}...[/cyan]")

    target = target_path or DATABASE_PATH

    # Confirm if target exists
    if target.exists():
        if (
            not console.input(
                f"[yellow]Target database exists: {target}\n"
                "A pre-restore backup will be created. Continue? (y/n): [/yellow]"
            )
            .lower()
            .startswith("y")
        ):
            console.print("[yellow]Restore cancelled[/yellow]")
            return 0

    engine_mgr = EngineManager(target)
    repo = EmailRepository(engine_mgr)
    service = BackupService(target, repo)

    with console.status("[cyan]Restoring database..."):
        success = await service.restore_from_backup(
            backup_path=backup_path,
            target_path=target,
        )

    await engine_mgr.close()

    if success:
        console.print("[green]✓ Database restored successfully![/green]")
        console.print(f"  Target: {target}")
        return 0
    else:
        console.print("[red]✗ Restore failed[/red]")
        return 1


async def verify_backup(backup_path: Path) -> int:
    """Verify backup integrity."""
    console.print(f"[cyan]Verifying {backup_path}...[/cyan]")

    # Create temporary service just for verification
    temp_db = Path("/tmp/kernel_verify.db")
    engine_mgr = EngineManager(temp_db)
    repo = EmailRepository(engine_mgr)
    service = BackupService(temp_db, repo)

    with console.status("[cyan]Verifying backup..."):
        is_valid = await service.verify_backup(backup_path)

    await engine_mgr.close()

    if is_valid:
        console.print("[green]✓ Backup is valid[/green]")
        return 0
    else:
        console.print("[red]✗ Backup verification failed[/red]")
        return 1


async def cleanup_backups(
    backup_dir: Path,
    keep_count: int,
    max_age_days: Optional[int] = None,
) -> int:
    """Clean up old backups."""
    console.print("[cyan]Cleaning up backups in {backup_dir}...[/cyan]")

    # Create temporary service for cleanup
    temp_db = Path("/tmp/kernel_cleanup.db")
    engine_mgr = EngineManager(temp_db)
    repo = EmailRepository(engine_mgr)
    service = BackupService(temp_db, repo)

    deleted = await service.cleanup_old_backups(
        backup_dir=backup_dir,
        keep_count=keep_count,
        max_age_days=max_age_days,
    )

    await engine_mgr.close()

    console.print(f"[green]✓ Deleted {deleted} old backups[/green]")
    return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Backup and restore utility for Kernel email database",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Backup command
    backup_parser = subparsers.add_parser("backup", help="Create database backup")
    backup_parser.add_argument(
        "--db-path",
        type=Path,
        default=DATABASE_PATH,
        help="Database file path",
    )
    backup_parser.add_argument(
        "--output",
        type=Path,
        help="Backup output path (auto-generated if not provided)",
    )
    backup_parser.add_argument(
        "--no-compress",
        action="store_true",
        help="Disable compression",
    )

    # Export command
    export_parser = subparsers.add_parser("export", help="Export to CSV")
    export_parser.add_argument(
        "--db-path",
        type=Path,
        default=DATABASE_PATH,
        help="Database file path",
    )
    export_parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Output directory for CSV files",
    )

    # Restore command
    restore_parser = subparsers.add_parser("restore", help="Restore from backup")
    restore_parser.add_argument(
        "--backup-file",
        type=Path,
        required=True,
        help="Backup file to restore from",
    )
    restore_parser.add_argument(
        "--target",
        type=Path,
        help="Target database path (uses original if not provided)",
    )

    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify backup integrity")
    verify_parser.add_argument(
        "--backup-file",
        type=Path,
        required=True,
        help="Backup file to verify",
    )

    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Clean up old backups")
    cleanup_parser.add_argument(
        "--backup-dir",
        type=Path,
        default=DATABASE_PATH.parent / "backups",
        help="Backup directory",
    )
    cleanup_parser.add_argument(
        "--keep",
        type=int,
        default=5,
        help="Number of recent backups to keep",
    )
    cleanup_parser.add_argument(
        "--max-age-days",
        type=int,
        help="Delete backups older than this many days",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Execute command
    try:
        if args.command == "backup":
            return asyncio.run(
                backup_database(
                    args.db_path,
                    args.output,
                    not args.no_compress,
                )
            )

        elif args.command == "export":
            return asyncio.run(
                export_to_csv(
                    args.db_path,
                    args.output_dir,
                )
            )

        elif args.command == "restore":
            return asyncio.run(
                restore_database(
                    args.backup_file,
                    args.target,
                )
            )

        elif args.command == "verify":
            return asyncio.run(verify_backup(args.backup_file))

        elif args.command == "cleanup":
            return asyncio.run(
                cleanup_backups(
                    args.backup_dir,
                    args.keep,
                    args.max_age_days,
                )
            )

    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled[/yellow]")
        return 130
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
