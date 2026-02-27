"""
ElastiCache auditing service.
"""
import boto3
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from app.schemas.audit import (
    ElastiCacheIdleCluster,
    ElastiCacheOverProvisionedCluster,
    ElastiCacheAuditResults
)

logger = logging.getLogger(__name__)


# ElastiCache pricing (approximate monthly costs in USD for us-east-1)
# Varies significantly by node type
ELASTICACHE_PRICING = {
    'cache.t3.micro': 0.017,     # $0.017/hour ~= $12.41/month
    'cache.t3.small': 0.034,     # $0.034/hour ~= $24.82/month
    'cache.t3.medium': 0.068,    # $0.068/hour ~= $49.64/month
    'cache.t4g.micro': 0.016,    # $0.016/hour ~= $11.68/month
    'cache.t4g.small': 0.032,    # $0.032/hour ~= $23.36/month
    'cache.t4g.medium': 0.064,   # $0.064/hour ~= $46.72/month
    'cache.m5.large': 0.146,     # $0.146/hour ~= $106.58/month
    'cache.m5.xlarge': 0.292,    # $0.292/hour ~= $213.16/month
    'cache.m6g.large': 0.132,    # $0.132/hour ~= $96.36/month
    'cache.r5.large': 0.209,     # $0.209/hour ~= $152.57/month
    'cache.r5.xlarge': 0.418,    # $0.418/hour ~= $305.14/month
    'cache.r6g.large': 0.189,    # $0.189/hour ~= $137.97/month
}

# Thresholds
IDLE_CPU_THRESHOLD = 5.0  # Less than 5% CPU
LOW_CACHE_HIT_RATE = 0.5  # Less than 50% cache hit rate
LOW_EVICTIONS_THRESHOLD = 10  # Less than 10 evictions per day


