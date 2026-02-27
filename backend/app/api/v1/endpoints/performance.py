"""
Performance monitoring and metrics endpoints.
"""
from fastapi import APIRouter, Depends
from typing import Dict, Any, Optional

from app.core.performance import performance_metrics
from app.core.cache import cache_manager

router = APIRouter()


@router.get("/stats")
async def get_performance_stats() -> Dict[str, Any]:
    """
    Get overall performance statistics.

    Returns:
        Dictionary with performance metrics including:
        - Request latencies
        - Cache hit rates
        - Slow queries
        - Slowest endpoints
    """
    return {
        "cache": get_cache_performance(),
        "endpoints": performance_metrics.get_slowest_endpoints(limit=10),
        "slow_queries": performance_metrics.get_slow_queries(limit=10),
        "summary": {
            "total_tracked_endpoints": len(performance_metrics.endpoint_metrics),
            "metrics_retention_minutes": performance_metrics.retention_minutes
        }
    }


@router.get("/endpoints")
async def get_endpoint_performance(
    endpoint: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get performance metrics for API endpoints.

    Args:
        endpoint: Optional specific endpoint to get stats for

    Returns:
        Performance metrics including p50, p95, p99 latencies
    """
    return performance_metrics.get_endpoint_stats(endpoint)


@router.get("/cache")
async def get_cache_performance() -> Dict[str, Any]:
    """
    Get cache performance statistics.

    Returns:
        Cache hit rate, total requests, and Redis stats
    """
    # Get application-level cache stats
    app_cache_stats = performance_metrics.get_cache_stats()

    # Get Redis-level stats
    redis_stats = cache_manager.get_stats()

    return {
        "application_level": app_cache_stats,
        "redis_level": redis_stats,
        "recommendations": _get_cache_recommendations(app_cache_stats)
    }


@router.get("/slow-queries")
async def get_slow_queries(
    limit: int = 20,
    threshold_ms: float = 1000
) -> Dict[str, Any]:
    """
    Get slow database queries.

    Args:
        limit: Maximum number of queries to return
        threshold_ms: Minimum duration to be considered slow

    Returns:
        List of slow queries with timing information
    """
    queries = performance_metrics.get_slow_queries(limit, threshold_ms)

    return {
        "slow_queries": queries,
        "total_slow_queries": len(queries),
        "threshold_ms": threshold_ms,
        "recommendations": _get_query_recommendations(queries)
    }


@router.post("/reset")
async def reset_performance_metrics() -> Dict[str, str]:
    """
    Reset all performance metrics.
    Use with caution - only for testing or after deployment.

    Returns:
        Confirmation message
    """
    performance_metrics.reset()
    return {
        "message": "Performance metrics reset successfully",
        "note": "Historical data has been cleared"
    }


@router.get("/health-check")
async def performance_health_check() -> Dict[str, Any]:
    """
    Check if application performance meets targets.

    Returns:
        Health status with pass/fail for each metric
    """
    cache_stats = performance_metrics.get_cache_stats()
    slowest_endpoints = performance_metrics.get_slowest_endpoints(limit=5)

    # Define performance targets
    targets = {
        "cache_hit_rate_percent": 70.0,
        "p95_latency_ms": 1000,
        "p99_latency_ms": 3000,
        "error_rate_percent": 1.0
    }

    # Check cache hit rate
    cache_healthy = cache_stats["hit_rate_percent"] >= targets["cache_hit_rate_percent"]

    # Check endpoint latencies
    endpoints_healthy = True
    unhealthy_endpoints = []

    for endpoint_stat in slowest_endpoints:
        if endpoint_stat["p95_duration_ms"] > targets["p95_latency_ms"]:
            endpoints_healthy = False
            unhealthy_endpoints.append({
                "endpoint": endpoint_stat["endpoint"],
                "p95_ms": endpoint_stat["p95_duration_ms"],
                "target_ms": targets["p95_latency_ms"]
            })

    overall_healthy = cache_healthy and endpoints_healthy

    return {
        "status": "healthy" if overall_healthy else "degraded",
        "targets": targets,
        "checks": {
            "cache_performance": {
                "status": "pass" if cache_healthy else "fail",
                "current_hit_rate_percent": cache_stats["hit_rate_percent"],
                "target_hit_rate_percent": targets["cache_hit_rate_percent"]
            },
            "endpoint_performance": {
                "status": "pass" if endpoints_healthy else "fail",
                "unhealthy_endpoints": unhealthy_endpoints
            }
        },
        "recommendations": _get_health_recommendations(
            cache_healthy,
            endpoints_healthy,
            unhealthy_endpoints
        )
    }


def _get_cache_recommendations(cache_stats: Dict[str, Any]) -> list:
    """Generate cache optimization recommendations."""
    recommendations = []

    hit_rate = cache_stats.get("hit_rate_percent", 0)

    if hit_rate < 50:
        recommendations.append({
            "priority": "high",
            "category": "cache",
            "message": "Cache hit rate is critically low (<50%). Consider increasing TTLs for stable data."
        })
    elif hit_rate < 70:
        recommendations.append({
            "priority": "medium",
            "category": "cache",
            "message": "Cache hit rate is below target (70%). Review cache key strategies and TTL settings."
        })

    if cache_stats.get("total_requests", 0) == 0:
        recommendations.append({
            "priority": "info",
            "category": "cache",
            "message": "No cache requests recorded yet. Metrics will be available after API usage."
        })

    return recommendations


def _get_query_recommendations(queries: list) -> list:
    """Generate database query optimization recommendations."""
    recommendations = []

    if not queries:
        return [{
            "priority": "info",
            "category": "database",
            "message": "No slow queries detected. Database performance is good."
        }]

    # Check for very slow queries (>5s)
    very_slow = [q for q in queries if q["duration_ms"] > 5000]
    if very_slow:
        recommendations.append({
            "priority": "high",
            "category": "database",
            "message": f"{len(very_slow)} queries taking >5 seconds. Add database indexes or optimize queries."
        })

    # Check for moderately slow queries (1-5s)
    slow = [q for q in queries if 1000 < q["duration_ms"] <= 5000]
    if slow:
        recommendations.append({
            "priority": "medium",
            "category": "database",
            "message": f"{len(slow)} queries taking 1-5 seconds. Consider adding indexes."
        })

    return recommendations


def _get_health_recommendations(
    cache_healthy: bool,
    endpoints_healthy: bool,
    unhealthy_endpoints: list
) -> list:
    """Generate performance health recommendations."""
    recommendations = []

    if not cache_healthy:
        recommendations.append({
            "priority": "high",
            "category": "cache",
            "action": "Review and increase cache TTLs for historical/stable data",
            "details": "Target: 70%+ cache hit rate for cost optimization"
        })

    if not endpoints_healthy:
        for endpoint_info in unhealthy_endpoints:
            recommendations.append({
                "priority": "high",
                "category": "endpoint",
                "action": f"Optimize endpoint: {endpoint_info['endpoint']}",
                "details": f"Current p95: {endpoint_info['p95_ms']}ms, Target: {endpoint_info['target_ms']}ms"
            })

    if cache_healthy and endpoints_healthy:
        recommendations.append({
            "priority": "info",
            "category": "overall",
            "action": "All performance targets met",
            "details": "Continue monitoring for performance regressions"
        })

    return recommendations
