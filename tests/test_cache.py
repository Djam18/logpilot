"""Tests for the Redis query cache (no live Redis required)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from logpilot.cache.redis_cache import QueryCache, make_cache_key


class TestMakeCacheKey:
    def test_deterministic(self) -> None:
        k1 = make_cache_key("/var/log/app.log", {"pattern": "error"})
        k2 = make_cache_key("/var/log/app.log", {"pattern": "error"})
        assert k1 == k2

    def test_different_params_different_keys(self) -> None:
        k1 = make_cache_key("/var/log/app.log", {"pattern": "error"})
        k2 = make_cache_key("/var/log/app.log", {"pattern": "warn"})
        assert k1 != k2

    def test_different_paths_different_keys(self) -> None:
        k1 = make_cache_key("/a.log", {})
        k2 = make_cache_key("/b.log", {})
        assert k1 != k2

    def test_key_prefix(self) -> None:
        key = make_cache_key("/app.log", {})
        assert key.startswith("logpilot:cache:")

    def test_params_order_independent(self) -> None:
        k1 = make_cache_key("/a.log", {"b": 2, "a": 1})
        k2 = make_cache_key("/a.log", {"a": 1, "b": 2})
        assert k1 == k2


class TestQueryCacheNoRedis:
    """Tests that pass even when Redis is not running."""

    def _disabled_cache(self) -> QueryCache:
        """Return a QueryCache whose Redis connection is disabled."""
        with patch("logpilot.cache.redis_cache.QueryCache._connect"):
            cache = QueryCache()
            cache._client = None
        return cache

    def test_available_false_when_no_redis(self) -> None:
        cache = self._disabled_cache()
        assert not cache.available

    def test_get_returns_none_when_disabled(self) -> None:
        cache = self._disabled_cache()
        assert cache.get("any-key") is None

    def test_set_returns_false_when_disabled(self) -> None:
        cache = self._disabled_cache()
        assert cache.set("any-key", [{"a": 1}]) is False

    def test_invalidate_returns_false_when_disabled(self) -> None:
        cache = self._disabled_cache()
        assert cache.invalidate("any-key") is False

    def test_flush_returns_zero_when_disabled(self) -> None:
        cache = self._disabled_cache()
        assert cache.flush() == 0


class TestQueryCacheMocked:
    """Tests using a mocked Redis client."""

    def _cache_with_mock_redis(self) -> tuple[QueryCache, MagicMock]:
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        with patch("logpilot.cache.redis_cache.QueryCache._connect"):
            cache = QueryCache()
            cache._client = mock_redis
        return cache, mock_redis

    def test_get_returns_deserialized_entries(self) -> None:
        cache, mock_redis = self._cache_with_mock_redis()
        mock_redis.get.return_value = '[{"level": "ERROR"}]'
        result = cache.get("test-key")
        assert result == [{"level": "ERROR"}]

    def test_get_returns_none_on_cache_miss(self) -> None:
        cache, mock_redis = self._cache_with_mock_redis()
        mock_redis.get.return_value = None
        assert cache.get("missing-key") is None

    def test_set_calls_setex_with_ttl(self) -> None:
        cache, mock_redis = self._cache_with_mock_redis()
        cache._ttl = 300
        entries = [{"level": "INFO", "message": "ok"}]
        result = cache.set("test-key", entries)
        assert result is True
        mock_redis.setex.assert_called_once()
        args = mock_redis.setex.call_args[0]
        assert args[0] == "test-key"
        assert args[1] == 300

    def test_invalidate_calls_delete(self) -> None:
        cache, mock_redis = self._cache_with_mock_redis()
        mock_redis.delete.return_value = 1
        result = cache.invalidate("test-key")
        assert result is True
        mock_redis.delete.assert_called_with("test-key")

    def test_flush_deletes_matching_keys(self) -> None:
        cache, mock_redis = self._cache_with_mock_redis()
        mock_redis.keys.return_value = ["logpilot:cache:abc", "logpilot:cache:def"]
        mock_redis.delete.return_value = 2
        count = cache.flush()
        assert count == 2

    def test_get_handles_redis_error_gracefully(self) -> None:
        cache, mock_redis = self._cache_with_mock_redis()
        mock_redis.get.side_effect = Exception("Redis error")
        # Should return None, not raise
        assert cache.get("bad-key") is None

    def test_set_handles_redis_error_gracefully(self) -> None:
        cache, mock_redis = self._cache_with_mock_redis()
        mock_redis.setex.side_effect = Exception("Redis error")
        assert cache.set("bad-key", []) is False
