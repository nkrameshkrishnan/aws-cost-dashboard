"""
EFS (Elastic File System) auditing service.
"""
import boto3
import logging
from datetime import datetime, timedelta
from typing import List
from app.schemas.audit import (
    EFSUnusedFileSystem,
    EFSWithoutLifecycle,
    EFSAuditResults
)

logger = logging.getLogger(__name__)


# EFS pricing (approximate monthly costs in USD for us-east-1)
EFS_STANDARD_STORAGE_COST = 0.30  # $0.30/GB/month
EFS_IA_STORAGE_COST = 0.025  # $0.025/GB/month (Infrequent Access)
EFS_PROVISIONED_THROUGHPUT_COST = 6.00  # $6.00 per MB/s/month

# Thresholds
UNUSED_LOOKBACK_DAYS = 30
NO_CONNECTIONS_THRESHOLD_DAYS = 30
LIFECYCLE_SAVINGS_PERCENTAGE = 0.70  # 70% of data can typically move to IA


class EFSAuditor:
    """Service for auditing EFS file systems."""

    @staticmethod
    def audit_efs_file_systems(
        session: boto3.Session,
        lookback_days: int = UNUSED_LOOKBACK_DAYS
    ) -> EFSAuditResults:
        """
        Audit EFS file systems for unused instances and missing lifecycle policies.

        Args:
            session: Boto3 session
            lookback_days: Days to look back for metrics

        Returns:
            EFSAuditResults with findings
        """
        try:
            efs_client = session.client('efs')
            cloudwatch_client = session.client('cloudwatch')
            region = session.region_name or 'us-east-1'

            unused_file_systems = []
            file_systems_without_lifecycle = []

            # Get all EFS file systems
            response = efs_client.describe_file_systems()
            file_systems = response.get('FileSystems', [])

            for fs in file_systems:
                file_system_id = fs['FileSystemId']
                size_bytes = fs.get('SizeInBytes', {}).get('Value', 0)
                size_gb = size_bytes / (1024 ** 3)
                creation_time = fs.get('CreationTime')
                performance_mode = fs.get('PerformanceMode', 'generalPurpose')
                throughput_mode = fs.get('ThroughputMode', 'bursting')

                # Get tags
                tags = {}
                try:
                    tags_response = efs_client.describe_tags(FileSystemId=file_system_id)
                    for tag in tags_response.get('Tags', []):
                        tags[tag['Key']] = tag['Value']
                except Exception:
                    pass

                # Get file system name from tags or use ID
                fs_name = tags.get('Name', None)

                # Check for lifecycle policy
                has_lifecycle = EFSAuditor._check_lifecycle_policy(efs_client, file_system_id)

                # Get connection metrics
                connections = EFSAuditor._get_connection_metrics(
                    cloudwatch_client,
                    file_system_id,
                    lookback_days
                )

                # Calculate costs
                monthly_cost = size_gb * EFS_STANDARD_STORAGE_COST

                # Add provisioned throughput cost if applicable
                if throughput_mode == 'provisioned':
                    provisioned_throughput = fs.get('ProvisionedThroughputInMibps', 0)
                    monthly_cost += provisioned_throughput * EFS_PROVISIONED_THROUGHPUT_COST

                # Check if unused (no connections)
                if connections == 0:
                    days_without_connections = NO_CONNECTIONS_THRESHOLD_DAYS  # Minimum

                    if creation_time:
                        days_since_creation = (datetime.now(creation_time.tzinfo) - creation_time).days
                        if days_since_creation < lookback_days:
                            # New file system, might not have had time to be used yet
                            continue

                    unused_fs = EFSUnusedFileSystem(
                        file_system_id=file_system_id,
                        file_system_name=fs_name,
                        size_gb=round(size_gb, 2),
                        creation_time=creation_time,
                        days_without_connections=days_without_connections,
                        performance_mode=performance_mode,
                        throughput_mode=throughput_mode,
                        estimated_monthly_cost=round(monthly_cost, 2),
                        region=region,
                        tags=tags,
                        recommendation=f"EFS file system has no connections in {lookback_days} days. Consider deleting to save ${monthly_cost:.2f}/month."
                    )
                    unused_file_systems.append(unused_fs)

                # Check if missing lifecycle policy
                elif not has_lifecycle and size_gb > 1.0:  # Only flag if >1GB
                    # Calculate potential savings with IA storage
                    # Assume 70% of data can move to IA
                    standard_storage_gb = size_gb * (1 - LIFECYCLE_SAVINGS_PERCENTAGE)
                    ia_storage_gb = size_gb * LIFECYCLE_SAVINGS_PERCENTAGE

                    # Calculate savings
                    current_cost = size_gb * EFS_STANDARD_STORAGE_COST
                    optimized_cost = (standard_storage_gb * EFS_STANDARD_STORAGE_COST) + \
                                    (ia_storage_gb * EFS_IA_STORAGE_COST)
                    potential_savings = current_cost - optimized_cost

                    if potential_savings > 1.0:  # Only flag if savings > $1/month
                        without_lifecycle = EFSWithoutLifecycle(
                            file_system_id=file_system_id,
                            file_system_name=fs_name,
                            size_gb=round(size_gb, 2),
                            standard_storage_gb=round(size_gb, 2),
                            performance_mode=performance_mode,
                            estimated_monthly_cost=round(monthly_cost, 2),
                            potential_monthly_savings=round(potential_savings, 2),
                            region=region,
                            tags=tags,
                            recommendation=f"EFS file system ({size_gb:.1f}GB) has no lifecycle policy. Implement IA storage transition to save ~${potential_savings:.2f}/month."
                        )
                        file_systems_without_lifecycle.append(without_lifecycle)

            # Calculate totals
            total_unused_cost = sum(fs.estimated_monthly_cost for fs in unused_file_systems)
            total_lifecycle_savings = sum(fs.potential_monthly_savings for fs in file_systems_without_lifecycle)
            total_savings = total_unused_cost + total_lifecycle_savings

            return EFSAuditResults(
                unused_file_systems=unused_file_systems,
                file_systems_without_lifecycle=file_systems_without_lifecycle,
                total_unused_cost=round(total_unused_cost, 2),
                total_lifecycle_savings=round(total_lifecycle_savings, 2),
                total_potential_savings=round(total_savings, 2)
            )

        except Exception as e:
            logger.error(f"Error auditing EFS file systems: {e}")
            return EFSAuditResults()

    @staticmethod
    def _check_lifecycle_policy(efs_client, file_system_id: str) -> bool:
        """Check if EFS file system has lifecycle policy configured."""
        try:
            response = efs_client.describe_lifecycle_configuration(FileSystemId=file_system_id)
            lifecycle_policies = response.get('LifecyclePolicies', [])
            return len(lifecycle_policies) > 0
        except Exception as e:
            logger.debug(f"Could not check lifecycle policy for {file_system_id}: {e}")
            return False

    @staticmethod
    def _get_connection_metrics(
        cloudwatch_client,
        file_system_id: str,
        lookback_days: int
    ) -> int:
        """Get total client connections for EFS file system."""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=lookback_days)

            # Get ClientConnections metric
            response = cloudwatch_client.get_metric_statistics(
                Namespace='AWS/EFS',
                MetricName='ClientConnections',
                Dimensions=[
                    {'Name': 'FileSystemId', 'Value': file_system_id}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,  # 1 day
                Statistics=['Sum']
            )

            datapoints = response.get('Datapoints', [])
            if datapoints:
                total_connections = sum(dp['Sum'] for dp in datapoints)
                return int(total_connections)

            return 0

        except Exception as e:
            logger.debug(f"Could not get metrics for EFS {file_system_id}: {e}")
            return 0
