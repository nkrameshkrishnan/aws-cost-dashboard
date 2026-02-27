"""
Redshift cost optimization auditor.
Identifies idle Redshift clusters with low database connections and query activity.
"""
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class RedshiftAuditor:
    """Auditor for Redshift clusters."""

    def __init__(self, session: boto3.Session, region: str):
        self.session = session
        self.region = region
        self.redshift = session.client('redshift', region_name=region)
        self.cloudwatch = session.client('cloudwatch', region_name=region)

    def audit_idle_clusters(self, connection_threshold: int = 1, days: int = 7) -> List[Dict[str, Any]]:
        """
        Find Redshift clusters with low database connections.

        Args:
            connection_threshold: Minimum average connections to be considered active
            days: Number of days to check (default: 7)

        Returns:
            List of idle Redshift clusters
        """
        idle = []

        try:
            paginator = self.redshift.get_paginator('describe_clusters')

            for page in paginator.paginate():
                for cluster in page.get('Clusters', []):
                    cluster_id = cluster['ClusterIdentifier']
                    cluster_status = cluster['ClusterStatus']
                    node_type = cluster['NodeType']
                    number_of_nodes = cluster['NumberOfNodes']

                    # Calculate estimated monthly cost (rough estimate)
                    # dc2.large: ~$180/month per node, ra3.xlplus: ~$1200/month per node
                    cost_per_node = 180 if 'dc2' in node_type else 300
                    estimated_monthly_cost = cost_per_node * number_of_nodes

                    # Check CloudWatch metrics for database connections
                    end_time = datetime.utcnow()
                    start_time = end_time - timedelta(days=days)

                    try:
                        metrics = self.cloudwatch.get_metric_statistics(
                            Namespace='AWS/Redshift',
                            MetricName='DatabaseConnections',
                            Dimensions=[{'Name': 'ClusterIdentifier', 'Value': cluster_id}],
                            StartTime=start_time,
                            EndTime=end_time,
                            Period=3600,
                            Statistics=['Average']
                        )

                        if metrics['Datapoints']:
                            avg_connections = sum(p['Average'] for p in metrics['Datapoints']) / len(metrics['Datapoints'])

                            # Flag if average connections are very low
                            if avg_connections < connection_threshold:
                                idle.append({
                                    'cluster_identifier': cluster_id,
                                    'region': self.region,
                                    'cluster_status': cluster_status,
                                    'node_type': node_type,
                                    'number_of_nodes': number_of_nodes,
                                    'avg_database_connections': round(avg_connections, 2),
                                    'days_checked': days,
                                    'estimated_monthly_cost': estimated_monthly_cost,
                                    'recommendation': 'Pause or delete idle Redshift cluster' if avg_connections == 0 else 'Consider downsizing cluster'
                                })
                        else:
                            # No metrics data - possibly never used
                            idle.append({
                                'cluster_identifier': cluster_id,
                                'region': self.region,
                                'cluster_status': cluster_status,
                                'node_type': node_type,
                                'number_of_nodes': number_of_nodes,
                                'avg_database_connections': 0,
                                'days_checked': days,
                                'estimated_monthly_cost': estimated_monthly_cost,
                                'recommendation': 'No connection metrics - consider deleting if unused'
                            })

                    except ClientError as e:
                        logger.warning(f"Could not get metrics for cluster {cluster_id}: {e}")

        except ClientError as e:
            logger.error(f"Error listing Redshift clusters: {e}")

        return idle
