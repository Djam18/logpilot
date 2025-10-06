"""Redis-backed query result cache.

Caches serialized query results (list[LogEntry]) under a content-addressed
key derived from the query parameters, allowing repeated identical queries
against the same log file to be served from cache without re-parsing.

Key schema:
    logpilot:cache:{sha256(path + params)}

TTL defaults to 300 seconds (5 minutes). Set LOGPILOT_CACHE_TTL in the
environment to override.

Usage::

    from logpilot.cache.redis_cache import QueryCache

    cache = QueryCache(url="redis://localhost:6379/0", ttl=600)

    results = cache.get("my-query-key")
    if results is None:
        results = run_expensive_query(...)
        cache.set("my-query-key", results)
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def make_cache_key(path: str, params: dict[str, Any]) -> str:
    """Derive a stable cache key from a file path and query parameters."""
    raw = json.dumps({"path": path, "params": params}, sort_keys=True)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:32]
    return f"logpilot:cache:{digest}"


class QueryCache:
    """Redis-backed cache for parsed log query results.

    Gracefully degrades to a no-op when the Redis client is unavailable —
    the caller never needs to handle cache errors.

    Args:
        url:  Redis connection URL (redis://host:port/db).
        ttl:  Time-to-live in seconds for cached entries (default: 300).
    """

    def __init__(self, url: str = "redis://localhost:6379/0", ttl: int = 300) -> None:
        self._url = url
        self._ttl = ttl
        self._client: Any = None
        self._connect()

    def _connect(self) -> None:
        try:
            import redis  # type: ignore[import-untyped]

            self._client = redis.Redis.from_url(self._url, decode_responses=True)
            self._client.ping()
            logger.debug("Redis cache connected: %s", self._url)
        except Exception as exc:
            logger.warning("Redis unavailable — caching disabled: %s", exc)
            self._client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str) -> list[dict[str, Any]] | None:
        """Return cached results for key, or None on miss / error."""
        if self._client is None:
            return None
        try:
            raw = self._client.get(key)
            if raw is None:
                return None
            return json.loads(raw)  # type: ignore[return-value]
        except Exception as exc:
            logger.warning("Cache get failed for key %r: %s", key, exc)
            return None

    def set(self, key: str, entries: list[dict[str, Any]]) -> bool:
        """Serialize and store entries under key with the configured TTL.

        Returns True on success, False on error.
        """
        if self._client is None:
            return False
        try:
            self._client.setex(key, self._ttl, json.dumps(entries, default=str))
            return True
        except Exception as exc:
            logger.warning("Cache set failed for key %r: %s", key, exc)
            return False

    def invalidate(self, key: str) -> bool:
        """Delete a specific cache key. Returns True if the key existed."""
        if self._client is None:
            return False
        try:
            return bool(self._client.delete(key))
        except Exception as exc:
            logger.warning("Cache invalidate failed for key %r: %s", key, exc)
            return False

    def flush(self, pattern: str = "logpilot:cache:*") -> int:
        """Delete all cache keys matching pattern.

        Returns the number of keys deleted.
        """
        if self._client is None:
            return 0
        try:
            keys = self._client.keys(pattern)
            if not keys:
                return 0
            return self._client.delete(*keys)
        except Exception as exc:
            logger.warning("Cache flush failed: %s", exc)
            return 0

    @property
    def available(self) -> bool:
        """True when the Redis connection is healthy."""
        return self._client is not None
