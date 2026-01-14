"""Query builders using SQLAlchemy Core for type-safe queries."""

from typing import Any, Dict, List, Optional, Set

from sqlalchemy import Select, and_, delete, insert, or_, select, update, Insert
from sqlalchemy.sql import ColumnElement

from src.core.database.models import get_table
from src.core.models.email import FolderName


class QueryBuilder:
    """Type-safe query builder using SQLAlchemy Core. """

    @staticmethod
    def select_emails(
        folder: FolderName,
        include_body: bool = True,
        conditions: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order_by_date_desc: bool = True,
    ) -> Select:
        """Build SELECT query for emails.

        Args:
            folder: Target folder
            include_body: Whether to include body text
            conditions: WHERE conditions as dict
            limit: Maximum rows to return
            offset: Number of rows to skip
            order_by_date_desc: Order by date DESC (newest first)

        Returns:
            SQLAlchemy Select statement
        """
        table = get_table(folder.value)

        # Select columns
        if include_body:
            columns = [
                table.c.id,
                table.c.uid,
                table.c.subject,
                table.c.sender.label("from"),
                table.c.recipient.label("to"),
                table.c.date,
                table.c.time,
                table.c.body,
                table.c.attachments,
                table.c.is_read,
            ]
        else:
            columns = [
                table.c.id,
                table.c.uid,
                table.c.subject,
                table.c.sender.label("from"),
                table.c.recipient.label("to"),
                table.c.date,
                table.c.time,
                table.c.attachments,
                table.c.is_read,
            ]

        # Add folder-specific columns
        if folder == FolderName.INBOX:
            columns.append(table.c.flagged)
        elif folder == FolderName.SENT:
            columns.extend([table.c.sent_status, table.c.send_at])
        elif folder == FolderName.TRASH:
            columns.extend([table.c.flagged, table.c.deleted_at])

        query = select(*columns)

        # WHERE clause
        if conditions:
            where_clause = QueryBuilder._build_where(table, conditions)
            query = query.where(where_clause)

        # ORDER BY
        if order_by_date_desc:
            query = query.order_by(table.c.date.desc(), table.c.time.desc())

        # LIMIT/OFFSET
        if limit is not None:
            query = query.limit(limit)
        if offset is not None:
            query = query.offset(offset)

        return query

    @staticmethod
    def insert_email(folder: FolderName, values: Dict[str, Any]) -> Insert:
        """Build INSERT OR REPLACE query for email.

        Args:
            folder: Target folder
            values: Column values as dict

        Returns:
            SQLAlchemy Insert statement
        """
        table = get_table(folder.value)
        
        query = insert(table).values(**values)
        query = query.on_conflict_do_update(
            constraint=table.primary_key,
            set_=values
        )
        
        return query

    @staticmethod
    def update_email(
        folder: FolderName,
        uid: str,
        values: Dict[str, Any],
    ):
        """Build UPDATE query for email.

        Args:
            folder: Target folder
            uid: Email UID
            values: Columns to update

        Returns:
            SQLAlchemy Update statement
        """
        table = get_table(folder.value)
        return update(table).where(table.c.uid == uid).values(**values)

    @staticmethod
    def delete_email(folder: FolderName, uid: str):
        """Build DELETE query for email.

        Args:
            folder: Target folder
            uid: Email UID

        Returns:
            SQLAlchemy Delete statement
        """
        table = get_table(folder.value)
        return delete(table).where(table.c.uid == uid)

    @staticmethod
    def search_emails(
        folders: List[FolderName],
        keyword: str,
        fields: Set[str],
        limit: int = 50,
        offset: int = 0,
    ) -> Select:
        """Build search query across multiple folders.

        Args:
            folders: Folders to search in
            keyword: Search keyword
            fields: Fields to search (subject, sender, recipient, body)
            limit: Maximum results
            offset: Result offset

        Returns:
            SQLAlchemy Select with UNION ALL
        """
        if not folders:
            raise ValueError("At least one folder must be specified")
        if not keyword or len(keyword) > 1000:
            raise ValueError("keyword must be 1-1000 characters")
        if limit < 1 or limit > 10000:
            raise ValueError("limit must be 1-10000")
        if offset < 0:
            raise ValueError("offset must be >= 0")
    
        valid_fields = {"subject", "sender", "recipient", "body"}
        
        if not fields.issubset(valid_fields):
            raise ValueError(f"Invalid search fields: {fields - valid_fields}")

        # Build query for each folder
        union_queries = []
        for folder in folders:
            table = get_table(folder.value)

            # Build OR conditions for each field
            field_conditions = []
            for field in fields:
                column = getattr(table.c, field)
                field_conditions.append(column.like(f"%{keyword}%"))

            where_clause = or_(*field_conditions)

            # Select with folder label
            columns = [
                table.c.id,
                table.c.uid,
                table.c.subject,
                table.c.sender.label("from"),
                table.c.recipient.label("to"),
                table.c.date,
                table.c.time,
                table.c.body,
                table.c.attachments,
                table.c.is_read,
            ]
            # Add flagged if applicable
            if folder in (FolderName.INBOX, FolderName.TRASH):
                columns.append(table.c.flagged)
            query = select(*columns).where(where_clause)

            union_queries.append(query)

        # UNION ALL
        if len(union_queries) == 1:
            combined = union_queries[0]
        else:
            combined = union_queries[0].union_all(*union_queries[1:])

        # ORDER BY, LIMIT, OFFSET
        final = combined.order_by("date DESC", "time DESC").limit(limit).offset(offset)

        return final

    @staticmethod
    def _build_where(table, conditions: Dict[str, Any]) -> ColumnElement[bool]:
        """Build WHERE clause from conditions dictionary.

        Args:
            table: SQLAlchemy Table
            conditions: Dict of column: value pairs

        Returns:
            SQLAlchemy WHERE clause

        Supported condition formats:
            - {"uid": "123"} → uid = '123'
            - {"uid": None} → uid IS NULL
            - {"uid": ["123", "456"]} → uid IN ('123', '456')
            - {"flagged": True} → flagged = 1
        """
        clauses = []

        for col_name, value in conditions.items():
            column = getattr(table.c, col_name, None)
            if column is None:
                raise ValueError(f"Invalid column: {col_name} for table {table.name}")

            if value is None:
                clauses.append(column.is_(None))
            elif isinstance(value, (list, tuple)):
                clauses.append(column.in_(value))
            else:
                clauses.append(column == value)

        from sqlalchemy import true
        return and_(*clauses) if clauses else true()

    @staticmethod
    def count_emails(
        folder: FolderName,
        conditions: Optional[Dict[str, Any]] = None,
    ) -> Select:
        """Build COUNT query.

        Args:
            folder: Target folder
            conditions: Optional WHERE conditions

        Returns:
            SQLAlchemy Select with COUNT(*)
        """
        from sqlalchemy import func

        table = get_table(folder.value)
        query = select(func.count()).select_from(table)

        if conditions:
            where_clause = QueryBuilder._build_where(table, conditions)
            query = query.where(where_clause)

        return query
