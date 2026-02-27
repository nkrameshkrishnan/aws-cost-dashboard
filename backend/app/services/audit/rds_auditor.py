"""
RDS resource auditing service.
"""
import boto3
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from app.schemas.audit import (
    RDSIdleInstance,
    RDSStoppedInstance,
    RDSOldSnapshot,
    RDSAuditResults
)

logger = logging.getLogger(__name__)


# RDS pricing (approximate monthly costs in USD)
# Source: AWS pricing for us-east-1 region
RDS_PRICING = {
    # MySQL/PostgreSQL/MariaDB instances
    'db.t3.micro': 15.0,
    'db.t3.small': 30.0,
    'db.t3.medium': 60.0,
    'db.t3.large': 120.0,
    'db.t4g.micro': 12.0,
    'db.t4g.small': 24.0,
    'db.t4g.medium': 48.0,
    'db.m5.large': 140.0,
    'db.m5.xlarge': 280.0,
    'db.m5.2xlarge': 560.0,
    'db.r5.large': 175.0,
    'db.r5.xlarge': 350.0,
    'db.r5.2xlarge': 700.0,
}

# RDS storage pricing per GB per month
RDS_STORAGE_PRICING = {
    'gp2': 0.115,
    'gp3': 0.115,
    'io1': 0.125,
    'io2': 0.125,
    'standard': 0.10,
}

RDS_SNAPSHOT_PRICING_PER_GB = 0.095  # USD per GB per month


