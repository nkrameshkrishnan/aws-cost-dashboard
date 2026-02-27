"""
Redis cache manager for caching AWS API responses.
Implements intelligent TTL strategies to minimize AWS Cost Explorer API costs.
"""
import redis
import json
import hashlib
import logging
from typing import Any, Optional, Callable
from functools import wraps

from app.config import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Redis-based caching manager with TTL strategies.
    Caches expensive AWS API calls to reduce costs.
    """

    def __init__(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            logger.info("Redis connection established successfully")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None

    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """
        Generate a unique cache key from prefix and parameters.

        Args:
            prefix: Key prefix (e.g., 'costs:daily')
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Unique cache key
        """
        # Create a deterministic hash of arguments
        key_data = {
            'args': args,
            'kwargs': sorted(kwargs.items())
        }
        key_hash = hashlib.md5(
            json.dumps(key_data, sort_keys=True).encode()
        ).hexdigest()

        return f"{prefix}:{key_hash}"

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        if not self.redis_client:
            return None

        try:
            value = self.redis_client.get(key)
            if value:
                logger.debug(f"Cache hit: {key}")
                # Track cache hit for performance metrics
                try:
                    from app.core.performance import performance_metrics
                    performance_metrics.record_cache_hit()
                except ImportError:
                    pass
                return json.loads(value)
            else:
                logger.debug(f"Cache miss: {key}")
                # Track cache miss for performance metrics
                try:
                    from app.core.performance import performance_metrics
                    performance_metrics.record_cache_miss()
                except ImportError:
                    pass
                return None
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {e}")
            return None

    def set(
        self,
        key: str,
        value: Any,
        ttl: int = 300
    ) -> bool:
        """
        Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds

        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            return False

        try:
            serialized = json.dumps(value)
            self.redis_client.setex(key, ttl, serialized)
            logger.debug(f"Cached key {key} with TTL {ttl}s")
            return True
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        Delete a specific key from cache.

        Args:
            key: Cache key to delete

        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            return False

        try:
            self.redis_client.delete(key)
            logger.debug(f"Deleted cache key: {key}")
            return True
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            return False

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching a pattern.

        Args:
            pattern: Redis key pattern (e.g., 'costs:*')

        Returns:
            Number of keys deleted
        """
        if not self.redis_client:
            return 0

        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"Invalidated {deleted} keys matching pattern: {pattern}")
                return deleted
            return 0
        except Exception as e:
            logger.error(f"Error invalidating pattern {pattern}: {e}")
            return 0

    def get_or_fetch(
        self,
        key: str,
        fetch_func: Callable,
        ttl: int = 300,
        *args,
        **kwargs
    ) -> Any:
        """
        Get value from cache or fetch and cache it if not present.

        Args:
            key: Cache key
            fetch_func: Function to call if cache miss
            ttl: Time to live in seconds
            *args: Arguments for fetch_func
            **kwargs: Keyword arguments for fetch_func

        Returns:
            Cached or fetched value
        """
        # Try to get from cache
        cached_value = self.get(key)
        if cached_value is not None:
            return cached_value

        # Cache miss - fetch data
        logger.info(f"Cache miss, fetching data for key: {key}")
        value = fetch_func(*args, **kwargs)

        # Cache the result
        if value is not None:
            self.set(key, value, ttl)

        return value

    def clear_all(self) -> bool:
        """
        Clear all cache entries (use with caution).

        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            return False

        try:
            self.redis_client.flushdb()
            logger.warning("Cleared all cache entries")
            return True
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False

    def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        if not self.redis_client:
            return {"connected": False}

        try:
            info = self.redis_client.info()
            return {
                "connected": True,
                "used_memory": info.get('used_memory_human'),
                "total_keys": self.redis_client.dbsize(),
                "hits": info.get('keyspace_hits', 0),
                "misses": info.get('keyspace_misses', 0),
                "hit_rate": self._calculate_hit_rate(
                    info.get('keyspace_hits', 0),
                    info.get('keyspace_misses', 0)
                )
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"connected": True, "error": str(e)}

    @staticmethod
    def _calculate_hit_rate(hits: int, misses: int) -> float:
        """Calculate cache hit rate percentage."""
        total = hits + misses
        if total == 0:
            return 0.0
        return round((hits / total) * 100, 2)


# Global cache manager instance
cache_manager = CacheManager()


def cached(prefix: str, ttl: Optional[int] = None):
    """
    Decorator for caching function results.

    Args:
        prefix: Cache key prefix
        ttl: Time to live in seconds (uses default if None)

    Usage:
        @cached('costs:daily', ttl=300)
        def get_daily_costs(profile, start_date, end_date):
            # ... expensive operation
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            cache_key = cache_manager._generate_key(
                f"{prefix}:{func.__name__}",
                *args,
                **kwargs
            )

            # Determine TTL
            cache_ttl = ttl if ttl is not None else 300

            # Get or fetch
            return cache_manager.get_or_fetch(
                cache_key,
                func,
                cache_ttl,
                *args,
                **kwargs
            )

        return wrapper
    return decorator


def invalidate_cache(pattern: str):
    """
    Invalidate cache entries matching a pattern.

    Args:
        pattern: Redis key pattern

    Usage:
        invalidate_cache('costs:profile123:*')
    """
    return cache_manager.invalidate_pattern(pattern)
