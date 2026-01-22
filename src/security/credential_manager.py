"""Credential management - prompting and validation of user credentials."""

from datetime import datetime, timedelta
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

from src.utils.config import ConfigManager
from src.utils.errors import InvalidCredentialsError, MissingCredentialsError
from src.utils.logging import get_logger

from .key_store import get_keystore

logger = get_logger(__name__)


class CredentialManager:
    """Handles user credential prompting and validation."""

    def __init__(self, config_manager: ConfigManager):
        """Initialise CredentialManager with ConfigManager."""

        self.config_manager = config_manager
        self.keystore = get_keystore()
        self._failed_attempts = 0
        self._lockout_until: Optional[datetime] = None
        self.MAX_ATTEMPTS = 5
        self.LOCKOUT_DURATION = timedelta(minutes=5)

    async def _check_rate_limit(self) -> bool:
        """Check if the user is currently locked out due to failed attempts.

        Returns:
            bool: True if the user is within the rate limit, False if locked out.
        """
        if self._lockout_until and datetime.now() < self._lockout_until:
            wait_seconds = (self._lockout_until - datetime.now()).total_seconds()
            logger.warning(f"Rate limited, wait {wait_seconds:.0f} seconds")
            return False

        return True

    async def _record_failure(self) -> None:
        """Record a failed login attempt and apply lockout if necessary."""
        self._failed_attempts += 1
        if self._failed_attempts >= self.MAX_ATTEMPTS:
            self._lockout_until = datetime.now() + self.LOCKOUT_DURATION
            logger.warning("Too many failed login attempts, user locked out")
        else:
            logger.warning(f"Failed login attempt {self._failed_attempts}")

    async def validate_and_prompt(self) -> bool:
        """Validate existing credentials, prompt user for missing ones.

        Returns:
            bool: True if credentials are valid, False otherwise.
        """
        account_config = self.config_manager.config.account

        if (
            not account_config.email
            or not account_config.username
            or not account_config.smtp_server
            or not account_config.imap_server
        ):
            logger.warning("Account configuration incomplete, prompting user...")

            if not await self._prompt_for_account_info():
                raise MissingCredentialsError("Account configuration is required.")

        # initialise keystore before use
        await self.keystore.initialise()

        password = await self.keystore.retrieve(account_config.username)
        if not password:
            logger.warning("Password not found in key store, prompting user...")
            if not await self._prompt_for_password():
                raise MissingCredentialsError("Password is required.")

        return True

    async def _prompt_for_account_info(self) -> bool:
        """Prompt user for email, username, and mail server settings if missing.

        Returns:
            bool: True if account information was provided, False otherwise.
        """
        account_config = self.config_manager.config.account

        session = PromptSession()

        try:
            if not account_config.email:
                with patch_stdout():
                    account_config.email = await session.prompt_async(
                        "Enter your email address: "
                    )

                if not account_config.email:
                    logger.error("No email address provided.")
                    return False

                self.config_manager.set_config("account.email", account_config.email)

            if not account_config.username:
                default_username = account_config.email
                username_prompt = (
                    f"Enter your username (press Enter to use '{default_username}'): "
                )
                with patch_stdout():
                    user_input = await session.prompt_async(username_prompt)
                username = user_input.strip()

                account_config.username = username if username else default_username
                self.config_manager.set_config(
                    "account.username", account_config.username
                )

                if username:
                    logger.info("Username set")
                else:
                    logger.info("Username defaulted to email")

            # Try auto-discovery for email servers
            if not account_config.imap_server or not account_config.smtp_server:
                from src.utils.email_autodiscover import autodiscover_email_config

                discovered = autodiscover_email_config(account_config.email)

                if discovered:
                    if not account_config.imap_server:
                        account_config.imap_server = discovered.imap_server
                        account_config.imap_port = discovered.imap_port
                        self.config_manager.set_config(
                            "account.imap_server", discovered.imap_server
                        )
                        self.config_manager.set_config(
                            "account.imap_port", discovered.imap_port
                        )
                        logger.info(
                            f"Auto-discovered IMAP server: {discovered.imap_server}"
                        )

                    if not account_config.smtp_server:
                        account_config.smtp_server = discovered.smtp_server
                        account_config.smtp_port = discovered.smtp_port
                        self.config_manager.set_config(
                            "account.smtp_server", discovered.smtp_server
                        )
                        self.config_manager.set_config(
                            "account.smtp_port", discovered.smtp_port
                        )
                        logger.info(
                            f"Auto-discovered SMTP server: {discovered.smtp_server}"
                        )

            if not account_config.imap_server:
                with patch_stdout():
                    account_config.imap_server = await session.prompt_async(
                        "Enter your IMAP server (e.g., imap.gmail.com): "
                    )

                if not account_config.imap_server:
                    logger.error("No IMAP server provided.")
                    return False

                self.config_manager.set_config(
                    "account.imap_server", account_config.imap_server
                )

            if not account_config.smtp_server:
                with patch_stdout():
                    account_config.smtp_server = await session.prompt_async(
                        "Enter your SMTP server (e.g., smtp.gmail.com): "
                    )

                if not account_config.smtp_server:
                    logger.error("No SMTP server provided.")
                    return False

                self.config_manager.set_config(
                    "account.smtp_server", account_config.smtp_server
                )

            logger.info("Account information updated successfully.")
            return True

        except KeyboardInterrupt:
            logger.info("User cancelled input.")
            return False

        except Exception as e:
            logger.error(f"Error while prompting for account info: {str(e)}")
            return False

    async def _prompt_for_password(self) -> bool:
        """Prompt user for password and store in keystore.

        Returns:
            bool: True if password was provided and stored, False otherwise.
        """
        account_config = self.config_manager.config.account

        session = PromptSession()

        try:
            with patch_stdout():
                password = await session.prompt_async(
                    "Enter password: ",
                    is_password=True,
                )

            if not password:
                logger.error("No password provided.")
                return False

            await self.keystore.store(account_config.username, password)
            logger.info("Password stored securely.")
            return True

        except KeyboardInterrupt:
            logger.info("User cancelled password input.")
            return False

        except Exception as e:
            logger.error(f"Error while prompting for password: {str(e)}")
            return False

    async def handle_auth_failure(self) -> None:
        """Handle authentication failure, prompt user to re-enter credentials."""
        account_config = self.config_manager.config.account

        logger.warning("Authentication failed, prompting user to re-enter credentials.")

        try:
            await self.keystore.delete(account_config.username)
            logger.info("Deleted stored password due to auth failure.")

        except Exception as e:
            logger.debug(f"Error deleting stored password: {str(e)}")

        logger.info("Please re-enter your credentials...")
        if not await self._prompt_for_password():
            raise InvalidCredentialsError(
                "Failed to obtain new password after authentication failure."
            )
