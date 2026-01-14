"""Daemon authentication and Unix socket security.

Provides token-based authentication and socket file security:
- DaemonAuth: Generate, verify, and rotate authentication tokens
- SocketSecurity: Validate socket location and permissions

Security Features
-----------------
- Tokens are 32-byte cryptographically secure random hex strings
- Token files have 0o600 permissions (owner read/write only)
- Socket must reside within user's home directory (not /tmp)
- Constant-time token comparison prevents timing attacks
- Automatic token rotation after 24 hours

Usage Examples
--------------

Generate and verify a token:
    >>> from src.daemon.auth import DaemonAuth
    >>>
    >>> token = await DaemonAuth.generate_token()
    >>> is_valid = await DaemonAuth.verify_token(provided_token)

Rotate token periodically:
    >>> rotated = await DaemonAuth.rotate_if_expired(max_age_hours=12)

Verify socket security:
    >>> from src.daemon.auth import SocketSecurity
    >>>
    >>> socket_path = SocketSecurity.get_socket_path()
    >>> await SocketSecurity.verify_socket_location(socket_path)
"""

import asyncio
import os
import secrets
import time
from pathlib import Path

import aiofiles

from src.utils.errors import FileSystemError
from src.utils.logging import get_logger, log_event
from src.utils.paths import DAEMON_TOKEN_PATH

logger = get_logger(__name__)


_auth_metrics = {
    "tokens_generated": 0,
    "tokens_rotated": 0,
    "verifications_success": 0,
    "verifications_failure": 0,
}


def get_auth_metrics() -> dict:
    """Get authentication metrics"""
    return _auth_metrics.copy()


def reset_auth_metrics() -> None:
    """Reset authentication metrics"""
    global _auth_metrics
    _auth_metrics = {key: 0 for key in _auth_metrics}


class DaemonAuth:
    """Generate and verify authentication tokens for the daemon"""

    TOKEN_FILE = DAEMON_TOKEN_PATH
    TOKEN_LENGTH = 32  # bytes
    MAX_TOKEN_AGE_HOURS = 24
    _lock = asyncio.Lock()

    @classmethod
    async def _write_new_token(cls) -> str:
        """Generate and write a new token (caller must hold lock)."""
        token = secrets.token_hex(cls.TOKEN_LENGTH)
        cls.TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(cls.TOKEN_FILE, "w") as f:
            await f.write(token)

        await asyncio.to_thread(cls.TOKEN_FILE.chmod, 0o600)
        _auth_metrics["tokens_generated"] += 1
        logger.info("Generated new daemon authentication token")
        log_event("daemon_token_generated", {"token_length": len(token)})
        return token

    @classmethod
    async def generate_token(cls) -> str:
        """Generate a new authentication token and save it to file"""
        async with cls._lock:
            return await cls._write_new_token()

    @classmethod
    async def get_token(cls) -> str | None:
        """Retrieve the current authentication token from file"""
        async with cls._lock:
            if not cls.TOKEN_FILE.exists():
                return await cls._write_new_token()

            try:
                async with aiofiles.open(cls.TOKEN_FILE, "r") as f:
                    token = (await f.read()).strip()
                return token

            except Exception as e:
                logger.error(f"Failed to read daemon token: {e}")
                return None

    @classmethod
    async def verify_token(cls, provided_token: str, client_info: dict | None) -> bool:
        """Verify a provided authentication token against the stored token"""
        if not provided_token:
            _auth_metrics["verifications_failure"] += 1
            logger.warning(
                "No token provided for verification", extra={"client": client_info}
            )
            cls._audit_log_failure("no_token", client_info or {})
            return False

        stored_token = await cls.get_token()
        if not stored_token:
            _auth_metrics["verifications_failure"] += 1
            logger.error(
                "No stored token available for verification",
                extra={"client": client_info},
            )
            return False

        is_valid = secrets.compare_digest(provided_token, stored_token)
        if is_valid:
            _auth_metrics["verifications_success"] += 1
            logger.debug("Token verification succeeded", extra={"client": client_info})
        else:
            _auth_metrics["verifications_failure"] += 1
            logger.warning("Token verification failed", extra={"client": client_info})
            cls._audit_log_failure("invalid_token", client_info or {})

        return is_valid

    @classmethod
    async def rotate_token(cls) -> str:
        """Rotate the authentication token by generating a new one"""
        async with cls._lock:
            if cls.TOKEN_FILE.exists():
                await asyncio.to_thread(cls.TOKEN_FILE.unlink, missing_ok=True)

            token = await cls._write_new_token()

            _auth_metrics["tokens_rotated"] += 1
            logger.info("Rotated daemon authentication token")
            log_event(
                "daemon_token_rotated",
                {"timestamp": time.time(), "token_length": len(token)},
            )

            return token

    @classmethod
    async def rotate_if_expired(cls, max_age_hours: int | None) -> bool:
        """Rotate the token if it is older than max_age_hours"""
        max_age = max_age_hours or cls.MAX_TOKEN_AGE_HOURS

        if not cls.TOKEN_FILE.exists():
            return False

        file_stat = await asyncio.to_thread(cls.TOKEN_FILE.stat)
        age_hours = (time.time() - file_stat.st_mtime) / 3600

        if age_hours >= max_age:
            logger.info(f"Token expired (age: {age_hours:.1f} hours), rotating...")
            await cls.rotate_token()
            return True

        return False

    @classmethod
    def _audit_log_failure(cls, reason: str, client_info: dict) -> None:
        """Log authentication failure for auditing purposes"""
        log_event(
            "daemon_auth_failure",
            {
                "reason": reason,
                "client_pid": client_info.get("pid"),
                "timestamp": time.time(),
            },
        )


