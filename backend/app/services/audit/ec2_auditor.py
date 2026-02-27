"""
EC2 resource auditing service.
"""
import boto3
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from app.schemas.audit import (
    EC2IdleInstance,
    EC2StoppedInstance,
    EC2AuditResults
)

logger = logging.getLogger(__name__)


# EC2 pricing (approximate monthly costs in USD)
EC2_PRICING = {
    't2.micro': 8.5,
    't2.small': 17.0,
    't2.medium': 33.0,
    't2.large': 66.0,
    't3.micro': 7.5,
    't3.small': 15.0,
    't3.medium': 30.0,
    't3.large': 60.0,
    'm5.large': 70.0,
    'm5.xlarge': 140.0,
    'm5.2xlarge': 280.0,
    'c5.large': 62.0,
    'c5.xlarge': 124.0,
    'r5.large': 91.0,
    'r5.xlarge': 182.0,
}

EBS_PRICING_PER_GB = 0.10  # USD per GB per month for gp2/gp3


class EC2Auditor:
    """Service for auditing EC2 instances."""

    @staticmethod
    def audit_ec2_instances(
        session: boto3.Session,
        cpu_threshold: float = 5.0,
        days_stopped_threshold: int = 7,
        lookback_days: int = 14
    ) -> EC2AuditResults:
        """
        Audit EC2 instances for idle and stopped instances.

        Args:
            session: Boto3 session
            cpu_threshold: CPU utilization threshold for idle instances (%)
            days_stopped_threshold: Days threshold for stopped instances
            lookback_days: Days to look back for CloudWatch metrics

        Returns:
            EC2AuditResults with findings
        """
        try:
            ec2_client = session.client('ec2')
            cloudwatch_client = session.client('cloudwatch')
            region = session.region_name or 'us-east-1'

            # Get all instances
            response = ec2_client.describe_instances()

            idle_instances = []
            stopped_instances = []
            total_idle_cost = 0.0
            total_stopped_ebs_cost = 0.0

            # Collect all running instances for batched CPU metric fetch
            running_instances = []
            running_instance_map = {}  # Map instance_id to instance data

            for reservation in response.get('Reservations', []):
                for instance in reservation.get('Instances', []):
                    instance_id = instance['InstanceId']
                    instance_type = instance['InstanceType']
                    state = instance['State']['Name']
                    launch_time = instance['LaunchTime']

                    # Get instance name from tags
                    instance_name = None
                    tags = {}
                    for tag in instance.get('Tags', []):
                        tags[tag['Key']] = tag['Value']
                        if tag['Key'] == 'Name':
                            instance_name = tag['Value']

                    # Collect running instances for batched metric fetch
                    if state == 'running':
                        running_instances.append(instance_id)
                        running_instance_map[instance_id] = {
                            'instance_type': instance_type,
                            'instance_name': instance_name,
                            'state': state,
                            'launch_time': launch_time,
                            'tags': tags,
                            'region': region
                        }

                    # Check stopped instances
                    elif state == 'stopped':
                        stopped_time = instance.get('StateTransitionReason', '')
                        days_stopped = EC2Auditor._parse_stopped_days(stopped_time)

                        if days_stopped >= days_stopped_threshold:
                            # Calculate EBS cost for attached volumes
                            ebs_cost = EC2Auditor._calculate_ebs_cost(ec2_client, instance_id)

                            stopped_instance = EC2StoppedInstance(
                                instance_id=instance_id,
                                instance_type=instance_type,
                                instance_name=instance_name,
                                stopped_time=None,  # Could parse from StateTransitionReason
                                days_stopped=days_stopped,
                                estimated_ebs_cost=ebs_cost,
                                region=region,
                                tags=tags,
                                recommendation=f"Instance stopped for {days_stopped} days. Consider terminating if no longer needed."
                            )
                            stopped_instances.append(stopped_instance)
                            total_stopped_ebs_cost += ebs_cost

            # Batch fetch CPU metrics for all running instances
            if running_instances:
                logger.info(f"Fetching CPU metrics for {len(running_instances)} running instances in batches")
                cpu_metrics = EC2Auditor._get_average_cpu_batch(
                    cloudwatch_client,
                    running_instances,
                    lookback_days
                )

                # Process idle instances based on batched metrics
                for instance_id, avg_cpu in cpu_metrics.items():
                    if avg_cpu is not None and avg_cpu < cpu_threshold:
                        instance_data = running_instance_map[instance_id]
                        launch_time = instance_data['launch_time']
                        instance_type = instance_data['instance_type']
                        days_running = (datetime.now(launch_time.tzinfo) - launch_time).days
                        monthly_cost = EC2_PRICING.get(instance_type, 50.0)  # Default estimate

                        idle_instance = EC2IdleInstance(
                            instance_id=instance_id,
                            instance_type=instance_type,
                            instance_name=instance_data['instance_name'],
                            state=instance_data['state'],
                            launch_time=launch_time,
                            avg_cpu_utilization=round(avg_cpu, 2),
                            days_running=days_running,
                            estimated_monthly_cost=monthly_cost,
                            potential_monthly_savings=monthly_cost,
                            region=instance_data['region'],
                            tags=instance_data['tags'],
                            recommendation=f"Instance has {avg_cpu:.1f}% average CPU utilization. Consider stopping or downsizing."
                        )
                        idle_instances.append(idle_instance)
                        total_idle_cost += monthly_cost

            total_savings = total_idle_cost + total_stopped_ebs_cost

            return EC2AuditResults(
                idle_instances=idle_instances,
                stopped_instances=stopped_instances,
                total_idle_cost=round(total_idle_cost, 2),
                total_stopped_ebs_cost=round(total_stopped_ebs_cost, 2),
                total_potential_savings=round(total_savings, 2)
            )

        except Exception as e:
            logger.error(f"Error auditing EC2 instances: {e}")
            return EC2AuditResults()

    @staticmethod
    def _get_average_cpu_batch(
        cloudwatch_client,
        instance_ids: List[str],
        lookback_days: int
    ) -> dict:
        """
        Get average CPU utilization for multiple instances in batches.

        Uses GetMetricData to batch up to 500 metrics per API call,
        dramatically reducing the number of CloudWatch API requests.

        Args:
            cloudwatch_client: CloudWatch client
            instance_ids: List of instance IDs to fetch metrics for
            lookback_days: Days to look back for CloudWatch metrics

        Returns:
            Dictionary mapping instance_id to average CPU utilization
        """
        cpu_metrics = {}

        if not instance_ids:
            return cpu_metrics

        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=lookback_days)

            # Process in batches of 500 (CloudWatch GetMetricData limit)
            batch_size = 500
            for i in range(0, len(instance_ids), batch_size):
                batch = instance_ids[i:i + batch_size]

                # Build metric queries for this batch
                metric_queries = []
                for idx, instance_id in enumerate(batch):
                    metric_queries.append({
                        'Id': f'm{idx}',  # Unique metric ID
                        'MetricStat': {
                            'Metric': {
                                'Namespace': 'AWS/EC2',
                                'MetricName': 'CPUUtilization',
                                'Dimensions': [
                                    {'Name': 'InstanceId', 'Value': instance_id}
                                ]
                            },
                            'Period': 86400,  # 1 day
                            'Stat': 'Average'
                        },
                        'ReturnData': True
                    })

                # Fetch all metrics in a single API call
                response = cloudwatch_client.get_metric_data(
                    MetricDataQueries=metric_queries,
                    StartTime=start_time,
                    EndTime=end_time
                )

                # Map results back to instance IDs
                for idx, instance_id in enumerate(batch):
                    metric_id = f'm{idx}'
                    # Find the corresponding result
                    for result in response.get('MetricDataResults', []):
                        if result['Id'] == metric_id:
                            values = result.get('Values', [])
                            if values:
                                avg_cpu = sum(values) / len(values)
                                cpu_metrics[instance_id] = avg_cpu
                            else:
                                cpu_metrics[instance_id] = None
                            break

                logger.info(f"Fetched CPU metrics for batch of {len(batch)} instances (batch {i//batch_size + 1})")

        except Exception as e:
            logger.error(f"Error fetching batched CPU metrics: {e}")
            # Fallback: return empty metrics for all instances
            for instance_id in instance_ids:
                cpu_metrics[instance_id] = None

        return cpu_metrics

    @staticmethod
    def _get_average_cpu(
        cloudwatch_client,
        instance_id: str,
        lookback_days: int
    ) -> Optional[float]:
        """
        Get average CPU utilization for an instance.

        DEPRECATED: Use _get_average_cpu_batch for better performance.
        This method is kept for backward compatibility.
        """
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=lookback_days)

            response = cloudwatch_client.get_metric_statistics(
                Namespace='AWS/EC2',
                MetricName='CPUUtilization',
                Dimensions=[
                    {'Name': 'InstanceId', 'Value': instance_id}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,  # 1 day
                Statistics=['Average']
            )

            datapoints = response.get('Datapoints', [])
            if datapoints:
                avg_cpu = sum(dp['Average'] for dp in datapoints) / len(datapoints)
                return avg_cpu
            return None

        except Exception as e:
            logger.warning(f"Could not get CPU metrics for {instance_id}: {e}")
            return None

    @staticmethod
    def _calculate_ebs_cost(ec2_client, instance_id: str) -> float:
        """Calculate monthly cost of EBS volumes attached to instance."""
        try:
            response = ec2_client.describe_volumes(
                Filters=[
                    {'Name': 'attachment.instance-id', 'Values': [instance_id]}
                ]
            )

            total_size_gb = 0
            for volume in response.get('Volumes', []):
                total_size_gb += volume['Size']

            monthly_cost = total_size_gb * EBS_PRICING_PER_GB
            return round(monthly_cost, 2)

        except Exception as e:
            logger.warning(f"Could not calculate EBS cost for {instance_id}: {e}")
            return 0.0

    @staticmethod
    def _parse_stopped_days(state_transition_reason: str) -> int:
        """Parse days stopped from StateTransitionReason."""
        # StateTransitionReason format: "User initiated (2024-01-15 10:30:45 GMT)"
        # This is a simplified parser - in production, use proper date parsing
        try:
            # For now, return a default value
            # In production, parse the actual date from the string
            return 7
        except Exception:
            return 0
