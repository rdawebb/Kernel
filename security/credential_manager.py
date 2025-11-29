"""Credential management - prompting and validation of user credentials."""

import getpass

from src.utils.config import ConfigManager
from src.utils.errors import InvalidCredentialsError, MissingCredentialsError
from src.utils.logging import get_logger

from .key_store import get_keystore

logger = get_logger(__name__)


class CredentialManager:
    """Handles user credential prompting and validation."""

    def __init__(self, config_manager: ConfigManager):
        """Initialize CredentialManager with ConfigManager."""

        self.config_manager = config_manager
        self.keystore = get_keystore()

    async def validate_and_prompt(self) -> bool:
        """Validate existing credentials, prompt user for missing ones."""

        account_config = self.config_manager.config.account

        if not account_config.email or not account_config.username:
            logger.warning("Email or username not configured, prompting user...")

            if not await self._prompt_for_account_info():
                raise MissingCredentialsError("Email or username are required.")

        password = self.keystore.retrieve(account_config.username)
        if not password:
            logger.warning("Password not found in key store, prompting user...")
            if not await self._prompt_for_password():
                raise MissingCredentialsError("Password is required.")

        return True

    async def _prompt_for_account_info(self) -> bool:
        """Prompt user for email and username if missing."""

        account_config = self.config_manager.config.account

        try:
            if not account_config.email:
                account_config.email = input("Enter your email address: ").strip()
                if not account_config.email:
                    logger.error("No email address provided.")
                    return False

                self.config_manager.set_config("account.email", account_config.email)

            if not account_config.username:
                default_username = account_config.email
                username_prompt = (
                    f"Enter your username (press Enter to use '{default_username}'): "
                )
                user_input = input(username_prompt).strip()

                account_config.username = user_input if user_input else default_username
                self.config_manager.set_config(
                    "account.username", account_config.username
                )

                if user_input:
                    logger.info(f"Username set to: {account_config.username}")
                else:
                    logger.info(
                        f"Username defaulted to email: {account_config.username}"
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
        """Prompt user for password and store in keystore."""

        account_config = self.config_manager.config.account

        try:
            password = getpass.getpass(
                f"Enter password for {account_config.username}: "
            )
            if not password:
                logger.error("No password provided.")
                return False

            self.keystore.store(account_config.username, password)
            logger.info(f"Password stored securely for {account_config.username}.")
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
            self.keystore.delete(account_config.username)
            logger.info(
                f"Deleted stored password for {account_config.username} due to auth failure."
            )

        except Exception as e:
            logger.debug(f"Error deleting stored password: {str(e)}")

        logger.info("Please re-enter your credentials...")
        if not await self._prompt_for_password():
            raise InvalidCredentialsError(
                "Failed to obtain new password after authentication failure."
            )
