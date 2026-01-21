"""Factory for EmailSendService with resource lifecycle management."""

from contextlib import asynccontextmanager
from typing import Optional

from src.core.database import EmailRepository, EngineManager
from src.core.email.smtp.connection import SMTPConnection
from src.core.email.smtp.protocol import SMTPProtocol
from src.core.email.services.send import EmailSendService
from src.utils.config import ConfigManager
from src.utils.logging import get_logger
from src.utils.paths import DATABASE_PATH

logger = get_logger(__name__)


class EmailSendServiceFactory:
    """Factory for creating EmailSendService with managed resources."""

    @classmethod
    @asynccontextmanager
    async def create(
        cls,
        config: Optional[ConfigManager] = None,
        max_retries: int = 3,
    ):
        """Create service with automatic resource management (recommended).

        Args:
            config: ConfigManager instance (creates new if None)
            max_retries: Maximum retry attempts for transient failures

        Yields:
            EmailSendService instance ready to use
        """
        resources = cls.create_resources(config)
        service = cls.create_service(resources, max_retries)

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
            - smtp_connection: SMTPConnection
            - protocol: SMTPProtocol
            - repository: EmailRepository
        """
        if config is None:
            config = ConfigManager()

        engine_manager = EngineManager(DATABASE_PATH)
        repository = EmailRepository(engine_manager)

        smtp_connection = SMTPConnection(config)
        protocol = SMTPProtocol(smtp_connection)

        logger.debug("Created all resources for EmailSendService")

        return {
            "config": config,
            "engine_manager": engine_manager,
            "smtp_connection": smtp_connection,
            "protocol": protocol,
            "repository": repository,
        }

    @classmethod
    def create_service(
        cls,
        resources: dict,
        max_retries: int = 3,
    ) -> EmailSendService:
        """Create service from resources.

        The service doesn't own the resources - it just uses them.
        Caller is responsible for cleanup.

        Args:
            resources: Dictionary from create_resources()
            max_retries: Maximum retry attempts

        Returns:
            EmailSendService instance
        """
        sender_email = resources["config"].config.account.email

        return EmailSendService(
            protocol=resources["protocol"],
            repository=resources["repository"],
            sender_email=sender_email,
            max_retries=max_retries,
        )

    @classmethod
    async def cleanup_resources(cls, resources: dict) -> None:
        """Clean up all resources in reverse order of creation.

        Args:
            resources: Dictionary from create_resources()
        """
        if "smtp_connection" in resources:
            try:
                await resources["smtp_connection"].close_connection()
                logger.debug("SMTP connection closed")
            except Exception as e:
                logger.error(f"Error closing SMTP connection: {e}")

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
