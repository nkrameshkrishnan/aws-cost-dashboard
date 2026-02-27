"""
Performance profiling and monitoring utilities.
Tracks API response times, database queries, and cache performance.
"""
import time
import logging
from typing import Callable, Optional, Dict, Any
from functools import wraps
from collections import defaultdict
from datetime import datetime, timedelta
import statistics

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """
    In-memory performance metrics tracker.
    Stores request timing, database query performance, and cache stats.
    """

    def __init__(self, retention_minutes: int = 60):
        """
        Initialize metrics tracker.

        Args:
            retention_minutes: How long to keep metrics in memory
        """
        self.retention_minutes = retention_minutes
        self.endpoint_metrics = defaultdict(list)  # {endpoint: [durations]}
        self.slow_queries = []  # List of slow queries
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "total_requests": 0
        }
        self._last_cleanup = datetime.now()

    def record_request(self, endpoint: str, method: str, duration_ms: float, status_code: int):
        """Record an API request performance metric."""
        key = f"{method} {endpoint}"
        self.endpoint_metrics[key].append({
            "duration_ms": duration_ms,
            "timestamp": datetime.now(),
            "status_code": status_code
        })

        # Periodic cleanup
        self._cleanup_old_metrics()

    def record_cache_hit(self):
        """Record a cache hit."""
        self.cache_stats["hits"] += 1
        self.cache_stats["total_requests"] += 1

    def record_cache_miss(self):
        """Record a cache miss."""
        self.cache_stats["misses"] += 1
        self.cache_stats["total_requests"] += 1

    def record_slow_query(self, query: str, duration_ms: float, params: Optional[Dict] = None):
        """Record a slow database query."""
        self.slow_queries.append({
            "query": query,
            "duration_ms": duration_ms,
            "params": params,
            "timestamp": datetime.now()
        })

        # Keep only recent slow queries
        if len(self.slow_queries) > 100:
            self.slow_queries = self.slow_queries[-100:]

    def get_endpoint_stats(self, endpoint: Optional[str] = None) -> Dict[str, Any]:
        """
        Get performance statistics for endpoints.

        Args:
            endpoint: Specific endpoint to get stats for, or None for all

        Returns:
            Dictionary with performance statistics
        """
        if endpoint:
            return self._calculate_stats(endpoint, self.endpoint_metrics.get(endpoint, []))

        # Return stats for all endpoints
        stats = {}
        for ep, metrics in self.endpoint_metrics.items():
            stats[ep] = self._calculate_stats(ep, metrics)

        return stats

    def _calculate_stats(self, endpoint: str, metrics: list) -> Dict[str, Any]:
        """Calculate statistics for a set of metrics."""
        if not metrics:
            return {
                "endpoint": endpoint,
                "total_requests": 0,
                "avg_duration_ms": 0,
                "min_duration_ms": 0,
                "max_duration_ms": 0,
                "p50_duration_ms": 0,
                "p95_duration_ms": 0,
                "p99_duration_ms": 0
            }

        durations = [m["duration_ms"] for m in metrics]
        sorted_durations = sorted(durations)

        return {
            "endpoint": endpoint,
            "total_requests": len(metrics),
            "avg_duration_ms": round(statistics.mean(durations), 2),
            "min_duration_ms": round(min(durations), 2),
            "max_duration_ms": round(max(durations), 2),
            "p50_duration_ms": round(self._percentile(sorted_durations, 50), 2),
            "p95_duration_ms": round(self._percentile(sorted_durations, 95), 2),
            "p99_duration_ms": round(self._percentile(sorted_durations, 99), 2),
            "error_rate": self._calculate_error_rate(metrics)
        }

    @staticmethod
    def _percentile(sorted_data: list, percentile: float) -> float:
        """Calculate percentile from sorted data."""
        if not sorted_data:
            return 0.0
        index = (len(sorted_data) - 1) * (percentile / 100)
        lower = int(index)
        upper = lower + 1
        weight = index - lower

        if upper >= len(sorted_data):
            return sorted_data[-1]

        return sorted_data[lower] * (1 - weight) + sorted_data[upper] * weight

    @staticmethod
    def _calculate_error_rate(metrics: list) -> float:
        """Calculate error rate (5xx responses)."""
        if not metrics:
            return 0.0
        errors = sum(1 for m in metrics if m.get("status_code", 200) >= 500)
        return round((errors / len(metrics)) * 100, 2)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        total = self.cache_stats["total_requests"]
        hits = self.cache_stats["hits"]
        misses = self.cache_stats["misses"]

        hit_rate = (hits / total * 100) if total > 0 else 0.0

        return {
            "total_requests": total,
            "hits": hits,
            "misses": misses,
            "hit_rate_percent": round(hit_rate, 2),
            "target_hit_rate_percent": 70.0,
            "meets_target": hit_rate >= 70.0
        }

    def get_slow_queries(self, limit: int = 20, threshold_ms: float = 1000) -> list:
        """
        Get slow database queries.

        Args:
            limit: Maximum number of queries to return
            threshold_ms: Minimum duration to be considered slow

        Returns:
            List of slow queries sorted by duration
        """
        slow = [q for q in self.slow_queries if q["duration_ms"] >= threshold_ms]
        slow.sort(key=lambda x: x["duration_ms"], reverse=True)
        return slow[:limit]

    def get_slowest_endpoints(self, limit: int = 10) -> list:
        """
        Get slowest API endpoints.

        Args:
            limit: Number of endpoints to return

        Returns:
            List of endpoints sorted by average response time
        """
        endpoint_stats = []
        for endpoint, metrics in self.endpoint_metrics.items():
            if metrics:
                stats = self._calculate_stats(endpoint, metrics)
                endpoint_stats.append(stats)

        # Sort by p95 latency (better metric than average)
        endpoint_stats.sort(key=lambda x: x["p95_duration_ms"], reverse=True)
        return endpoint_stats[:limit]

    def _cleanup_old_metrics(self):
        """Remove metrics older than retention period."""
        now = datetime.now()

        # Only cleanup every 5 minutes
        if (now - self._last_cleanup).total_seconds() < 300:
            return

        cutoff = now - timedelta(minutes=self.retention_minutes)

        for endpoint in list(self.endpoint_metrics.keys()):
            self.endpoint_metrics[endpoint] = [
                m for m in self.endpoint_metrics[endpoint]
                if m["timestamp"] > cutoff
            ]

            # Remove empty entries
            if not self.endpoint_metrics[endpoint]:
                del self.endpoint_metrics[endpoint]

        # Cleanup slow queries
        self.slow_queries = [
            q for q in self.slow_queries
            if q["timestamp"] > cutoff
        ]

        self._last_cleanup = now

    def reset(self):
        """Reset all metrics."""
        self.endpoint_metrics.clear()
        self.slow_queries.clear()
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "total_requests": 0
        }


