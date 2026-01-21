"""BatchResult: Result of batch operation for repositories."""

from dataclasses import dataclass, field
from typing import List
from src.core.models.email import EmailId


@dataclass
class BatchResult:
    """Result of batch operation."""

    total: int
    succeeded: int
    failed: int
    errors: List[tuple[EmailId, str]] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        return (self.succeeded / self.total * 100) if self.total > 0 else 0.0
