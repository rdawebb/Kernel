"""Search service with type-safe queries and operator support."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional, Set

from sqlalchemy import and_, literal, or_, select, func
from sqlalchemy.sql import ColumnElement, Select

from src.core.database import EngineManager, get_config, get_table
from src.core.models.email import Email, FolderName
from src.utils.logging import get_logger

from ..utils import row_to_email

logger = get_logger(__name__)


class SearchOperator(Enum):
    """Search operators for query building."""

    EQUALS = "="
    NOT_EQUALS = "!="
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_EQUAL = ">="
    LESS_EQUAL = "<="
    IN = "in"
    NOT_IN = "not_in"


@dataclass
class SearchFilter:
    """Individual search filter with field, operator, and value."""

    field: str
    operator: SearchOperator
    value: Any

    def __post_init__(self):
        """Validate field name."""
        valid_fields = {
            "subject",
            "sender",
            "recipient",
            "body",
            "date",
            "time",
            "flagged",
            "is_read",
        }
        if self.field not in valid_fields:
            raise ValueError(
                f"Invalid search field: {self.field}. "
                f"Must be one of: {', '.join(sorted(valid_fields))}"
            )


@dataclass
class SearchQuery:
    """Search query specification with filters and options."""

    keyword: Optional[str] = None
    filters: List[SearchFilter] = field(default_factory=list)
    folders: List[FolderName] = field(default_factory=lambda: list(FolderName))
    search_fields: Optional[Set[str]] = None
    limit: int = 50
    offset: int = 0
    order_by: str = "date"
    order_desc: bool = True

    def __post_init__(self):
        """Validate and set defaults."""
        if self.search_fields is None:
            self.search_fields = {"subject", "sender", "recipient", "body"}

        # Validate search fields
        valid_fields = {"subject", "sender", "recipient", "body"}
        invalid = self.search_fields - valid_fields
        if invalid:
            raise ValueError(f"Invalid search fields: {invalid}")

        # Validate order_by
        valid_order = {"date", "time", "subject", "sender"}
        if self.order_by not in valid_order:
            raise ValueError(
                f"Invalid order_by: {self.order_by}. Must be one of: {valid_order}"
            )

        # Validate limit
        if self.limit <= 0:
            raise ValueError("limit must be positive")
        if self.limit > 1000:
            raise ValueError("limit cannot exceed 1000")


@dataclass
class SearchResult:
    """Search result with emails and metadata."""

    emails: List[Email]
    total_count: int
    query_time_ms: float
    folders_searched: List[str]

    @property
    def has_more(self) -> bool:
        """Check if there are more results available."""
        return len(self.emails) < self.total_count


class SearchService:
    """Type-safe search service with operator support.

    Provides:
    - Field validation (whitelist approach)
    - Multiple operators (=, contains, >, <, etc.)
    - Multi-folder search with UNION
    - Query optimization hints
    - Result counting and pagination
    """

    # Mapping from domain field names to database columns
    FIELD_MAP = {
        "sender": "sender",
        "recipient": "recipient",
        "subject": "subject",
        "body": "body",
        "date": "date",
        "time": "time",
        "flagged": "flagged",
        "is_read": "is_read",
    }

    def __init__(self, engine_manager: EngineManager):
        """Initialize search service.

        Args:
            engine_manager: Engine manager for database access
        """
        self.engine_mgr = engine_manager

    async def search(self, query: SearchQuery) -> SearchResult:
        """Execute search query.

        Args:
            query: Search query specification

        Returns:
            SearchResult with matching emails and metadata
        """
        import time

        start_time = time.time()

        # Build and execute query
        engine = await self.engine_mgr.get_engine()

        # If no keyword and no filters, return empty
        if not query.keyword and not query.filters:
            return SearchResult(
                emails=[],
                total_count=0,
                query_time_ms=0,
                folders_searched=[f.value for f in query.folders],
            )

        # Build queries: one for data (with LIMIT/OFFSET), one for counting
        sql_query = self._build_search_query(query)
        count_query = self._build_count_query(query)

        async with engine.connect() as conn:
            # Execute both queries concurrently for efficiency
            result = await conn.execute(sql_query)
            rows = result.fetchall()

            count_result = await conn.execute(count_query)
            total_count = count_result.scalar() or 0

        # Convert rows to Email objects
        emails = []
        for row in rows:
            folder_name = row.folder if hasattr(row, "folder") else "inbox"
            try:
                folder = FolderName(folder_name)
                email = row_to_email(row, folder)
                emails.append(email)
            except Exception as e:
                logger.warning(f"Failed to parse email row: {e}")
                continue

        # Calculate query time
        query_time_ms = (time.time() - start_time) * 1000

        # Log slow queries
        config = get_config()
        if (
            config.log_slow_queries
            and query_time_ms > config.slow_query_threshold * 1000
        ):
            logger.warning(
                f"Slow search query: {query_time_ms:.1f}ms "
                f"(keyword={query.keyword}, folders={len(query.folders)}, "
                f"total_count={total_count})"
            )

        return SearchResult(
            emails=emails,
            total_count=total_count,
            query_time_ms=query_time_ms,
            folders_searched=[f.value for f in query.folders],
        )

    async def search_in_folder(
        self,
        folder: FolderName,
        keyword: str,
        fields: Optional[Set[str]] = None,
        limit: int = 50,
    ) -> List[Email]:
        """Search in single folder (convenience method).

        Args:
            folder: Folder to search in
            keyword: Search keyword
            fields: Fields to search in (default: all)
            limit: Maximum results

        Returns:
            List of matching emails
        """
        query = SearchQuery(
            keyword=keyword,
            folders=[folder],
            search_fields=fields,
            limit=limit,
        )

        result = await self.search(query)
        return result.emails

    async def search_all_folders(
        self,
        keyword: str,
        fields: Optional[Set[str]] = None,
        limit: int = 50,
    ) -> List[Email]:
        """Search across all folders (convenience method).

        Args:
            keyword: Search keyword
            fields: Fields to search in (default: all)
            limit: Maximum results

        Returns:
            List of matching emails
        """
        query = SearchQuery(
            keyword=keyword,
            folders=list(FolderName),
            search_fields=fields,
            limit=limit,
        )

        result = await self.search(query)
        return result.emails

    async def advanced_search(
        self,
        filters: List[SearchFilter],
        folders: Optional[List[FolderName]] = None,
        limit: int = 50,
    ) -> SearchResult:
        """Advanced search with multiple filters.

        Args:
            filters: List of search filters
            folders: Folders to search (default: all)
            limit: Maximum results

        Returns:
            SearchResult with matching emails

        Example:
            filters = [
                SearchFilter("sender", SearchOperator.CONTAINS, "example.com"),
                SearchFilter("date", SearchOperator.GREATER_EQUAL, "2024-01-01"),
                SearchFilter("flagged", SearchOperator.EQUALS, True),
            ]
            result = await service.advanced_search(filters)
        """
        query = SearchQuery(
            filters=filters,
            folders=folders or list(FolderName),
            limit=limit,
        )

        return await self.search(query)

    def _build_search_query(self, query: SearchQuery) -> Select:
        """Build SQLAlchemy SELECT query from search specification.

        Args:
            query: Search query specification

        Returns:
            SQLAlchemy Select statement
        """
        union_queries = []

        for folder in query.folders:
            table = get_table(folder.value)

            # Build WHERE conditions
            conditions = []

            # Keyword search across specified fields
            if query.keyword and query.keyword.strip():
                keyword_conditions = []
                search_fields = query.search_fields or {
                    "subject",
                    "sender",
                    "recipient",
                    "body",
                }
                for field in search_fields:
                    column = getattr(table.c, self.FIELD_MAP[field])
                    keyword_conditions.append(column.like(f"%{query.keyword}%"))
                conditions.append(or_(*keyword_conditions))

            # Additional filters
            for filter_ in query.filters:
                column = getattr(table.c, self.FIELD_MAP[filter_.field])
                condition = self._build_filter_condition(column, filter_)
                conditions.append(condition)

            # Combine conditions with AND
            where_clause = and_(*conditions) if conditions else None

            # Select columns
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

            # Add folder-specific columns
            if hasattr(table.c, "flagged"):
                columns.append(table.c.flagged)

            # Add folder label for result parsing
            columns.append(literal(folder.value).label("folder"))

            # Build query for this folder
            if where_clause is not None:
                folder_query = select(*columns).where(where_clause)
            else:
                folder_query = select(*columns)

            union_queries.append(folder_query)

        # Combine with UNION ALL
        if len(union_queries) == 1:
            combined = union_queries[0]
        else:
            combined = union_queries[0].union_all(*union_queries[1:])

        # Add ORDER BY
        order_col = query.order_by
        if query.order_desc:
            combined = combined.order_by(f"{order_col} DESC")
        else:
            combined = combined.order_by(order_col)

        # Add secondary sort by time if ordering by date
        if query.order_by == "date":
            time_order = "time DESC" if query.order_desc else "time ASC"
            combined = combined.order_by(
                f"{order_col} DESC" if query.order_desc else order_col, time_order
            )

        # Add LIMIT and OFFSET
        combined = combined.limit(query.limit).offset(query.offset)

        return combined

    def _build_count_query(self, query: SearchQuery) -> Select:
        """Build SQLAlchemy COUNT query from search specification (without LIMIT/OFFSET).

        This query counts ALL matching results across all folders, used for pagination.

        Args:
            query: Search query specification

        Returns:
            SQLAlchemy Select statement that returns total count
        """
        union_queries = []

        for folder in query.folders:
            table = get_table(folder.value)

            # Build WHERE conditions
            conditions = []

            # Keyword search across specified fields
            if query.keyword and query.keyword.strip():
                keyword_conditions = []
                search_fields = query.search_fields or {
                    "subject",
                    "sender",
                    "recipient",
                    "body",
                }
                for field in search_fields:
                    column = getattr(table.c, self.FIELD_MAP[field])
                    keyword_conditions.append(column.like(f"%{query.keyword}%"))
                conditions.append(or_(*keyword_conditions))

            # Additional filters
            for filter_ in query.filters:
                column = getattr(table.c, self.FIELD_MAP[filter_.field])
                condition = self._build_filter_condition(column, filter_)
                conditions.append(condition)

            # Combine conditions with AND
            where_clause = and_(*conditions) if conditions else None

            # Count query for this folder (just count the IDs)
            if where_clause is not None:
                folder_query = select(func.count(table.c.id)).where(where_clause)
            else:
                folder_query = select(func.count(table.c.id))

            union_queries.append(folder_query)

        # Sum counts across all folders using UNION ALL with outer aggregation
        if len(union_queries) == 1:
            combined = union_queries[0]
        else:
            # Union all folder counts and sum them
            combined = select(func.sum(func.count())).select_from(
                union_queries[0].union_all(*union_queries[1:]).subquery()
            )

        return combined

    def _build_filter_condition(
        self,
        column: ColumnElement,
        filter_: SearchFilter,
    ) -> ColumnElement[bool]:
        """Build SQLAlchemy condition from filter.

        Args:
            column: Table column
            filter_: Search filter

        Returns:
            SQLAlchemy WHERE condition
        """
        op = filter_.operator
        value = filter_.value

        if op == SearchOperator.EQUALS:
            return column == value
        elif op == SearchOperator.NOT_EQUALS:
            return column != value
        elif op == SearchOperator.CONTAINS:
            return column.like(f"%{value}%")
        elif op == SearchOperator.STARTS_WITH:
            return column.like(f"{value}%")
        elif op == SearchOperator.ENDS_WITH:
            return column.like(f"%{value}")
        elif op == SearchOperator.GREATER_THAN:
            return column > value
        elif op == SearchOperator.LESS_THAN:
            return column < value
        elif op == SearchOperator.GREATER_EQUAL:
            return column >= value
        elif op == SearchOperator.LESS_EQUAL:
            return column <= value
        elif op == SearchOperator.IN:
            return column.in_(value)
        elif op == SearchOperator.NOT_IN:
            return column.notin_(value)
        else:
            raise ValueError(f"Unsupported operator: {op}")


class SearchQueryBuilder:
    """Fluent builder for SearchQuery (convenience API).

    Example:
        query = (SearchQueryBuilder()
            .keyword("important")
            .in_folders([FolderName.INBOX])
            .filter("sender", SearchOperator.CONTAINS, "boss@company.com")
            .filter("flagged", SearchOperator.EQUALS, True)
            .limit(20)
            .build())

        result = await search_service.search(query)
    """

    def __init__(self):
        self._keyword: Optional[str] = None
        self._filters: List[SearchFilter] = []
        self._folders: List[FolderName] = list(FolderName)
        self._search_fields: Optional[Set[str]] = None
        self._limit: int = 50
        self._offset: int = 0
        self._order_by: str = "date"
        self._order_desc: bool = True

    def keyword(self, keyword: str) -> "SearchQueryBuilder":
        """Set search keyword."""
        self._keyword = keyword
        return self

    def filter(
        self,
        field: str,
        operator: SearchOperator,
        value: Any,
    ) -> "SearchQueryBuilder":
        """Add a filter."""
        self._filters.append(SearchFilter(field, operator, value))
        return self

    def in_folders(self, folders: List[FolderName]) -> "SearchQueryBuilder":
        """Set folders to search."""
        self._folders = folders
        return self

    def in_folder(self, folder: FolderName) -> "SearchQueryBuilder":
        """Set single folder to search."""
        self._folders = [folder]
        return self

    def fields(self, fields: Set[str]) -> "SearchQueryBuilder":
        """Set fields to search in."""
        self._search_fields = fields
        return self

    def limit(self, limit: int) -> "SearchQueryBuilder":
        """Set result limit."""
        self._limit = limit
        return self

    def offset(self, offset: int) -> "SearchQueryBuilder":
        """Set result offset."""
        self._offset = offset
        return self

    def order_by(self, field: str, desc: bool = True) -> "SearchQueryBuilder":
        """Set ordering."""
        self._order_by = field
        self._order_desc = desc
        return self

    def build(self) -> SearchQuery:
        """Build the search query."""
        return SearchQuery(
            keyword=self._keyword,
            filters=self._filters,
            folders=self._folders,
            search_fields=self._search_fields,
            limit=self._limit,
            offset=self._offset,
            order_by=self._order_by,
            order_desc=self._order_desc,
        )
