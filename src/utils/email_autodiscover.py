"""Email server auto-discovery for common email providers."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class EmailServerConfig:
    """Email server configuration for a provider."""

    imap_server: str
    imap_port: int = 993
    smtp_server: str = ""
    smtp_port: int = 587
    use_tls: bool = True


# Known email provider configurations
KNOWN_PROVIDERS = {
    "gmail.com": EmailServerConfig(
        imap_server="imap.gmail.com",
        imap_port=993,
        smtp_server="smtp.gmail.com",
        smtp_port=465,
        use_tls=True,
    ),
    "googlemail.com": EmailServerConfig(
        imap_server="imap.gmail.com",
        imap_port=993,
        smtp_server="smtp.gmail.com",
        smtp_port=465,
        use_tls=True,
    ),
    "outlook.com": EmailServerConfig(
        imap_server="imap-mail.outlook.com",
        imap_port=993,
        smtp_server="smtp-mail.outlook.com",
        smtp_port=587,
        use_tls=True,
    ),
    "hotmail.com": EmailServerConfig(
        imap_server="imap-mail.outlook.com",
        imap_port=993,
        smtp_server="smtp-mail.outlook.com",
        smtp_port=587,
        use_tls=True,
    ),
    "live.com": EmailServerConfig(
        imap_server="imap-mail.outlook.com",
        imap_port=993,
        smtp_server="smtp-mail.outlook.com",
        smtp_port=587,
        use_tls=True,
    ),
    "yahoo.com": EmailServerConfig(
        imap_server="imap.mail.yahoo.com",
        imap_port=993,
        smtp_server="smtp.mail.yahoo.com",
        smtp_port=587,
        use_tls=True,
    ),
    "aol.com": EmailServerConfig(
        imap_server="imap.aol.com",
        imap_port=993,
        smtp_server="smtp.aol.com",
        smtp_port=587,
        use_tls=True,
    ),
    "protonmail.com": EmailServerConfig(
        imap_server="imap.protonmail.com",
        imap_port=993,
        smtp_server="smtp.protonmail.com",
        smtp_port=587,
        use_tls=True,
    ),
    "proton.me": EmailServerConfig(
        imap_server="imap.protonmail.com",
        imap_port=993,
        smtp_server="smtp.protonmail.com",
        smtp_port=587,
        use_tls=True,
    ),
    "tutanota.com": EmailServerConfig(
        imap_server="imap.tutanota.com",
        imap_port=993,
        smtp_server="smtp.tutanota.com",
        smtp_port=587,
        use_tls=True,
    ),
    "fastmail.com": EmailServerConfig(
        imap_server="imap.fastmail.com",
        imap_port=993,
        smtp_server="smtp.fastmail.com",
        smtp_port=587,
        use_tls=True,
    ),
    "1and1.com": EmailServerConfig(
        imap_server="imap.1and1.com",
        imap_port=993,
        smtp_server="smtp.1and1.com",
        smtp_port=587,
        use_tls=True,
    ),
}


def autodiscover_email_config(email: str) -> Optional[EmailServerConfig]:
    """Discover email server configuration based on email address.

    Args:
        email: Email address (e.g., user@gmail.com)

    Returns:
        EmailServerConfig if provider is known, None otherwise
    """
    if not email or "@" not in email:
        return None

    domain = email.split("@")[1].lower()

    # Check exact match
    if domain in KNOWN_PROVIDERS:
        return KNOWN_PROVIDERS[domain]

    # Check for common subdomain (to be implemented)
    return None