class RDSAuditor:
    """Service for auditing RDS instances and snapshots."""

    @staticmethod
    def audit_rds_resources(
        session: boto3.Session,
        cpu_threshold: float = 5.0,
        connection_threshold: int = 5,
        days_stopped_threshold: int = 7,
        snapshot_age_threshold: int = 90,
        lookback_days: int = 14
    ) -> RDSAuditResults:
        """
        Audit RDS instances and snapshots.

        Args:
            session: Boto3 session
            cpu_threshold: CPU utilization threshold for idle instances (%)
            connection_threshold: Connection count threshold for idle instances
            days_stopped_threshold: Days threshold for stopped instances
            snapshot_age_threshold: Age threshold for old snapshots (days)
            lookback_days: Days to look back for CloudWatch metrics

        Returns:
            RDSAuditResults with findings
        """
        try:
            rds_client = session.client('rds')
            cloudwatch_client = session.client('cloudwatch')
            region = session.region_name or 'us-east-1'

            # Audit idle instances
            idle_instances = RDSAuditor._audit_idle_instances(
                rds_client,
                cloudwatch_client,
                region,
                cpu_threshold,
                connection_threshold,
                lookback_days
            )

            # Audit stopped instances
            stopped_instances = RDSAuditor._audit_stopped_instances(
                rds_client,
                region,
                days_stopped_threshold
            )

            # Audit old snapshots
            old_snapshots = RDSAuditor._audit_old_snapshots(
                rds_client,
                region,
                snapshot_age_threshold
            )

            # Calculate totals
            total_idle_cost = sum(i.potential_monthly_savings for i in idle_instances)
            total_stopped_storage_cost = sum(i.estimated_storage_cost for i in stopped_instances)
            total_snapshot_cost = sum(s.estimated_monthly_cost for s in old_snapshots)
            total_savings = total_idle_cost + total_stopped_storage_cost + total_snapshot_cost

            return RDSAuditResults(
                idle_instances=idle_instances,
                stopped_instances=stopped_instances,
                old_snapshots=old_snapshots,
                total_idle_cost=round(total_idle_cost, 2),
                total_stopped_storage_cost=round(total_stopped_storage_cost, 2),
                total_snapshot_cost=round(total_snapshot_cost, 2),
                total_potential_savings=round(total_savings, 2)
            )

        except Exception as e:
            logger.error(f"Error auditing RDS resources: {e}")
            return RDSAuditResults()

    @staticmethod
    def _audit_idle_instances(
        rds_client,
        cloudwatch_client,
        region: str,
        cpu_threshold: float,
        connection_threshold: int,
        lookback_days: int
    ) -> List[RDSIdleInstance]:
        """Find idle RDS instances."""
        idle_instances = []

        try:
            response = rds_client.describe_db_instances()

            # Collect all available instances for batched metric fetch
            available_instances = []
            instance_map = {}

            for db_instance in response.get('DBInstances', []):
                if db_instance['DBInstanceStatus'] != 'available':
                    continue

                db_instance_id = db_instance['DBInstanceIdentifier']
                available_instances.append(db_instance_id)
                instance_map[db_instance_id] = db_instance

            # Batch fetch CPU and connection metrics for all instances
            if available_instances:
                logger.info(f"Fetching CPU and connection metrics for {len(available_instances)} RDS instances in batches")
                metrics = RDSAuditor._get_batch_metrics(
                    cloudwatch_client,
                    available_instances,
                    lookback_days
                )

                # Process idle instances based on batched metrics
                for db_instance_id, metric_data in metrics.items():
                    avg_cpu = metric_data.get('cpu')
                    avg_connections = metric_data.get('connections')

                    # Check if idle
                    if (avg_cpu is not None and avg_cpu < cpu_threshold) or \
                       (avg_connections is not None and avg_connections < connection_threshold):

                        db_instance = instance_map[db_instance_id]
                        db_instance_class = db_instance['DBInstanceClass']
                        engine = db_instance['Engine']
                        engine_version = db_instance['EngineVersion']
                        allocated_storage = db_instance['AllocatedStorage']
                        created_time = db_instance['InstanceCreateTime']
                        days_running = (datetime.now(created_time.tzinfo) - created_time).days
                        monthly_cost = RDS_PRICING.get(db_instance_class, 100.0)  # Default estimate

                        # Add storage cost
                        storage_type = db_instance.get('StorageType', 'gp2')
                        storage_price = RDS_STORAGE_PRICING.get(storage_type, 0.115)
                        monthly_cost += allocated_storage * storage_price

                        # Get tags
                        tags = {}
                        tag_list = db_instance.get('TagList', [])
                        for tag in tag_list:
                            tags[tag['Key']] = tag['Value']

                        idle_instance = RDSIdleInstance(
                            db_instance_id=db_instance_id,
                            db_instance_class=db_instance_class,
                            engine=engine,
                            engine_version=engine_version,
                            allocated_storage_gb=allocated_storage,
                            status=db_instance['DBInstanceStatus'],
                            created_time=created_time,
                            avg_cpu_utilization=round(avg_cpu or 0, 2),
                            avg_connections=round(avg_connections or 0, 2),
                            days_running=days_running,
                            estimated_monthly_cost=round(monthly_cost, 2),
                            potential_monthly_savings=round(monthly_cost, 2),
                            region=region,
                            tags=tags,
                            recommendation=f"RDS instance has {avg_cpu or 0:.1f}% average CPU and {avg_connections or 0:.0f} average connections. Consider stopping or downsizing."
                        )
                        idle_instances.append(idle_instance)

        except Exception as e:
            logger.error(f"Error finding idle RDS instances: {e}")

        return idle_instances

    @staticmethod
    def _audit_stopped_instances(
        rds_client,
        region: str,
        days_threshold: int
    ) -> List[RDSStoppedInstance]:
        """Find stopped RDS instances."""
        stopped_instances = []

        try:
            response = rds_client.describe_db_instances()

            for db_instance in response.get('DBInstances', []):
                if db_instance['DBInstanceStatus'] != 'stopped':
                    continue

                db_instance_id = db_instance['DBInstanceIdentifier']
                db_instance_class = db_instance['DBInstanceClass']
                engine = db_instance['Engine']
                allocated_storage = db_instance['AllocatedStorage']

                # RDS stopped instances can only be stopped for 7 days
                # After that, AWS automatically starts them
                days_stopped = 7  # Approximate

                if days_stopped >= days_threshold:
                    # Calculate storage cost (instance cost is not charged when stopped)
                    storage_type = db_instance.get('StorageType', 'gp2')
                    storage_price = RDS_STORAGE_PRICING.get(storage_type, 0.115)
                    storage_cost = allocated_storage * storage_price

                    # Get tags
                    tags = {}
                    tag_list = db_instance.get('TagList', [])
                    for tag in tag_list:
                        tags[tag['Key']] = tag['Value']

                    stopped_instance = RDSStoppedInstance(
                        db_instance_id=db_instance_id,
                        db_instance_class=db_instance_class,
                        engine=engine,
                        allocated_storage_gb=allocated_storage,
                        stopped_time=None,
                        days_stopped=days_stopped,
                        estimated_storage_cost=round(storage_cost, 2),
                        region=region,
                        tags=tags,
                        recommendation=f"RDS instance stopped for {days_stopped} days. Consider creating a final snapshot and deleting if no longer needed."
                    )
                    stopped_instances.append(stopped_instance)

        except Exception as e:
            logger.error(f"Error finding stopped RDS instances: {e}")

        return stopped_instances

    @staticmethod
    def _audit_old_snapshots(
        rds_client,
        region: str,
        age_threshold: int
    ) -> List[RDSOldSnapshot]:
        """Find old RDS snapshots."""
        old_snapshots = []

        try:
            # Get manual snapshots
            response = rds_client.describe_db_snapshots(SnapshotType='manual')

            for snapshot in response.get('DBSnapshots', []):
                snapshot_id = snapshot['DBSnapshotIdentifier']
                db_instance_id = snapshot.get('DBInstanceIdentifier')
                engine = snapshot['Engine']
                allocated_storage = snapshot['AllocatedStorage']
                snapshot_type = snapshot['SnapshotType']
                created_time = snapshot['SnapshotCreateTime']

                # Calculate age
                days_old = (datetime.now(created_time.tzinfo) - created_time).days

                if days_old >= age_threshold:
                    # Calculate monthly cost
                    monthly_cost = allocated_storage * RDS_SNAPSHOT_PRICING_PER_GB

                    # Get tags
                    tags = {}
                    tag_list = snapshot.get('TagList', [])
                    for tag in tag_list:
                        tags[tag['Key']] = tag['Value']

                    old_snapshot = RDSOldSnapshot(
                        snapshot_id=snapshot_id,
                        db_instance_id=db_instance_id,
                        engine=engine,
                        allocated_storage_gb=allocated_storage,
                        snapshot_type=snapshot_type,
                        created_time=created_time,
                        days_old=days_old,
                        estimated_monthly_cost=round(monthly_cost, 2),
                        region=region,
                        tags=tags,
                        recommendation=f"Manual snapshot is {days_old} days old. Review if still needed or implement automated cleanup."
                    )
                    old_snapshots.append(old_snapshot)

        except Exception as e:
            logger.error(f"Error finding old RDS snapshots: {e}")

        return old_snapshots

    @staticmethod
    def _get_batch_metrics(
        cloudwatch_client,
        db_instance_ids: List[str],
        lookback_days: int
    ) -> dict:
        """
        Get CPU and connection metrics for multiple RDS instances in batches.

        Uses GetMetricData to batch up to 250 metric queries per API call
        (500 total / 2 metrics per instance = 250 instances per call).

        Args:
            cloudwatch_client: CloudWatch client
            db_instance_ids: List of RDS instance IDs
            lookback_days: Days to look back for CloudWatch metrics

        Returns:
            Dictionary mapping instance_id to {'cpu': float, 'connections': float}
        """
        all_metrics = {}

        if not db_instance_ids:
            return all_metrics

        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=lookback_days)

            # Process in batches (2 metrics per instance, 500 metric limit = 250 instances per batch)
            batch_size = 250
            for i in range(0, len(db_instance_ids), batch_size):
                batch = db_instance_ids[i:i + batch_size]

                # Build metric queries for this batch (CPU + connections for each instance)
                metric_queries = []
                for idx, db_instance_id in enumerate(batch):
                    # CPU metric
                    metric_queries.append({
                        'Id': f'cpu{idx}',
                        'MetricStat': {
                            'Metric': {
                                'Namespace': 'AWS/RDS',
                                'MetricName': 'CPUUtilization',
                                'Dimensions': [
                                    {'Name': 'DBInstanceIdentifier', 'Value': db_instance_id}
                                ]
                            },
                            'Period': 86400,  # 1 day
                            'Stat': 'Average'
                        },
                        'ReturnData': True
                    })

                    # DatabaseConnections metric
                    metric_queries.append({
                        'Id': f'conn{idx}',
                        'MetricStat': {
                            'Metric': {
                                'Namespace': 'AWS/RDS',
                                'MetricName': 'DatabaseConnections',
                                'Dimensions': [
                                    {'Name': 'DBInstanceIdentifier', 'Value': db_instance_id}
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
                for idx, db_instance_id in enumerate(batch):
                    cpu_metric_id = f'cpu{idx}'
                    conn_metric_id = f'conn{idx}'

                    metrics = {'cpu': None, 'connections': None}

                    # Find CPU and connection results
                    for result in response.get('MetricDataResults', []):
                        if result['Id'] == cpu_metric_id:
                            values = result.get('Values', [])
                            if values:
                                metrics['cpu'] = sum(values) / len(values)
                        elif result['Id'] == conn_metric_id:
                            values = result.get('Values', [])
                            if values:
                                metrics['connections'] = sum(values) / len(values)

                    all_metrics[db_instance_id] = metrics

                logger.info(f"Fetched CPU + connection metrics for batch of {len(batch)} RDS instances (batch {i//batch_size + 1})")

        except Exception as e:
            logger.error(f"Error fetching batched RDS metrics: {e}")
            # Fallback: return empty metrics
            for db_instance_id in db_instance_ids:
                all_metrics[db_instance_id] = {'cpu': None, 'connections': None}

        return all_metrics

    @staticmethod
    def _get_average_cpu(
        cloudwatch_client,
        db_instance_id: str,
        lookback_days: int
    ) -> Optional[float]:
        """
        Get average CPU utilization for an RDS instance.

        DEPRECATED: Use _get_batch_metrics for better performance.
        This method is kept for backward compatibility.
        """
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=lookback_days)

            response = cloudwatch_client.get_metric_statistics(
                Namespace='AWS/RDS',
                MetricName='CPUUtilization',
                Dimensions=[
                    {'Name': 'DBInstanceIdentifier', 'Value': db_instance_id}
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
            logger.warning(f"Could not get CPU metrics for {db_instance_id}: {e}")
            return None

    @staticmethod
    def _get_average_connections(
        cloudwatch_client,
        db_instance_id: str,
        lookback_days: int
    ) -> Optional[float]:
        """
        Get average database connections for an RDS instance.

        DEPRECATED: Use _get_batch_metrics for better performance.
        This method is kept for backward compatibility.
        """
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=lookback_days)

            response = cloudwatch_client.get_metric_statistics(
                Namespace='AWS/RDS',
                MetricName='DatabaseConnections',
                Dimensions=[
                    {'Name': 'DBInstanceIdentifier', 'Value': db_instance_id}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,  # 1 day
                Statistics=['Average']
            )

            datapoints = response.get('Datapoints', [])
            if datapoints:
                avg_connections = sum(dp['Average'] for dp in datapoints) / len(datapoints)
                return avg_connections
            return None

        except Exception as e:
            logger.warning(f"Could not get connection metrics for {db_instance_id}: {e}")
            return None
