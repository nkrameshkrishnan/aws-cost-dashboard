# Performance Monitoring & Optimization

This document describes the performance monitoring, profiling, and optimization features implemented in the AWS Cost Dashboard backend.

## Table of Contents

1. [Overview](#overview)
2. [Performance Metrics](#performance-metrics)
3. [API Endpoints](#api-endpoints)
4. [Cache Optimization](#cache-optimization)
5. [Database Query Optimization](#database-query-optimization)
6. [Performance Targets](#performance-targets)
7. [Usage Examples](#usage-examples)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The performance monitoring system provides:

- **Real-time request tracking**: Track latency for all API endpoints
- **Cache performance monitoring**: Monitor cache hit rates and optimize TTLs
- **Slow query detection**: Identify and log slow database queries
- **Performance health checks**: Automated checks against performance targets
- **Optimization recommendations**: AI-generated suggestions for improvements

### Key Components

```
backend/app/core/
├── performance.py      # Performance metrics tracking and profiling
├── cache.py           # Enhanced cache with metrics integration
└── database.py        # Database optimization utilities
```

---

## Performance Metrics

### Tracked Metrics

#### API Endpoints
- **Request Count**: Total requests per endpoint
- **Response Times**: Min, max, avg, p50, p95, p99 latencies
- **Error Rate**: Percentage of 5xx responses
- **Slow Requests**: Requests exceeding threshold (default: 1000ms)

#### Cache Performance
- **Hit Rate**: Percentage of cache hits (target: 70%+)
- **Total Requests**: Total cache operations
- **Hits/Misses**: Absolute counts
- **Redis Stats**: Memory usage, key count, connection info

#### Database Queries
- **Slow Queries**: Queries exceeding threshold (default: 1000ms)
- **Query Duration**: Execution time in milliseconds
- **Connection Pool**: Active connections, pool size, overflow

### Retention

Metrics are retained in memory for **60 minutes** by default. Configure via:

```python
from app.core.performance import PerformanceMetrics

metrics = PerformanceMetrics(retention_minutes=120)
```

---

## API Endpoints

All performance endpoints are available at `/api/v1/performance/`.

### Get Performance Statistics

```http
GET /api/v1/performance/stats
```

Returns comprehensive performance overview:

**Response:**
```json
{
  "cache": {
    "application_level": {
      "total_requests": 1500,
      "hits": 1200,
      "misses": 300,
      "hit_rate_percent": 80.0,
      "target_hit_rate_percent": 70.0,
      "meets_target": true
    },
    "redis_level": {
      "connected": true,
      "used_memory": "2.5M",
      "total_keys": 342,
      "hits": 5620,
      "misses": 890,
      "hit_rate": 86.32
    },
    "recommendations": []
  },
  "endpoints": [
    {
      "endpoint": "POST /api/v1/costs/summary",
      "total_requests": 234,
      "avg_duration_ms": 456.78,
      "p50_duration_ms": 423.12,
      "p95_duration_ms": 892.45,
      "p99_duration_ms": 1205.89,
      "error_rate": 0.0
    }
  ],
  "slow_queries": [],
  "summary": {
    "total_tracked_endpoints": 15,
    "metrics_retention_minutes": 60
  }
}
```

### Get Endpoint Performance

```http
GET /api/v1/performance/endpoints?endpoint=/api/v1/costs/summary
```

Get metrics for specific endpoint (or all if no parameter).

### Get Cache Performance

```http
GET /api/v1/performance/cache
```

Detailed cache statistics with optimization recommendations.

### Get Slow Queries

```http
GET /api/v1/performance/slow-queries?limit=20&threshold_ms=1000
```

**Query Parameters:**
- `limit` (int): Max queries to return (default: 20)
- `threshold_ms` (float): Min duration for slow query (default: 1000)

**Response:**
```json
{
  "slow_queries": [
    {
      "query": "SELECT * FROM budgets WHERE account_id = ?",
      "duration_ms": 2345.67,
      "params": {},
      "timestamp": "2026-02-23T19:30:00"
    }
  ],
  "total_slow_queries": 1,
  "threshold_ms": 1000,
  "recommendations": [
    {
      "priority": "medium",
      "category": "database",
      "message": "1 queries taking 1-5 seconds. Consider adding indexes."
    }
  ]
}
```

### Health Check

```http
GET /api/v1/performance/health-check
```

Validates performance against targets:

**Response:**
```json
{
  "status": "healthy",
  "targets": {
    "cache_hit_rate_percent": 70.0,
    "p95_latency_ms": 1000,
    "p99_latency_ms": 3000,
    "error_rate_percent": 1.0
  },
  "checks": {
    "cache_performance": {
      "status": "pass",
      "current_hit_rate_percent": 82.5,
      "target_hit_rate_percent": 70.0
    },
    "endpoint_performance": {
      "status": "pass",
      "unhealthy_endpoints": []
    }
  },
  "recommendations": [
    {
      "priority": "info",
      "category": "overall",
      "action": "All performance targets met",
      "details": "Continue monitoring for performance regressions"
    }
  ]
}
```

### Reset Metrics

```http
POST /api/v1/performance/reset
```

Clear all performance metrics (use with caution).

---

## Cache Optimization

### Current Strategy

The cache system uses Redis with intelligent TTL strategies:

| Data Type | TTL | Rationale |
|-----------|-----|-----------|
| Current month costs | 5 min | Updates throughout day |
| Historical costs | 24 hours | Doesn't change |
| Cost forecasts | 1 hour | Relatively stable |
| Service breakdowns | 15 min | Balance freshness/cost |
| Budget status | 10 min | Needs to be current |
| Audit results | 30 min | Resources change slowly |

### Cache Hit Rate Targets

- **Minimum**: 50% (Critical threshold)
- **Target**: 70%+ (Optimal for cost savings)
- **Excellent**: 85%+ (Exceptional performance)

### Monitoring Cache Performance

```python
from app.core.cache import cache_manager

# Get Redis stats
stats = cache_manager.get_stats()
print(f"Hit rate: {stats['hit_rate']}%")
print(f"Total keys: {stats['total_keys']}")

# Check application-level metrics
from app.core.performance import performance_metrics
cache_stats = performance_metrics.get_cache_stats()
print(f"App hit rate: {cache_stats['hit_rate_percent']}%")
```

### Cache Invalidation

Invalidate cache when data changes:

```python
from app.core.cache import invalidate_cache

# Invalidate all costs for a profile
invalidate_cache('costs:profile123:*')

# Invalidate specific cache key
cache_manager.delete('costs:daily:abc123hash')

# Clear entire cache (use sparingly!)
cache_manager.clear_all()
```

### Cost Savings

With 100 users making 10 Cost Explorer API requests/hour:

- **Without cache**: 24,000 requests/day × $0.01 = **$240/day** = **$7,200/month**
- **With 70% hit rate**: 7,200 requests/day × $0.01 = **$72/day** = **$2,160/month**
- **Savings**: **$5,040/month** (70% reduction)

---

## Database Query Optimization

### Query Performance Tracking

All database queries are automatically tracked. Slow queries (>1 second) are logged and recorded.

### Connection Pooling

Optimized connection pool configuration:

```python
# backend/app/core/database.py
engine = create_engine(
    DATABASE_URL,
    pool_size=10,        # Maintain 10 connections
    max_overflow=20,     # Allow 20 additional connections
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=3600    # Recycle connections after 1 hour
)
```

### Query Optimization Utilities

#### Batch Querying

For large result sets, use batch queries to avoid memory issues:

```python
from app.core.database import query_optimizer

# Query in batches of 1000
for batch in query_optimizer.batch_query(db, query, batch_size=1000):
    process_batch(batch)
```

#### Bulk Insert

Efficiently insert multiple records:

```python
from app.core.database import query_optimizer

records = [
    {"account_id": "123", "name": "Account 1"},
    {"account_id": "456", "name": "Account 2"},
    # ... 1000s of records
]

# Insert in batches
count = query_optimizer.bulk_insert(
    db,
    AWSAccount,
    records,
    batch_size=500
)
print(f"Inserted {count} records")
```

#### Bulk Update

Efficiently update multiple records:

```python
updates = [
    {"id": 1, "status": "active"},
    {"id": 2, "status": "active"},
    # ... many updates
]

count = query_optimizer.bulk_update(
    db,
    Budget,
    updates,
    batch_size=500
)
```

### Index Optimization

Create indexes for frequently queried columns:

```python
# In your SQLAlchemy models
class Budget(Base):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True)
    account_id = Column(String, index=True)  # Add index
    name = Column(String)
    created_at = Column(DateTime, index=True)  # Add index

    # Composite index for common queries
    __table_args__ = (
        Index('idx_budget_account_created', 'account_id', 'created_at'),
    )
```

### Monitor Connection Pool

```python
from app.core.database import get_connection_pool_stats

stats = get_connection_pool_stats()
print(f"Total connections: {stats['total_connections']}")
print(f"Checked out: {stats['checked_out_connections']}")
print(f"Available: {stats['checked_in_connections']}")
```

---

## Performance Targets

### Response Time Targets

| Metric | Target | Critical |
|--------|--------|----------|
| P50 (Median) | <500ms | <1000ms |
| P95 | <1000ms | <2000ms |
| P99 | <3000ms | <5000ms |
| Average | <750ms | <1500ms |

### Cache Targets

- **Hit Rate**: >70% (minimum 50%)
- **Memory Usage**: <1GB for typical workload
- **Key Count**: <10,000 keys

### Database Targets

- **Query Time**: <100ms for simple queries, <1000ms for complex
- **Connection Pool**: <80% utilization under normal load
- **No N+1 Queries**: Use eager loading with `joinedload()` or `selectinload()`

### Error Rate Targets

- **5xx Errors**: <1% of requests
- **4xx Errors**: <5% of requests (excluding intentional 401/403)

---

## Usage Examples

### Example 1: Profile a Slow Function

```python
from app.core.performance import profile_function

@profile_function(threshold_ms=500)
async def expensive_operation(profile_name: str):
    # ... expensive AWS API call
    return results
```

If the function takes >500ms, it will log a warning.

### Example 2: Track Database Query

```python
from app.core.performance import track_query_performance

@track_query_performance("Fetch monthly budgets", threshold_ms=1000)
def get_monthly_budgets(db: Session):
    return db.query(Budget).filter(
        Budget.period == "monthly"
    ).all()
```

### Example 3: Cache with Metrics

```python
from app.core.cache import cached

@cached('costs:summary', ttl=300)
def get_cost_summary(profile_name: str, start_date: str, end_date: str):
    # Expensive Cost Explorer API call
    response = cost_explorer_client.get_cost_and_usage(...)
    return process_response(response)
```

Cache hits/misses are automatically tracked in performance metrics.

### Example 4: Monitor Performance in Production

```python
import requests

# Get performance stats
response = requests.get("https://api.example.com/api/v1/performance/stats")
stats = response.json()

# Check if targets are met
cache_hit_rate = stats["cache"]["application_level"]["hit_rate_percent"]
if cache_hit_rate < 70:
    print(f"⚠️ Cache hit rate below target: {cache_hit_rate}%")

# Check slowest endpoints
slowest = stats["endpoints"][:5]
for endpoint in slowest:
    if endpoint["p95_duration_ms"] > 1000:
        print(f"⚠️ Slow endpoint: {endpoint['endpoint']} "
              f"(p95: {endpoint['p95_duration_ms']}ms)")
```

---

## Troubleshooting

### Low Cache Hit Rate

**Symptoms**: Cache hit rate <50%

**Diagnosis**:
```http
GET /api/v1/performance/cache
```

**Solutions**:
1. Increase TTLs for stable data
2. Review cache key generation (ensure consistency)
3. Warm cache on application startup
4. Check Redis memory limits

### Slow API Responses

**Symptoms**: p95 latency >1000ms

**Diagnosis**:
```http
GET /api/v1/performance/endpoints
```

**Solutions**:
1. Enable caching for expensive operations
2. Optimize database queries (add indexes)
3. Use async/await for I/O operations
4. Implement pagination for large result sets
5. Add database query result caching

### Slow Database Queries

**Symptoms**: Queries taking >1 second

**Diagnosis**:
```http
GET /api/v1/performance/slow-queries
```

**Solutions**:
1. Add indexes on frequently queried columns
2. Use `select_related()` / `joinedload()` for relationships
3. Implement query result caching
4. Break complex queries into smaller chunks
5. Use database-level aggregations

### High Database Connection Usage

**Symptoms**: Connection pool exhausted, timeouts

**Diagnosis**:
```python
from app.core.database import get_connection_pool_stats
stats = get_connection_pool_stats()
```

**Solutions**:
1. Increase `pool_size` and `max_overflow`
2. Ensure connections are properly closed
3. Use connection pooling best practices
4. Implement connection retry logic

### Memory Issues

**Symptoms**: High memory usage, OOM errors

**Solutions**:
1. Use batch queries for large result sets
2. Implement pagination
3. Reduce cache retention time
4. Clear old cache keys regularly
5. Use Redis eviction policies

---

## Best Practices

### 1. Always Use Caching for AWS API Calls

```python
# ❌ Bad - no caching
def get_costs(profile, start, end):
    return cost_explorer_client.get_cost_and_usage(...)

# ✅ Good - with caching
@cached('costs:daily', ttl=300)
def get_costs(profile, start, end):
    return cost_explorer_client.get_cost_and_usage(...)
```

### 2. Profile Expensive Operations

```python
# ✅ Profile expensive functions
@profile_function(threshold_ms=1000)
async def run_full_audit(account_id):
    # ... audit logic
```

### 3. Use Bulk Operations

```python
# ❌ Bad - N queries
for record in records:
    db.add(Budget(**record))
    db.commit()

# ✅ Good - bulk insert
query_optimizer.bulk_insert(db, Budget, records)
```

### 4. Monitor Performance Regularly

Set up automated monitoring:

```bash
# Cron job to check performance daily
0 9 * * * curl https://api.example.com/api/v1/performance/health-check
```

### 5. Invalidate Cache on Data Changes

```python
# After updating budget
budget.update(amount=new_amount)
db.commit()

# Invalidate related caches
invalidate_cache(f'budgets:account_{budget.account_id}:*')
```

---

## Next Steps

1. **Set up monitoring alerts** for performance degradation
2. **Create Grafana dashboards** using performance metrics API
3. **Implement cache warming** on application startup
4. **Add performance tests** to CI/CD pipeline
5. **Configure auto-scaling** based on performance metrics

---

## Related Documentation

- [Cache Strategy](./CACHE_STRATEGY.md)
- [Database Optimization](./DATABASE_OPTIMIZATION.md)
- [API Performance](./API_PERFORMANCE.md)
