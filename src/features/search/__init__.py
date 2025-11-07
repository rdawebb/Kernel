"""Email search feature.

Public API:
    search_emails(keyword, folder, limit) -> Search and display results
    SearchWorkflow -> Full search orchestration
"""

from .workflow import search_emails, SearchWorkflow
from .query import SearchQuery, QueryBuilder

__all__ = ['search_emails', 'SearchWorkflow', 'SearchQuery', 'QueryBuilder']