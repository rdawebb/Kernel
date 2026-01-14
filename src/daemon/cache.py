"""LRU cache with TTL for daemon command results.

Provides in-memory caching to reduce redundant database queries
and improve response times for frequently accessed data.

Features
--------
- LRU (Least Recently Used) eviction when max entries reached
- TTL (Time To Live) expiration for stale entries
- Pattern-based invalidation for targeted cache clearing
- Thread-safe with asyncio locks
- Metrics tracking for hit rate analysis

Usage Examples
--------------

Basic cache operations:
    >>> cache = CacheManager(max_entries=100, ttl_seconds=120)
    >>>
    >>> cache_key = cache.get_cache_key("inbox", {"limit": 10})
    >>> await cache.set(cache_key, result_data)
    >>> cached = await cache.get(cache_key)

Invalidate after write operations:
    >>> await cache.invalidate_table("inbox")
    >>> await cache.invalidate_email("12345")
    >>> await cache.invalidate_all()

Check cache statistics:
    >>> stats = await cache.get_stats()
    >>> print(f"Hit rate: {stats['hit_rate_percent']:.1f}%")
"""

import asyncio
import json
import time
from collections import OrderedDict
from typing import Any, Dict, Optional, Tuple

from src.utils.logging import get_logger, log_event

logger = get_logger(__name__)


_cache_metrics = {
    "hits": 0,
    "misses": 0,
    "sets": 0,
    "evictions_lru": 0,
    "evictions_ttl": 0,
    "invalidations_all": 0,
    "invalidations_pattern": 0,
}


def get_cache_metrics() -> Dict[str, int]:
    """Return current cache metrics"""
    return _cache_metrics.copy()


def reset_cache_metrics() -> None:
    """Reset cache metrics to zero"""
    global _cache_metrics
    _cache_metrics = {key: 0 for key in _cache_metrics}


class CacheManager:
    """LRU Cache Manager with TTL support"""

    def __init__(self, max_entries: int = 50, ttl_seconds: int = 60) -> None:
        """Initialise the cache manager"""
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, Tuple[str, float]] = OrderedDict()
        self._lock = asyncio.Lock()

    def get_cache_key(self, command: str, args: Dict) -> str:
        """Generate a unique cache key based on command and arguments"""
        key_data = {
            "command": command,
            "table": args.get("table", "inbox"),
            "limit": args.get("limit", 50),
            "keyword": args.get("keyword", ""),
            "id": args.get("id", ""),
            "flagged": args.get("flagged", None),
        }

        return json.dumps(key_data, sort_keys=True)

    async def get(self, cache_key: str) -> Optional[Tuple[str, float]]:
        """Retrieve cached output if valid"""
        async with self._lock:
            if cache_key not in self._cache:
                _cache_metrics["misses"] += 1
                return None

            output, timestamp = self._cache[cache_key]
            age = time.time() - timestamp

            if age > self.ttl_seconds:
                del self._cache[cache_key]
                _cache_metrics["evictions_ttl"] += 1
                logger.debug(f"Cache entry expired (TTL) for key: {cache_key[:50]}...")
                return None

            self._cache.move_to_end(cache_key)
            _cache_metrics["hits"] += 1
            logger.debug(f"Cache hit (age: {age:.1f}s)")
            return output, age

    async def set(self, cache_key: str, output: str) -> None:
        """Store output in cache with LRU eviction"""
        async with self._lock:
            if len(self._cache) >= self.max_entries and cache_key not in self._cache:
                self._cache.popitem(last=False)
                _cache_metrics["evictions_lru"] += 1
                logger.debug("Oldest cache entry evicted (LRU)")

            self._cache[cache_key] = (output, time.time())
            _cache_metrics["sets"] += 1
            logger.debug(
                f"Cache entry set ({len(self._cache)}/{self.max_entries} entries)"
            )

    async def invalidate_all(self) -> None:
        """Invalidate all cache entries"""
        async with self._lock:
            num_entries = len(self._cache)
            self._cache.clear()
            _cache_metrics["invalidations_all"] += 1
            logger.info(
                f"All cache entries invalidated ({num_entries} entries removed)"
            )
            log_event("cache_cleared", {"entries_removed": num_entries})

    async def invalidate_by_pattern(self, pattern: str) -> int:
        """Invalidate cache entries matching a pattern"""
        async with self._lock:
            keys_to_remove = [key for key in self._cache if pattern in key]
            for key in keys_to_remove:
                del self._cache[key]

            if keys_to_remove:
                _cache_metrics["invalidations_pattern"] += 1
                logger.info(
                    f"Cache entries invalidated by pattern '{pattern}': {len(keys_to_remove)} entries"
                )
                log_event(
                    "cache_invalidated_pattern",
                    {"pattern": pattern, "entries_removed": len(keys_to_remove)},
                )

            return len(keys_to_remove)

    async def invalidate_table(self, table: str) -> int:
        """Invalidate cache entries for a specific table"""
        pattern = f'"table": "{table}"'
        return await self.invalidate_by_pattern(pattern)

    async def invalidate_email(self, email_id: str, table: Optional[str] = None) -> int:
        """Invalidate cache entries for a specific email ID, optionally within a specific table"""
        pattern = f'"id": "{email_id}"'
        count = await self.invalidate_by_pattern(pattern)

        if table:
            count += await self.invalidate_table(table)

        return count

    async def invalidate_search(self, keyword: str) -> int:
        """Invalidate cache entries for a specific search keyword"""
        pattern = f'"keyword": "{keyword}"'
        return await self.invalidate_by_pattern(pattern)

    async def invalidate_command(self, command: str) -> int:
        """Invalidate cache entries for a specific command"""
        pattern = f'"command": "{command}"'
        return await self.invalidate_by_pattern(pattern)

    async def get_stats(self) -> Dict[str, Any]:
        """Return cache statistics"""
        async with self._lock:
            total_requests = _cache_metrics["hits"] + _cache_metrics["misses"]
            hit_rate = (
                (_cache_metrics["hits"] / total_requests) * 100
                if total_requests > 0
                else 0.0
            )

            return {
                "entries": len(self._cache),
                "max_entries": self.max_entries,
                "ttl_seconds": self.ttl_seconds,
                "usage_percent": (len(self._cache) / self.max_entries) * 100,
                "hit_rate_percent": hit_rate,
                "metrics": get_cache_metrics(),
            }

    def __len__(self) -> int:
        """Return the number of entries in the cache."""
        return len(self._cache)
