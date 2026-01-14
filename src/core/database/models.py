"""SQLAlchemy table definitions with proper types and constraints."""

from sqlalchemy import (
    Boolean,
    Column,
    Index,
    Integer,
    String,
    Table,
    Text,
    CheckConstraint,
)

from src.core.database.base import metadata


def _email_columns(include_flagged: bool = False, include_status: bool = False):
    """Generate common email columns.

    Args:
        include_flagged: Whether to include flagged status column
        include_status: Whether to include sent status columns

    Returns:
        List of SQLAlchemy Column objects
    """
    columns = [
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("uid", String(255), unique=True, nullable=False, index=True),
        Column("subject", String(1000), nullable=False, default="", server_default=""),
        Column("sender", String(500), nullable=False, index=True),
        Column("recipient", String(500), nullable=False),
        Column("date", String(10), nullable=False),  # YYYY-MM-DD (ISO8601)
        Column("time", String(8), nullable=False),  # HH:MM:SS (24-hour)
        Column("body", Text, nullable=True),
        Column("attachments", Text, nullable=False, default="", server_default=""),
        Column("is_read", Boolean, nullable=False, default=False, server_default="0"),
    ]

    if include_flagged:
        columns.append(
            Column(
                "flagged", Boolean, nullable=False, default=False, server_default="0"
            )
        )

    if include_status:
        columns.extend(
            [
                Column(
                    "sent_status",
                    String(20),
                    nullable=False,
                    default="pending",
                    server_default="pending",
                ),
                Column("send_at", String(26), nullable=True),  # ISO8601 with timezone
            ]
        )
        columns.append(
            CheckConstraint(
                "sent_status IN ('pending', 'sent', 'failed')",
                name="ck_sent_status_values",
            )
        )

    return columns


inbox = Table(
    "inbox",
    metadata,
    *_email_columns(include_flagged=True),
    Index("ix_inbox_date_time", "date", "time", sqlite_where=None),
    Index("ix_inbox_flagged", "flagged", sqlite_where=Column("flagged") == True),
)

sent = Table(
    "sent",
    metadata,
    *_email_columns(include_status=True),
    Index("ix_sent_date_time", "date", "time"),
    Index("ix_sent_status", "sent_status"),
)

drafts = Table(
    "drafts",
    metadata,
    *_email_columns(),
    Index("ix_drafts_date_time", "date", "time"),
)

trash = Table(
    "trash",
    metadata,
    *_email_columns(include_flagged=True),
    Column("deleted_at", String(26), nullable=False),  # ISO8601 deletion timestamp
    Index("ix_trash_date_time", "date", "time"),
    Index("ix_trash_deleted_at", "deleted_at"),
)

# Export all tables
ALL_TABLES = {
    "inbox": inbox,
    "sent": sent,
    "drafts": drafts,
    "trash": trash,
}


def get_table(name: str) -> Table:
    """Get table by name with validation.

    Args:
        name: Table name (inbox, sent, drafts, trash)

    Returns:
        SQLAlchemy Table object

    Raises:
        ValueError: If table name is invalid
    """
    if name not in ALL_TABLES:
        raise ValueError(
            f"Invalid table name: {name}. Must be one of: {', '.join(ALL_TABLES.keys())}"
        )

    return ALL_TABLES[name]
