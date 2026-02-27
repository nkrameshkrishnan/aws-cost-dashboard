"""
ECS/Fargate cost optimization auditor.
Identifies oversized tasks with low CPU/memory utilization.
"""
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class ECSAuditor:
    """Auditor for ECS tasks and services."""

    def __init__(self, session: boto3.Session, region: str):
        self.session = session
        self.region = region
        self.ecs = session.client('ecs', region_name=region)
        self.cloudwatch = session.client('cloudwatch', region_name=region)

    def audit_oversized_tasks(self, cpu_threshold: float = 20.0, memory_threshold: float = 30.0) -> List[Dict[str, Any]]:
        """
        Find ECS tasks with low CPU/memory utilization (oversized).

        Args:
            cpu_threshold: CPU utilization threshold (default: 20%)
            memory_threshold: Memory utilization threshold (default: 30%)

        Returns:
            List of oversized tasks
        """
        oversized = []

        try:
            # List clusters
            clusters = self.ecs.list_clusters()['clusterArns']

            for cluster_arn in clusters:
                cluster_name = cluster_arn.split('/')[-1]

                # List services in cluster
                try:
                    services = self.ecs.list_services(cluster=cluster_arn)['serviceArns']

                    for service_arn in services:
                        service_name = service_arn.split('/')[-1]

                        # Get service details
                        try:
                            service_details = self.ecs.describe_services(
                                cluster=cluster_arn,
                                services=[service_arn]
                            )['services'][0]

                            task_definition = service_details['taskDefinition']
                            desired_count = service_details.get('desiredCount', 0)

                            # Get task definition details
                            task_def_response = self.ecs.describe_task_definition(
                                taskDefinition=task_definition
                            )['taskDefinition']

                            cpu = task_def_response.get('cpu', 'N/A')
                            memory = task_def_response.get('memory', 'N/A')
                            launch_type = service_details.get('launchType', 'FARGATE')

                            # Check CloudWatch metrics for CPU and memory utilization
                            end_time = datetime.utcnow()
                            start_time = end_time - timedelta(days=7)

                            try:
                                cpu_metrics = self.cloudwatch.get_metric_statistics(
                                    Namespace='AWS/ECS',
                                    MetricName='CPUUtilization',
                                    Dimensions=[
                                        {'Name': 'ServiceName', 'Value': service_name},
                                        {'Name': 'ClusterName', 'Value': cluster_name}
                                    ],
                                    StartTime=start_time,
                                    EndTime=end_time,
                                    Period=3600,
                                    Statistics=['Average']
                                )

                                memory_metrics = self.cloudwatch.get_metric_statistics(
                                    Namespace='AWS/ECS',
                                    MetricName='MemoryUtilization',
                                    Dimensions=[
                                        {'Name': 'ServiceName', 'Value': service_name},
                                        {'Name': 'ClusterName', 'Value': cluster_name}
                                    ],
                                    StartTime=start_time,
                                    EndTime=end_time,
                                    Period=3600,
                                    Statistics=['Average']
                                )

                                if cpu_metrics['Datapoints'] and memory_metrics['Datapoints']:
                                    avg_cpu = sum(p['Average'] for p in cpu_metrics['Datapoints']) / len(cpu_metrics['Datapoints'])
                                    avg_memory = sum(p['Average'] for p in memory_metrics['Datapoints']) / len(memory_metrics['Datapoints'])

                                    # Flag if both CPU and memory are low
                                    if avg_cpu < cpu_threshold and avg_memory < memory_threshold:
                                        oversized.append({
                                            'cluster_name': cluster_name,
                                            'service_name': service_name,
                                            'region': self.region,
                                            'launch_type': launch_type,
                                            'task_cpu': cpu,
                                            'task_memory': memory,
                                            'avg_cpu_utilization': round(avg_cpu, 2),
                                            'avg_memory_utilization': round(avg_memory, 2),
                                            'desired_count': desired_count,
                                            'recommendation': f'Reduce task size - CPU: {cpu} Memory: {memory} are underutilized'
                                        })
                            except ClientError as e:
                                logger.warning(f"Could not get metrics for service {service_name}: {e}")

                        except (ClientError, IndexError) as e:
                            logger.warning(f"Could not describe service {service_arn}: {e}")

                except ClientError as e:
                    logger.warning(f"Could not list services for cluster {cluster_name}: {e}")

        except ClientError as e:
            logger.error(f"Error listing ECS clusters: {e}")

        return oversized