class SocketSecurity:
    """Manage socket file security for the daemon"""

    @staticmethod
    def get_socket_path() -> Path:
        """Get the path to the daemon socket file"""
        from src.utils.paths import DAEMON_SOCKET_PATH

        return DAEMON_SOCKET_PATH

    @staticmethod
    async def verify_socket_location(socket_path: Path) -> None:
        """Verify that the socket file is in the correct location and has secure permissions"""
        try:
            resolved_path = await asyncio.to_thread(socket_path.resolve)
            home_dir = await asyncio.to_thread(Path.home().resolve)

            try:
                await asyncio.to_thread(resolved_path.relative_to, home_dir)
            except ValueError:
                raise FileSystemError(
                    f"Socket must be located within the user's home directory ({home_dir}), not {resolved_path}",
                    details={"path": str(resolved_path), "home": str(home_dir)},
                )

            tmp_dir = await asyncio.to_thread(Path("/tmp").resolve)
            try:
                await asyncio.to_thread(resolved_path.relative_to, tmp_dir)
                raise FileSystemError(
                    f"Socket must not be located within /tmp directory, found at {resolved_path}",
                    details={"path": str(resolved_path), "tmp": str(tmp_dir)},
                )
            except ValueError:
                pass

            parent_dir = resolved_path.parent
            if not parent_dir.exists():
                parent_dir.mkdir(parents=True, exist_ok=True)
                await asyncio.to_thread(parent_dir.chmod, 0o700)
                logger.info(f"Created secure socket directory: {parent_dir}")

            stat_info = await asyncio.to_thread(parent_dir.stat)
            current_uid = os.getuid()
            if stat_info.st_uid != current_uid:
                raise FileSystemError(
                    "Socket directory is not owned by the current user",
                    details={
                        "path": str(parent_dir),
                        "owner_uid": stat_info.st_uid,
                        "current_uid": current_uid,
                    },
                )

            logger.info(f"Socket location verified as secure: {resolved_path}")
            log_event("socket_security_verified", {"path": str(resolved_path)})

        except FileSystemError:
            raise

        except Exception as e:
            logger.error(f"Failed to verify socket location: {e}")
            raise FileSystemError(
                "Failed to verify socket location",
                details={"error": str(e), "path": str(socket_path)},
            ) from e

    @staticmethod
    async def secure_socket_permissions(socket_path: Path) -> None:
        """Set secure permissions on the socket file"""
        if socket_path.exists():
            await asyncio.to_thread(socket_path.chmod, 0o600)
            logger.debug(f"Set secure permissions on socket: {socket_path}")

    @staticmethod
    async def verify_socket_permissions(socket_path: Path) -> bool:
        """Verify that the socket file has secure permissions"""
        if not socket_path.exists():
            logger.warning(
                f"Socket file does not exist for permission verification: {socket_path}"
            )
            return False

        try:
            stat_info = await asyncio.to_thread(socket_path.stat)
            mode = stat_info.st_mode & 0o777

            if mode != 0o600:
                logger.warning(f"Socket file has insecure permissions: {oct(mode)}")
                return False

            if stat_info.st_uid != os.getuid():
                logger.warning(
                    f"Socket file is not owned by the current user: {stat_info.st_uid}"
                )
                return False

            return True

        except Exception as e:
            logger.error(f"Failed to verify socket permissions: {e}")
            return False