# Global metrics instance
performance_metrics = PerformanceMetrics()


class PerformanceMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware to track request performance.
    Logs slow requests and collects timing metrics.
    """

    def __init__(self, app, slow_request_threshold_ms: float = 1000):
        """
        Initialize middleware.

        Args:
            app: FastAPI application
            slow_request_threshold_ms: Threshold for logging slow requests
        """
        super().__init__(app)
        self.slow_threshold = slow_request_threshold_ms

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and track timing."""
        # Skip performance tracking for static files and health checks
        if request.url.path in ["/health", "/metrics", "/favicon.ico"]:
            return await call_next(request)

        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Record metrics
        endpoint = request.url.path
        method = request.method
        status_code = response.status_code

        performance_metrics.record_request(endpoint, method, duration_ms, status_code)

        # Log slow requests
        if duration_ms >= self.slow_threshold:
            logger.warning(
                f"Slow request: {method} {endpoint} "
                f"took {duration_ms:.2f}ms (status: {status_code})"
            )

        # Add performance header
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

        return response


def profile_function(threshold_ms: float = 100):
    """
    Decorator to profile function execution time.
    Logs warning if function takes longer than threshold.

    Args:
        threshold_ms: Threshold in milliseconds for logging

    Usage:
        @profile_function(threshold_ms=500)
        def expensive_operation():
            # ... code
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            result = await func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000

            if duration_ms >= threshold_ms:
                logger.warning(
                    f"Function {func.__name__} took {duration_ms:.2f}ms "
                    f"(threshold: {threshold_ms}ms)"
                )

            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000

            if duration_ms >= threshold_ms:
                logger.warning(
                    f"Function {func.__name__} took {duration_ms:.2f}ms "
                    f"(threshold: {threshold_ms}ms)"
                )

            return result

        # Return appropriate wrapper based on function type
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def track_query_performance(query: str, threshold_ms: float = 1000):
    """
    Decorator to track database query performance.
    Records slow queries for analysis.

    Args:
        query: Query description
        threshold_ms: Threshold for slow query logging

    Usage:
        @track_query_performance("Fetch all budgets", threshold_ms=500)
        def get_budgets(db):
            return db.query(Budget).all()
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000

            if duration_ms >= threshold_ms:
                performance_metrics.record_slow_query(query, duration_ms)
                logger.warning(
                    f"Slow query: {query} took {duration_ms:.2f}ms "
                    f"(threshold: {threshold_ms}ms)"
                )

            return result

        return wrapper

    return decorator
