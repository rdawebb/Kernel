"""Database schema and query builders."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class TableSchema:
    """Schema definition for a database table."""

    name: str
    additional_columns: List[str] = field(default_factory=list)

    BASE_COLUMNS = [
        "uid",
        "subject",
        "sender",
        "recipient",
        "date",
        "time",
        "body",
        "attachments",
    ]

    COLUMN_DEFS = {
        "flagged": "flagged BOOLEAN DEFAULT 0",
        "deleted_at": "deleted_at TEXT",
        "sent_status": "sent_status TEXT DEFAULT 'pending'",
        "send_at": "send_at TEXT",
    }

    @property
    def all_columns(self) -> List[str]:
        """Return all columns including additional ones."""
        return self.BASE_COLUMNS + self.additional_columns

    def create_table_sql(self) -> str:
        """Generate SQL for creating the table."""
        base = """
            uid TEXT PRIMARY KEY,
            subject TEXT,
            sender TEXT,
            recipient TEXT,
            date TEXT,
            time TEXT,
            body TEXT,
            attachments TEXT DEFAULT ''
        """

        if self.additional_columns:
            additional = [self.COLUMN_DEFS[col] for col in self.additional_columns]
            base = base.rstrip() + ",\n" + ",\n".join(additional)

        return f"CREATE TABLE IF NOT EXISTS {self.name} ({base});"

    def create_indexes_sql(self) -> List[str]:
        """Generate SQL for creating indexes on table."""
        indexes = [
            f"CREATE INDEX IF NOT EXISTS idx_{self.name}_uid ON {self.name}(uid);",
            f"CREATE INDEX IF NOT EXISTS idx_{self.name}_date ON {self.name}(date DESC, time DESC);",
            f"CREATE INDEX IF NOT EXISTS idx_{self.name}_sender ON {self.name}(sender);",
        ]

        if "flagged" in self.additional_columns:
            indexes.append(
                f"CREATE INDEX IF NOT EXISTS idx_{self.name}_flagged ON {self.name}(flagged) WHERE flagged = 1;"
            )

        return indexes


SCHEMAS = {
    "inbox": TableSchema("inbox", ["flagged"]),
    "sent": TableSchema("sent", ["sent_status", "send_at"]),
    "drafts": TableSchema("drafts"),
    "trash": TableSchema("trash", ["deleted_at"]),
}

FIELD_MAPPING = {
    "sender": ["sender", "from"],
    "recipient": ["recipient", "to"],
}

## Query Building


class QueryBuilder:
    """Helper class to build SQL queries dynamically."""

    @staticmethod
    def build_select_columns(schema: TableSchema, include_body: bool = True) -> str:
        """Build a comma-separated string of columns for SELECT queries."""
        columns = [
            "uid",
            "subject",
            "sender as 'from'",
            "recipient as 'to'",
            "date",
            "time",
        ]

        if include_body:
            columns.append("body")

        columns.append("attachments")

        return ", ".join(columns)

    @staticmethod
    def build_where_clause(
        conditions: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, List[Any]]:
        """Build WHERE clause and parameters from conditions."""
        if not conditions:
            return "1=1", []

        clauses = []
        params = []

        for cond_field, value in conditions.items():
            if value is None:
                clauses.append(f"{cond_field} IS NULL")
            elif isinstance(value, (list, tuple)):
                placeholders = ", ".join("?" for _ in value)
                clauses.append(f"{cond_field} IN ({placeholders})")
                params.extend(value)
            else:
                clauses.append(f"{cond_field} = ?")
                params.append(value)

        return " AND ".join(clauses), params

    @staticmethod
    def build_placeholders(count: int) -> str:
        """Build a string of placeholders for prepared statements."""
        return ", ".join("?" for _ in range(count))