class ElastiCacheAuditor:
    """Service for auditing ElastiCache clusters."""

    @staticmethod
    def audit_elasticache(
        session: boto3.Session,
        cpu_threshold: float = IDLE_CPU_THRESHOLD,
        lookback_days: int = 7
    ) -> ElastiCacheAuditResults:
        """
        Audit ElastiCache clusters for idle and over-provisioned instances.

        Args:
            session: Boto3 session
            cpu_threshold: CPU threshold for idle classification
            lookback_days: Days to look back for metrics

        Returns:
            ElastiCacheAuditResults with findings
        """
        try:
            elasticache_client = session.client('elasticache')
            cloudwatch_client = session.client('cloudwatch')
            region = session.region_name or 'us-east-1'

            idle_clusters = []
            over_provisioned_clusters = []

            # Get Redis replication groups
            redis_findings = ElastiCacheAuditor._audit_redis_clusters(
                elasticache_client,
                cloudwatch_client,
                region,
                cpu_threshold,
                lookback_days
            )
            idle_clusters.extend(redis_findings['idle'])
            over_provisioned_clusters.extend(redis_findings['over_provisioned'])

            # Get Memcached clusters
            memcached_findings = ElastiCacheAuditor._audit_memcached_clusters(
                elasticache_client,
                cloudwatch_client,
                region,
                cpu_threshold,
                lookback_days
            )
            idle_clusters.extend(memcached_findings['idle'])
            over_provisioned_clusters.extend(memcached_findings['over_provisioned'])

            # Calculate totals
            total_idle_cost = sum(c.estimated_monthly_cost for c in idle_clusters)
            total_over_provisioned_waste = sum(c.potential_monthly_savings for c in over_provisioned_clusters)
            total_savings = total_idle_cost + total_over_provisioned_waste

            return ElastiCacheAuditResults(
                idle_clusters=idle_clusters,
                over_provisioned_clusters=over_provisioned_clusters,
                total_idle_cost=round(total_idle_cost, 2),
                total_over_provisioned_waste=round(total_over_provisioned_waste, 2),
                total_potential_savings=round(total_savings, 2)
            )

        except Exception as e:
            logger.error(f"Error auditing ElastiCache: {e}")
            return ElastiCacheAuditResults()

    @staticmethod
    def _audit_redis_clusters(
        elasticache_client,
        cloudwatch_client,
        region: str,
        cpu_threshold: float,
        lookback_days: int
    ) -> dict:
        """Audit Redis replication groups."""
        idle = []
        over_provisioned = []

        try:
            response = elasticache_client.describe_replication_groups()
            replication_groups = response.get('ReplicationGroups', [])

            for rg in replication_groups:
                cluster_id = rg['ReplicationGroupId']
                description = rg.get('Description', '')
                status = rg['Status']
                node_type = rg.get('CacheNodeType', 'unknown')
                num_cache_clusters = rg.get('MemberClusters', [])
                num_nodes = len(num_cache_clusters)

                # Skip if not available
                if status != 'available':
                    continue

                # Get tags
                tags = {}
                try:
                    tags_response = elasticache_client.list_tags_for_resource(
                        ResourceName=rg['ARN']
                    )
                    for tag in tags_response.get('TagList', []):
                        tags[tag['Key']] = tag['Value']
                except Exception:
                    pass

                # Get metrics for the primary node
                if num_cache_clusters:
                    primary_cluster_id = num_cache_clusters[0]
                    avg_cpu = ElastiCacheAuditor._get_redis_cpu(
                        cloudwatch_client, cluster_id, lookback_days
                    )
                    cache_hit_rate = ElastiCacheAuditor._get_cache_hit_rate(
                        cloudwatch_client, cluster_id, lookback_days
                    )
                    evictions = ElastiCacheAuditor._get_evictions(
                        cloudwatch_client, cluster_id, lookback_days
                    )

                    # Calculate cost
                    hourly_cost = ELASTICACHE_PRICING.get(node_type, 0.10)
                    monthly_cost = hourly_cost * 730 * num_nodes

                    # Check if idle
                    if avg_cpu is not None and avg_cpu < cpu_threshold and cache_hit_rate is not None and cache_hit_rate < LOW_CACHE_HIT_RATE:
                        idle_cluster = ElastiCacheIdleCluster(
                            cluster_id=cluster_id,
                            cluster_type='redis',
                            node_type=node_type,
                            num_nodes=num_nodes,
                            status=status,
                            avg_cpu_utilization=round(avg_cpu, 2),
                            cache_hit_rate=round(cache_hit_rate, 2),
                            estimated_monthly_cost=round(monthly_cost, 2),
                            region=region,
                            tags=tags,
                            recommendation=f"Redis cluster has very low CPU ({avg_cpu:.1f}%) and low cache hit rate ({cache_hit_rate*100:.1f}%). Consider deleting to save ${monthly_cost:.2f}/month."
                        )
                        idle.append(idle_cluster)

                    # Check if over-provisioned (high memory available, low evictions)
                    elif evictions is not None and evictions < LOW_EVICTIONS_THRESHOLD and avg_cpu is not None and avg_cpu < 20:
                        # Could downsize to smaller instance type
                        potential_savings = monthly_cost * 0.5  # Assume 50% savings from downsizing

                        over_prov_cluster = ElastiCacheOverProvisionedCluster(
                            cluster_id=cluster_id,
                            cluster_type='redis',
                            current_node_type=node_type,
                            num_nodes=num_nodes,
                            avg_cpu_utilization=round(avg_cpu, 2) if avg_cpu else 0.0,
                            avg_memory_utilization=0.0,  # Would need FreeableMemory metric
                            evictions_per_day=round(evictions, 0),
                            estimated_monthly_cost=round(monthly_cost, 2),
                            potential_monthly_savings=round(potential_savings, 2),
                            region=region,
                            tags=tags,
                            recommendation=f"Redis cluster has low CPU ({avg_cpu:.1f}%) and very few evictions. Consider downsizing to save ~${potential_savings:.2f}/month."
                        )
                        over_provisioned.append(over_prov_cluster)

        except Exception as e:
            logger.error(f"Error auditing Redis clusters: {e}")

        return {'idle': idle, 'over_provisioned': over_provisioned}

    @staticmethod
    def _audit_memcached_clusters(
        elasticache_client,
        cloudwatch_client,
        region: str,
        cpu_threshold: float,
        lookback_days: int
    ) -> dict:
        """Audit Memcached clusters."""
        idle = []
        over_provisioned = []

        try:
            response = elasticache_client.describe_cache_clusters()
            clusters = response.get('CacheClusters', [])

            for cluster in clusters:
                # Only Memcached clusters
                if cluster.get('Engine') != 'memcached':
                    continue

                cluster_id = cluster['CacheClusterId']
                status = cluster['CacheClusterStatus']
                node_type = cluster.get('CacheNodeType', 'unknown')
                num_nodes = cluster.get('NumCacheNodes', 1)

                if status != 'available':
                    continue

                # Get tags
                tags = {}
                try:
                    tags_response = elasticache_client.list_tags_for_resource(
                        ResourceName=cluster['ARN']
                    )
                    for tag in tags_response.get('TagList', []):
                        tags[tag['Key']] = tag['Value']
                except Exception:
                    pass

                # Get metrics
                avg_cpu = ElastiCacheAuditor._get_memcached_cpu(
                    cloudwatch_client, cluster_id, lookback_days
                )
                cache_hit_rate = ElastiCacheAuditor._get_cache_hit_rate(
                    cloudwatch_client, cluster_id, lookback_days
                )

                # Calculate cost
                hourly_cost = ELASTICACHE_PRICING.get(node_type, 0.10)
                monthly_cost = hourly_cost * 730 * num_nodes

                # Check if idle
                if avg_cpu is not None and avg_cpu < cpu_threshold:
                    idle_cluster = ElastiCacheIdleCluster(
                        cluster_id=cluster_id,
                        cluster_type='memcached',
                        node_type=node_type,
                        num_nodes=num_nodes,
                        status=status,
                        avg_cpu_utilization=round(avg_cpu, 2),
                        cache_hit_rate=round(cache_hit_rate, 2) if cache_hit_rate else 0.0,
                        estimated_monthly_cost=round(monthly_cost, 2),
                        region=region,
                        tags=tags,
                        recommendation=f"Memcached cluster has very low CPU ({avg_cpu:.1f}%). Consider deleting to save ${monthly_cost:.2f}/month."
                    )
                    idle.append(idle_cluster)

        except Exception as e:
            logger.error(f"Error auditing Memcached clusters: {e}")

        return {'idle': idle, 'over_provisioned': over_provisioned}

    @staticmethod
    def _get_redis_cpu(cloudwatch_client, cluster_id: str, lookback_days: int) -> Optional[float]:
        """Get average CPU for Redis cluster."""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=lookback_days)

            response = cloudwatch_client.get_metric_statistics(
                Namespace='AWS/ElastiCache',
                MetricName='CPUUtilization',
                Dimensions=[
                    {'Name': 'ReplicationGroupId', 'Value': cluster_id}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=['Average']
            )

            datapoints = response.get('Datapoints', [])
            if datapoints:
                return sum(dp['Average'] for dp in datapoints) / len(datapoints)
            return None
        except Exception as e:
            logger.warning(f"Could not get CPU for Redis cluster {cluster_id}: {e}")
            return None

    @staticmethod
    def _get_memcached_cpu(cloudwatch_client, cluster_id: str, lookback_days: int) -> Optional[float]:
        """Get average CPU for Memcached cluster."""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=lookback_days)

            response = cloudwatch_client.get_metric_statistics(
                Namespace='AWS/ElastiCache',
                MetricName='CPUUtilization',
                Dimensions=[
                    {'Name': 'CacheClusterId', 'Value': cluster_id}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=['Average']
            )

            datapoints = response.get('Datapoints', [])
            if datapoints:
                return sum(dp['Average'] for dp in datapoints) / len(datapoints)
            return None
        except Exception as e:
            logger.warning(f"Could not get CPU for Memcached cluster {cluster_id}: {e}")
            return None

    @staticmethod
    def _get_cache_hit_rate(cloudwatch_client, cluster_id: str, lookback_days: int) -> Optional[float]:
        """Get cache hit rate."""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=lookback_days)

            # Get cache hits
            hits_response = cloudwatch_client.get_metric_statistics(
                Namespace='AWS/ElastiCache',
                MetricName='CacheHits',
                Dimensions=[
                    {'Name': 'CacheClusterId', 'Value': cluster_id}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=['Sum']
            )

            # Get cache misses
            misses_response = cloudwatch_client.get_metric_statistics(
                Namespace='AWS/ElastiCache',
                MetricName='CacheMisses',
                Dimensions=[
                    {'Name': 'CacheClusterId', 'Value': cluster_id}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=['Sum']
            )

            hits = sum(dp['Sum'] for dp in hits_response.get('Datapoints', []))
            misses = sum(dp['Sum'] for dp in misses_response.get('Datapoints', []))

            total = hits + misses
            if total > 0:
                return hits / total
            return None
        except Exception:
            return None

    @staticmethod
    def _get_evictions(cloudwatch_client, cluster_id: str, lookback_days: int) -> Optional[float]:
        """Get average evictions per day."""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=lookback_days)

            response = cloudwatch_client.get_metric_statistics(
                Namespace='AWS/ElastiCache',
                MetricName='Evictions',
                Dimensions=[
                    {'Name': 'ReplicationGroupId', 'Value': cluster_id}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=['Sum']
            )

            datapoints = response.get('Datapoints', [])
            if datapoints:
                return sum(dp['Sum'] for dp in datapoints) / len(datapoints)
            return None
        except Exception:
            return None
