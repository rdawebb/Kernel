"""Base repository interface."""

import asyncio
from abc import ABC, abstractmethod
from typing import Callable, Generic, List, Optional, TypeVar

from src.core.models.email import FolderName

from .batch_result import BatchResult

T = TypeVar("T")
ID = TypeVar("ID")
CTX = TypeVar("CTX")


class Repository(ABC, Generic[T, ID, CTX]):
    """Base repository interface."""

    @abstractmethod
    async def save(self, entity: T) -> None:
        """Save single entity.

        Args:
            entity: The entity to save.
        """
        pass

    @abstractmethod
    async def save_batch(
        self,
        entities: List[T],
        batch_size: int = 100,
        progress: Optional[Callable[[int, int], None]] = None,
        cancel_token: Optional[asyncio.Event] = None,
    ) -> "BatchResult":
        """Save multiple entities in batches

        Args:
            entities: The entities to save.
            batch_size: The number of entities to save in each batch.
            progress: A callback function to report progress.
            cancel_token: An optional event to signal cancellation.

        Returns:
            BatchResult: The result of the batch save operation.
        """
        pass

    @abstractmethod
    async def find_by_id(self, id: ID, context: FolderName) -> Optional[T]:
        """Find entity by ID.

        Args:
            id: The entity ID to find.
            context: The context for lookup.

        Returns:
            The entity if found, None otherwise.
        """
        pass

    @abstractmethod
    async def find_all(
        self, context: FolderName, limit: int = 100, offset: int = 0
    ) -> List[T]:
        """Find all entities in context.

        Args:
            context: The context for querying.
            limit: The maximum number of entities to return.
            offset: Offset for pagination.

        Returns:
            A list of all entities.
        """
        pass

    @abstractmethod
    async def delete(self, id: ID, context: FolderName) -> None:
        """Delete entity by ID.

        Args:
            id: The ID of the entity to delete.
            context: The context for deletion.
        """
        pass

    @abstractmethod
    async def exists(self, id: ID, context: FolderName) -> bool:
        """Check if entity exists.

        Args:
            id: The ID of the entity to check.
            context: The context to check.

        Returns:
            True if the entity exists, False otherwise.
        """
        pass
