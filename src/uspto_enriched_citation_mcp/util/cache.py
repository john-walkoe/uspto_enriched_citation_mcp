"""Response caching with TTL and LRU strategies.

Provides performance optimization through intelligent caching:
- TTL Cache: Time-based expiration for relatively static data (fields)
- LRU Cache: Size-based eviction for dynamic data (search results)
- Thread-safe operations
- Configurable sizes and TTLs
"""

import time
import hashlib
import json
import threading
from typing import Any, Optional, Dict
from collections import OrderedDict
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Single cache entry with metadata."""

    key: str
    value: Any
    created_at: float
    expires_at: Optional[float]
    hit_count: int = 0
    last_accessed: float = 0.0

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def access(self) -> None:
        """Record an access to this entry."""
        self.hit_count += 1
        self.last_accessed = time.time()


class CacheStatsMixin:
    """
    Mixin providing common cache statistics functionality.

    Provides shared get_stats() method for cache implementations.
    Requires subclass to have: _lock, _hits, _misses, _cache, max_size
    """

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with hits, misses, size, hit_rate
        """
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0.0

            return {
                "hits": self._hits,
                "misses": self._misses,
                "total_requests": total,
                "hit_rate_percent": round(hit_rate, 2),
                "current_size": len(self._cache),
                "max_size": self.max_size,
                "fill_percent": (
                    round(len(self._cache) / self.max_size * 100, 2)
                    if self.max_size > 0
                    else 0.0
                ),
            }


