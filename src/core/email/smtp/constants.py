"""SMTP constants and configuration values."""

from dataclasses import dataclass


class SMTPResponse:
    """Standard SMTP response codes."""

    # 2xx Success
    OK = 250  # Requested mail action okay, completed
    USER_NOT_LOCAL = 251  # User not local; will forward
    CANNOT_VRFY = 252  # Cannot VRFY user, but will accept message

    # 3xx Intermediate
    START_MAIL = 354  # Start mail input; end with <CRLF>.<CRLF>

    # 4xx Transient Failure
    SERVICE_NOT_AVAILABLE = 421  # Service not available, closing channel
    MAILBOX_BUSY = 450  # Mailbox unavailable (e.g., busy)
    LOCAL_ERROR = 451  # Local error in processing
    INSUFFICIENT_STORAGE = 452  # Insufficient system storage

    # 5xx Permanent Failure
    SYNTAX_ERROR = 500  # Syntax error, command unrecognized
    PARAMETER_ERROR = 501  # Syntax error in parameters
    NOT_IMPLEMENTED = 502  # Command not implemented
    BAD_SEQUENCE = 503  # Bad sequence of commands
    PARAMETER_NOT_IMPLEMENTED = 504  # Command parameter not implemented
    MAILBOX_UNAVAILABLE = 550  # Mailbox unavailable
    USER_NOT_LOCAL_ERROR = 551  # User not local
    STORAGE_EXCEEDED = 552  # Exceeded storage allocation
    MAILBOX_NAME_INVALID = 553  # Mailbox name not allowed
    TRANSACTION_FAILED = 554  # Transaction failed


class Timeouts:
    """Timeout values for SMTP operations (in seconds)."""

    SMTP_CONNECT = 30.0  # Initial connection timeout
    SMTP_LOGIN = 30.0  # Login operation timeout
    SMTP_SEND = 60.0  # Send operation timeout (can be slow for large emails)
    SMTP_NOOP = 5.0  # NOOP (keep-alive) timeout
    SMTP_QUIT = 5.0  # QUIT operation timeout
    SMTP_VRFY = 10.0  # VRFY (verify address) timeout
    SMTP_STARTTLS = 30.0  # STARTTLS handshake timeout


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    MAX_RETRIES: int = 3  # Maximum retry attempts
    BASE_DELAY: float = 1.0  # Base delay for exponential backoff (seconds)
    MAX_DELAY: float = 60.0  # Maximum delay between retries (seconds)


class TransientErrors:
    """SMTP error codes that warrant retry attempts."""

    CODES = [
        SMTPResponse.SERVICE_NOT_AVAILABLE,  # 421
        SMTPResponse.MAILBOX_BUSY,  # 450
        SMTPResponse.LOCAL_ERROR,  # 451
        SMTPResponse.INSUFFICIENT_STORAGE,  # 452
    ]

    @classmethod
    def is_transient(cls, code: int) -> bool:
        """Check if an error code is transient.

        Args:
            code: SMTP response code

        Returns:
            True if transient, False otherwise
        """
        return code in cls.CODES


class SMTPPorts:
    """Standard SMTP port numbers."""

    # Submission ports (client to server)
    SUBMISSION = 587  # STARTTLS (recommended)
    SUBMISSION_SSL = 465  # Implicit TLS/SSL

    # Legacy/relay ports
    SMTP = 25  # Plain SMTP (server-to-server)

    @classmethod
    def requires_starttls(cls, port: int) -> bool:
        """Check if port requires STARTTLS.

        Args:
            port: SMTP port number

        Returns:
            True if STARTTLS required, False if implicit SSL
        """
        return port in (cls.SUBMISSION, cls.SMTP)

    @classmethod
    def is_implicit_ssl(cls, port: int) -> bool:
        """Check if port uses implicit SSL.

        Args:
            port: SMTP port number

        Returns:
            True if implicit SSL, False otherwise
        """
        return port == cls.SUBMISSION_SSL


class ConnectionLimits:
    """Connection and message limits."""

    DEFAULT_TTL = 1800  # Default connection TTL (30 minutes)
    MAX_MESSAGE_SIZE = 25 * 1024 * 1024  # 25 MB (common limit)
    MAX_RECIPIENTS = 100  # Maximum recipients per message
    MAX_LINE_LENGTH = 998  # RFC 5321 limit (excluding CRLF)
