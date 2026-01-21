"""Data migration script for existing Kernel databases."""

import argparse
import asyncio
import shutil
import sys
from datetime import datetime
from pathlib import Path

import aiosqlite


async def backup_database(db_path: Path) -> Path:
    """Create backup of database before migration."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"{db_path.stem}_backup_{timestamp}.db"

    await asyncio.to_thread(lambda: shutil.copy2(db_path, backup_path))
    print(f"✓ Backup created: {backup_path}")

    return backup_path


async def check_schema_version(conn: aiosqlite.Connection) -> str:
    """Check if database is already migrated."""
    try:
        # Check if new schema exists (has id column)
        cursor = await conn.execute("PRAGMA table_info(inbox)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]

        if "id" in column_names:
            return "new"
        else:
            return "old"
    except Exception:
        return "unknown"


async def migrate_table(
    conn: aiosqlite.Connection,
    table_name: str,
) -> tuple[int, int]:
    """Migrate a single table to new schema.

    Args:
        conn (aiosqlite.Connection): Database connection.
        table_name (str): Name of the table to migrate.

    Returns:
        Tuple of (total_rows, migrated_rows)
    """
    print(f"\n  Migrating table: {table_name}")

    # Check if old table exists
    cursor = await conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
    )
    if not await cursor.fetchone():
        print(f"  ⚠ Table {table_name} not found, skipping")
        return 0, 0

    # Count existing rows
    cursor = await conn.execute(f"SELECT COUNT(*) FROM {table_name}")
    row = await cursor.fetchone()
    total = row[0] if row is not None else 0

    if total == 0:
        print(f"  ℹ Table {table_name} is empty, skipping")
        return 0, 0

    # Rename old table
    old_table = f"{table_name}_old"
    await conn.execute(f"ALTER TABLE {table_name} RENAME TO {old_table}")
    print(f"  ✓ Renamed {table_name} → {old_table}")

    # Note: This assumes Alembic migration has already been run

    # Determine which columns to copy based on table
    base_columns = "uid, subject, sender, recipient, date, time, body, attachments"

    if table_name == "inbox":
        # Inbox has flagged column
        insert_sql = f"""
            INSERT INTO {table_name} 
            ({base_columns}, is_read, flagged)
            SELECT {base_columns}, 
                   COALESCE(is_read, 0),
                   COALESCE(flagged, 0)
            FROM {old_table}
        """
    elif table_name == "sent":
        # Sent has sent_status and send_at
        insert_sql = f"""
            INSERT INTO {table_name}
            ({base_columns}, is_read, sent_status, send_at)
            SELECT {base_columns},
                   COALESCE(is_read, 0),
                   COALESCE(sent_status, 'sent'),
                   send_at
            FROM {old_table}
        """
    elif table_name == "trash":
        # Trash has flagged and deleted_at
        insert_sql = f"""
            INSERT INTO {table_name}
            ({base_columns}, is_read, flagged, deleted_at)
            SELECT {base_columns},
                   COALESCE(is_read, 0),
                   COALESCE(flagged, 0),
                   COALESCE(deleted_at, datetime('now'))
            FROM {old_table}
        """
    else:
        # Drafts - no extra columns
        insert_sql = f"""
            INSERT INTO {table_name}
            ({base_columns}, is_read)
            SELECT {base_columns},
                   COALESCE(is_read, 0)
            FROM {old_table}
        """

    try:
        await conn.execute(insert_sql)
        await conn.commit()

        # Count migrated rows
        cursor = await conn.execute(f"SELECT COUNT(*) FROM {table_name}")
        migrated_row = await cursor.fetchone()
        migrated = migrated_row[0] if migrated_row is not None else 0

        print(f"  ✓ Migrated {migrated}/{total} rows")

        # Keep old table for safety (user can drop manually later)
        print(
            f"  ℹ Old table kept as {old_table} (drop manually if migration successful)"
        )

        return total, migrated

    except Exception as e:
        print(f"  ✗ Migration failed: {e}")
        await conn.rollback()
        # Restore old table
        await conn.execute(f"DROP TABLE IF EXISTS {table_name}")
        await conn.execute(f"ALTER TABLE {old_table} RENAME TO {table_name}")
        await conn.commit()
        print("  ✓ Rolled back to original table")
        return total, 0


async def migrate_database(db_path: Path, create_backup: bool = True) -> bool:
    """Migrate database to new schema.

    Args:
        db_path: Path to database file
        create_backup: Whether to create backup before migration

    Returns:
        True if successful, False otherwise
    """
    print("=" * 70)
    print("Kernel Email Client - Database Migration")
    print("=" * 70)
    print()

    if not db_path.exists():
        print(f"✗ Database not found: {db_path}")
        return False

    # Create backup if requested
    if create_backup:
        print("Creating backup...")
        await backup_database(db_path)
        print()

    # Open database
    async with aiosqlite.connect(db_path) as conn:
        # Check current schema
        print("Checking schema version...")
        schema_version = await check_schema_version(conn)
        print(f"  Schema version: {schema_version}")
        print()

        if schema_version == "new":
            print("✓ Database already migrated to new schema")
            return True
        elif schema_version == "unknown":
            print("✗ Cannot determine schema version")
            return False

        # Run Alembic migration first to create new schema
        print("Note: Run 'alembic upgrade head' first to create new schema")
        print("      Then run this script to migrate data")
        print()

        # Migrate each table
        print("Migrating tables...")
        tables = ["inbox", "sent", "drafts", "trash"]

        total_rows = 0
        migrated_rows = 0

        for table in tables:
            t, m = await migrate_table(conn, table)
            total_rows += t
            migrated_rows += m

        print()
        print("=" * 70)
        print("Migration Summary")
        print("=" * 70)
        print(f"  Total rows: {total_rows}")
        print(f"  Migrated: {migrated_rows}")
        print(
            f"  Success rate: {migrated_rows / total_rows * 100:.1f}%"
            if total_rows > 0
            else "N/A"
        )
        print()

        if migrated_rows == total_rows:
            print("✓ Migration completed successfully")
            print()
            print("Next steps:")
            print("  1. Test application with new database")
            print("  2. If everything works, drop old tables:")
            print("     DROP TABLE inbox_old;")
            print("     DROP TABLE sent_old;")
            print("     DROP TABLE drafts_old;")
            print("     DROP TABLE trash_old;")
            return True
        else:
            print("⚠ Migration completed with errors")
            print("  Review logs and check data integrity")
            return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate Kernel database to new schema",
    )

    parser.add_argument(
        "--db-path",
        type=Path,
        help="Path to database file (default: uses config)",
    )

    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backup creation (not recommended)",
    )

    args = parser.parse_args()

    # Get database path
    if args.db_path:
        db_path = args.db_path
    else:
        # Use default from config
        try:
            from src.utils.paths import DATABASE_PATH

            db_path = DATABASE_PATH
        except ImportError:
            print("✗ Could not determine database path")
            print("  Use --db-path to specify manually")
            return 1

    # Run migration
    success = asyncio.run(migrate_database(db_path, create_backup=not args.no_backup))

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