class TTLCache(CacheStatsMixin):
    """
    Time-to-live cache with automatic expiration.

    Best for data that changes infrequently but needs periodic refresh.
    Examples: API field definitions, configuration data.
    """

    def __init__(self, default_ttl_seconds: int = 3600, max_size: int = 100):
        """
        Initialize TTL cache.

        Args:
            default_ttl_seconds: Default time-to-live in seconds (default: 1 hour)
            max_size: Maximum number of entries (prevents unbounded growth)
        """
        self.default_ttl = default_ttl_seconds
        self.max_size = max_size
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str, allow_stale: bool = False) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key
            allow_stale: If True, return expired entries (for graceful degradation)

        Returns:
            Cached value if exists and not expired, None otherwise
            If allow_stale=True, returns even expired entries
        """
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._misses += 1
                logger.debug(f"Cache miss: {key}")
                return None

            if entry.is_expired():
                if allow_stale:
                    # Return stale data for graceful degradation
                    entry.access()
                    self._hits += 1
                    logger.warning(f"Cache stale (degraded mode): {key} (age: {time.time() - entry.created_at:.0f}s)")
                    return entry.value
                else:
                    # Remove expired entry
                    del self._cache[key]
                    self._misses += 1
                    logger.debug(f"Cache expired: {key}")
                    return None

            # Record access and return value
            entry.access()
            self._hits += 1
            logger.debug(f"Cache hit: {key} (hits: {entry.hit_count})")
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """
        Store value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time-to-live in seconds (uses default if None)
        """
        with self._lock:
            # Enforce max size by removing oldest entry
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict_oldest()

            ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
            now = time.time()
            expires_at = now + ttl if ttl > 0 else None

            entry = CacheEntry(
                key=key,
                value=value,
                created_at=now,
                expires_at=expires_at,
                last_accessed=now,
            )

            self._cache[key] = entry
            logger.debug(f"Cache set: {key} (TTL: {ttl}s, size: {len(self._cache)})")

    def _evict_oldest(self) -> None:
        """Evict the oldest entry to make room."""
        if not self._cache:
            return

        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].created_at)
        del self._cache[oldest_key]
        logger.debug(f"Cache evicted (oldest): {oldest_key}")

    def invalidate(self, key: str) -> bool:
        """
        Remove entry from cache.

        Args:
            key: Cache key to invalidate

        Returns:
            True if entry was removed, False if not found
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Cache invalidated: {key}")
                return True
            return False

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cache cleared: {count} entries removed")

    def get_with_metadata(self, key: str, allow_stale: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get value with cache metadata (for graceful degradation).

        Args:
            key: Cache key
            allow_stale: If True, return expired entries

        Returns:
            Dict with 'value', 'is_stale', 'age_seconds', 'hit_count' or None
        """
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._misses += 1
                return None

            is_stale = entry.is_expired()

            if is_stale and not allow_stale:
                del self._cache[key]
                self._misses += 1
                return None

            # Record access
            entry.access()
            self._hits += 1

            age_seconds = time.time() - entry.created_at

            return {
                "value": entry.value,
                "is_stale": is_stale,
                "age_seconds": round(age_seconds, 1),
                "hit_count": entry.hit_count,
                "created_at": entry.created_at,
                "expires_at": entry.expires_at,
            }

    # get_stats() inherited from CacheStatsMixin


class LRUCache(CacheStatsMixin):
    """
    Least Recently Used cache with size-based eviction.

    Best for data that's frequently accessed but memory-limited.
    Examples: Search results, computed values.
    """

    def __init__(self, max_size: int = 100):
        """
        Initialize LRU cache.

        Args:
            max_size: Maximum number of entries
        """
        self.max_size = max_size
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache and move to end (most recently used).

        Args:
            key: Cache key

        Returns:
            Cached value if exists, None otherwise
        """
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._misses += 1
                logger.debug(f"LRU miss: {key}")
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.access()
            self._hits += 1
            logger.debug(f"LRU hit: {key} (hits: {entry.hit_count})")
            return entry.value

    def set(self, key: str, value: Any) -> None:
        """
        Store value in cache.

        Args:
            key: Cache key
            value: Value to cache
        """
        with self._lock:
            # If key exists, update and move to end
            if key in self._cache:
                self._cache.move_to_end(key)
                entry = self._cache[key]
                entry.value = value
                entry.last_accessed = time.time()
                logger.debug(f"LRU updated: {key}")
                return

            # Add new entry
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                expires_at=None,
                last_accessed=time.time(),
            )

            self._cache[key] = entry

            # Evict least recently used if over size
            if len(self._cache) > self.max_size:
                evicted_key, evicted_entry = self._cache.popitem(last=False)
                logger.debug(
                    f"LRU evicted: {evicted_key} (hits: {evicted_entry.hit_count})"
                )

            logger.debug(f"LRU set: {key} (size: {len(self._cache)}/{self.max_size})")

    def invalidate(self, key: str) -> bool:
        """
        Remove entry from cache.

        Args:
            key: Cache key to invalidate

        Returns:
            True if entry was removed, False if not found
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"LRU invalidated: {key}")
                return True
            return False

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"LRU cache cleared: {count} entries removed")

    # get_stats() inherited from CacheStatsMixin


def generate_cache_key(prefix: str, *args, **kwargs) -> str:
    """
    Generate a deterministic cache key from arguments.

    Args:
        prefix: Key prefix (e.g., 'search', 'fields')
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Deterministic cache key string
    """
    # Create a deterministic representation of arguments
    key_parts = [prefix]

    # Add positional args
    for arg in args:
        if isinstance(arg, (str, int, float, bool)):
            key_parts.append(str(arg))
        else:
            # For complex types, use JSON serialization
            key_parts.append(json.dumps(arg, sort_keys=True))

    # Add keyword args (sorted for determinism)
    for k in sorted(kwargs.keys()):
        v = kwargs[k]
        if isinstance(v, (str, int, float, bool)):
            key_parts.append(f"{k}={v}")
        else:
            key_parts.append(f"{k}={json.dumps(v, sort_keys=True)}")

    # Create hash for long keys
    key_str = ":".join(key_parts)
    if len(key_str) > 200:
        # Use hash for very long keys
        key_hash = hashlib.sha256(key_str.encode()).hexdigest()[:16]
        return f"{prefix}:hash:{key_hash}"

    return key_str


# Global cache instances
_fields_cache: Optional[TTLCache] = None
_search_cache: Optional[LRUCache] = None


def get_fields_cache(ttl_seconds: int = 3600, max_size: int = 10) -> TTLCache:
    """
    Get or create the global fields cache.

    Args:
        ttl_seconds: TTL for field definitions (default: 1 hour)
        max_size: Max entries (default: 10, fields API has limited endpoints)

    Returns:
        TTLCache instance
    """
    global _fields_cache
    if _fields_cache is None:
        _fields_cache = TTLCache(default_ttl_seconds=ttl_seconds, max_size=max_size)
        logger.info(f"Fields cache initialized (TTL: {ttl_seconds}s, max: {max_size})")
    return _fields_cache


def get_search_cache(max_size: int = 100) -> LRUCache:
    """
    Get or create the global search results cache.

    Args:
        max_size: Max cached search results (default: 100)

    Returns:
        LRUCache instance
    """
    global _search_cache
    if _search_cache is None:
        _search_cache = LRUCache(max_size=max_size)
        logger.info(f"Search cache initialized (max: {max_size})")
    return _search_cache


def clear_all_caches() -> None:
    """Clear all global caches."""
    global _fields_cache, _search_cache

    if _fields_cache:
        _fields_cache.clear()
    if _search_cache:
        _search_cache.clear()

    logger.info("All caches cleared")


def get_all_cache_stats() -> Dict[str, Dict[str, Any]]:
    """
    Get statistics from all caches.

    Returns:
        Dict with stats for each cache type
    """
    stats = {}

    if _fields_cache:
        stats["fields_cache"] = _fields_cache.get_stats()
    if _search_cache:
        stats["search_cache"] = _search_cache.get_stats()

    return stats
