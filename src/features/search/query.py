"""Search query building and parsing."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class SearchQuery:
    """Represents a search query."""
    
    keyword: str
    folder: str = "inbox"
    search_all_folders: bool = False
    fields: List[str] = field(default_factory=lambda: ["subject", "from", "to", "body"])
    
    def __post_init__(self):
        """Validate query."""
        if not self.keyword or not self.keyword.strip():
            raise ValueError("Search keyword cannot be empty")
        
        self.keyword = self.keyword.strip()


class QueryBuilder:
    """Builds search queries from various inputs."""
    
    @staticmethod
    def from_string(query_string: str, folder: str = "inbox") -> SearchQuery:
        """Parse natural language query string.
        
        Examples:
            "hello" -> Search for "hello"
            "from:alice hello" -> Search "hello" from alice
            "subject:meeting" -> Search "meeting" in subject only
        """
        # Basic implementation - can be expanded for advanced queries
        parts = query_string.split()
        
        keyword = query_string
        search_fields = ["subject", "from", "to", "body"]
        from_filter = None
        subject_filter = None
        
        # Parse field filters
        filtered_parts = []
        for part in parts:
            if part.startswith("from:"):
                from_filter = part[5:]
            elif part.startswith("subject:"):
                subject_filter = part[8:]
            else:
                filtered_parts.append(part)
        
        if filtered_parts:
            keyword = " ".join(filtered_parts)
        
        # Adjust search fields based on filters
        if from_filter:
            search_fields = ["from"]
            keyword = from_filter
        elif subject_filter:
            search_fields = ["subject"]
            keyword = subject_filter
        
        return SearchQuery(
            keyword=keyword,
            folder=folder,
            fields=search_fields
        )
    
    @staticmethod
    def from_args(args) -> SearchQuery:
        """Create query from CLI arguments."""
        keyword = getattr(args, 'keyword', '')
        folder = getattr(args, 'folder', 'inbox')
        search_all = getattr(args, 'all', False)
        
        return SearchQuery(
            keyword=keyword,
            folder=folder,
            search_all_folders=search_all
        )