"""Background daemon for persistent email connections and command execution.

This module provides the email daemon infrastructure:
- EmailDaemon: Core daemon with command routing and caching
- DaemonClient: CLI interface for daemon communication
- ConnectionPoolManager: Managed IMAP/SMTP connection pools
- CacheManager: LRU cache with TTL for command results

The daemon runs as a background process, maintaining persistent connections
and handling commands via Unix socket communication.

Usage Examples
--------------

Start the daemon:
    >>> from src.daemon import run_daemon
    >>> await run_daemon()

Send a command via client:
    >>> from src.daemon import DaemonClient
    >>>
    >>> client = DaemonClient()
    >>> result = await client.send_command("inbox", {"limit": 10})
    >>> print(result)

Check daemon status:
    >>> from src.daemon import DaemonClient
    >>>
    >>> client = DaemonClient()
    >>> if await client.is_running():
    ...     print("Daemon is running")

Notes
-----
- Daemon communicates via secure Unix socket
- Token-based authentication for socket connections
- Circuit breaker pattern prevents cascading failures
- Connections are pooled with automatic keepalive

See Also
--------
- EmailDaemon: Full daemon command handling documentation
- DaemonClient: Client communication documentation
- ConnectionPoolManager: Connection pool documentation
"""

from .auth import DaemonAuth, SocketSecurity
from .cache import CacheManager, get_cache_metrics
from .client import CircuitBreaker, CircuitState, DaemonClient
from .daemon import run_daemon
from .lifecycle import CommandResult, EmailDaemon
from .pools import ConnectionPoolManager, get_pool_metrics

__all__ = [
    # Core daemon
    "EmailDaemon",
    "CommandResult",
    "run_daemon",
    # Client
    "DaemonClient",
    "CircuitBreaker",
    "CircuitState",
    # Infrastructure
    "ConnectionPoolManager",
    "CacheManager",
    "DaemonAuth",
    "SocketSecurity",
    # Metrics
    "get_cache_metrics",
    "get_pool_metrics",
]
