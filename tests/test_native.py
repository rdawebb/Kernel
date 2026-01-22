"""Test native IMAP/SMTP backend."""

import asyncio

from src.core.email.imap.connection import IMAPConnection
from src.core.email.imap.protocol import IMAPProtocol
from src.utils.config import ConfigManager


async def test_imap():
    """Test native IMAP implementation."""
    config = ConfigManager()
    connection = IMAPConnection(config)
    protocol = IMAPProtocol(connection)

    try:
        # Test connection and basic operations
        await protocol.select_folder("INBOX")

        uids = await protocol.search_uids("ALL")
        print(f"Found {len(uids)} messages in INBOX")

        if uids:
            # Fetch first message
            messages = await protocol.fetch_messages(uids[:1])
            print(f"Fetched {len(messages)} message(s)")

    finally:
        # Cleanup happens automatically
        pass


if __name__ == "__main__":
    asyncio.run(test_imap())
