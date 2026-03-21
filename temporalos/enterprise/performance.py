"""Performance utilities — caching, indexing, and optimization helpers.

Provides:
- LRU cache with TTL for expensive operations
- Batch processing utilities
- Query result caching
"""
from __future__ import annotations

import functools
import hashlib
import json
import logging
import time
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class TTLCache:
    """Simple TTL cache (thread-safe for single-threaded async)."""

    def __init__(self, max_size: int = 256, ttl_seconds: float = 300) -> None:
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self.max_size = max_size
        self.ttl = ttl_seconds
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None
        value, expiry = entry
        if time.time() > expiry:
            del self._cache[key]
            self._misses += 1
            return None
        self._hits += 1
        return value

    def set(self, key: str, value: Any) -> None:
        # Evict oldest if at capacity
        if len(self._cache) >= self.max_size and key not in self._cache:
            oldest = min(self._cache, key=lambda k: self._cache[k][1])
            del self._cache[oldest]
        self._cache[key] = (value, time.time() + self.ttl)

    def invalidate(self, key: str) -> bool:
        return self._cache.pop(key, None) is not None

    def clear(self) -> int:
        count = len(self._cache)
        self._cache.clear()
        return count

    @property
    def stats(self) -> Dict[str, Any]:
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / max(total, 1), 3),
        }


def cache_key(*args: Any, **kwargs: Any) -> str:
    """Generate a deterministic cache key from arguments."""
    raw = json.dumps({"args": [str(a) for a in args],
                      "kwargs": {k: str(v) for k, v in sorted(kwargs.items())}},
                     sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


_default_cache = TTLCache()


def cached(ttl: float = 300, max_size: int = 256) -> Callable:
    """Decorator for caching function results with TTL."""
    _cache = TTLCache(max_size=max_size, ttl_seconds=ttl)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = cache_key(func.__name__, *args, **kwargs)
            result = _cache.get(key)
            if result is not None:
                return result
            result = func(*args, **kwargs)
            _cache.set(key, result)
            return result
        wrapper._cache = _cache  # type: ignore
        return wrapper
    return decorator


def batch_process(items: list, batch_size: int, processor: Callable) -> list:
    """Process items in batches."""
    results = []
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        batch_result = processor(batch)
        if isinstance(batch_result, list):
            results.extend(batch_result)
        else:
            results.append(batch_result)
    return results
