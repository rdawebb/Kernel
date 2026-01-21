"""Factory for EmailFetchService with resource lifecycle management."""

from contextlib import asynccontextmanager
from typing import Optional

from src.core.database import EmailRepository, EngineManager
from src.core.email.imap.connection import IMAPConnection
from src.core.email.imap.protocol import IMAPProtocol
from src.core.email.services.fetch import EmailFetchService
from src.utils.config import ConfigManager
from src.utils.logging import get_logger
from src.utils.paths import DATABASE_PATH

logger = get_logger(__name__)


class EmailFetchServiceFactory:
    """Factory for creating EmailFetchService with managed resources."""

    @classmethod
    @asynccontextmanager
    async def create(
        cls,
        config: Optional[ConfigManager] = None,
        batch_size: int = 50,
        batch_delay: float = 0.0,
    ):
        """Create service with automatic resource management (recommended).

        Args:
            config: ConfigManager instance (creates new if None)
            batch_size: Number of emails to fetch per batch
            batch_delay: Delay in seconds between batches

        Yields:
            EmailFetchService instance ready to use
        """
        resources = cls.create_resources(config)

        service = cls.create_service(resources, batch_size, batch_delay)

        try:
            yield service
        finally:
            await cls.cleanup_resources(resources)

    @classmethod
    def create_resources(
        cls,
        config: Optional[ConfigManager] = None,
    ) -> dict:
        """Create all required resources.

        Args:
            config: ConfigManager instance (creates new if None)

        Returns:
            Dictionary containing all resources:
            - config: ConfigManager
            - engine_manager: EngineManager
            - imap_connection: IMAPConnection
            - protocol: IMAPProtocol
            - repository: EmailRepository
        """
        if config is None:
            config = ConfigManager()

        engine_manager = EngineManager(DATABASE_PATH)
        repository = EmailRepository(engine_manager)

        imap_connection = IMAPConnection(config)
        protocol = IMAPProtocol(imap_connection)

        logger.debug("Created all resources for EmailFetchService")

        return {
            "config": config,
            "engine_manager": engine_manager,
            "imap_connection": imap_connection,
            "protocol": protocol,
            "repository": repository,
        }

    @classmethod
    def create_service(
        cls,
        resources: dict,
        batch_size: int = 50,
        batch_delay: float = 0.0,
    ) -> EmailFetchService:
        """Create service from resources.

        The service doesn't own the resources - it just uses them.
        Caller is responsible for cleanup.

        Args:
            resources: Dictionary from create_resources()
            batch_size: Number of emails to fetch per batch
            batch_delay: Delay in seconds between batches

        Returns:
            EmailFetchService instance
        """
        return EmailFetchService(
            protocol=resources["protocol"],
            repository=resources["repository"],
            batch_size=batch_size,
            batch_delay=batch_delay,
        )

    @classmethod
    async def cleanup_resources(cls, resources: dict) -> None:
        """Clean up all resources in reverse order of creation.

        Args:
            resources: Dictionary from create_resources()
        """
        if "imap_connection" in resources:
            try:
                await resources["imap_connection"].close_connection()
                logger.debug("IMAP connection closed")
            except Exception as e:
                logger.error(f"Error closing IMAP connection: {e}")

        if "engine_manager" in resources:
            try:
                await resources["engine_manager"].close()
                logger.debug("Database connection closed")
            except Exception as e:
                logger.error(f"Error closing database connection: {e}")

        logger.debug("All resources cleaned up")

    @classmethod
    @asynccontextmanager
    async def create_shared(
        cls,
        config: Optional[ConfigManager] = None,
    ):
        """Create resources that can be shared across multiple services.

        This is useful when you need multiple service instances but want
        to share the underlying connections for efficiency.

        Args:
            config: ConfigManager instance (creates new if None)

        Yields:
            Dictionary of resources that can be passed to create_service()
        """
        resources = cls.create_resources(config)

        try:
            yield resources
        finally:
            await cls.cleanup_resources(resources)
