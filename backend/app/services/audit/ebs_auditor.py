"""
EBS resource auditing service.
"""
import boto3
import logging
from datetime import datetime, timedelta
from typing import List
from app.schemas.audit import (
    EBSUnattachedVolume,
    EBSOldSnapshot,
    EBSAuditResults
)

logger = logging.getLogger(__name__)


# EBS pricing per GB per month (USD)
VOLUME_PRICING = {
    'gp2': 0.10,
    'gp3': 0.08,
    'io1': 0.125,
    'io2': 0.125,
    'st1': 0.045,
    'sc1': 0.025,
    'standard': 0.05,
}

SNAPSHOT_PRICING_PER_GB = 0.05  # USD per GB per month


class EBSAuditor:
    """Service for auditing EBS volumes and snapshots."""

    @staticmethod
    def audit_ebs_resources(
        session: boto3.Session,
        days_unattached_threshold: int = 7,
        snapshot_age_threshold: int = 90
    ) -> EBSAuditResults:
        """
        Audit EBS volumes and snapshots.

        Args:
            session: Boto3 session
            days_unattached_threshold: Days threshold for unattached volumes
            snapshot_age_threshold: Age threshold for old snapshots (days)

        Returns:
            EBSAuditResults with findings
        """
        try:
            ec2_client = session.client('ec2')
            region = session.region_name or 'us-east-1'

            # Audit unattached volumes
            unattached_volumes = EBSAuditor._audit_unattached_volumes(
                ec2_client,
                region,
                days_unattached_threshold
            )

            # Audit old snapshots
            old_snapshots = EBSAuditor._audit_old_snapshots(
                ec2_client,
                region,
                snapshot_age_threshold
            )

            # Calculate totals
            total_unattached_cost = sum(v.estimated_monthly_cost for v in unattached_volumes)
            total_snapshot_cost = sum(s.estimated_monthly_cost for s in old_snapshots)
            total_savings = total_unattached_cost + total_snapshot_cost

            return EBSAuditResults(
                unattached_volumes=unattached_volumes,
                old_snapshots=old_snapshots,
                total_unattached_cost=round(total_unattached_cost, 2),
                total_snapshot_cost=round(total_snapshot_cost, 2),
                total_potential_savings=round(total_savings, 2)
            )

        except Exception as e:
            logger.error(f"Error auditing EBS resources: {e}")
            return EBSAuditResults()

    @staticmethod
    def _audit_unattached_volumes(
        ec2_client,
        region: str,
        days_threshold: int
    ) -> List[EBSUnattachedVolume]:
        """Find unattached EBS volumes."""
        unattached_volumes = []

        try:
            response = ec2_client.describe_volumes(
                Filters=[
                    {'Name': 'status', 'Values': ['available']}
                ]
            )

            for volume in response.get('Volumes', []):
                volume_id = volume['VolumeId']
                volume_type = volume['VolumeType']
                size_gb = volume['Size']
                created_time = volume['CreateTime']

                # Calculate days unattached
                days_unattached = (datetime.now(created_time.tzinfo) - created_time).days

                if days_unattached >= days_threshold:
                    # Calculate monthly cost
                    price_per_gb = VOLUME_PRICING.get(volume_type, 0.10)
                    monthly_cost = size_gb * price_per_gb

                    # Get tags
                    tags = {}
                    for tag in volume.get('Tags', []):
                        tags[tag['Key']] = tag['Value']

                    unattached_volume = EBSUnattachedVolume(
                        volume_id=volume_id,
                        volume_type=volume_type,
                        size_gb=size_gb,
                        created_time=created_time,
                        days_unattached=days_unattached,
                        estimated_monthly_cost=round(monthly_cost, 2),
                        region=region,
                        tags=tags,
                        recommendation=f"Volume unattached for {days_unattached} days. Consider deleting or creating a snapshot before deletion."
                    )
                    unattached_volumes.append(unattached_volume)

        except Exception as e:
            logger.error(f"Error finding unattached volumes: {e}")

        return unattached_volumes

    @staticmethod
    def _audit_old_snapshots(
        ec2_client,
        region: str,
        age_threshold: int
    ) -> List[EBSOldSnapshot]:
        """Find old EBS snapshots."""
        old_snapshots = []

        try:
            # Get snapshots owned by this account
            response = ec2_client.describe_snapshots(OwnerIds=['self'])

            for snapshot in response.get('Snapshots', []):
                snapshot_id = snapshot['SnapshotId']
                volume_id = snapshot.get('VolumeId')
                size_gb = snapshot['VolumeSize']
                created_time = snapshot['StartTime']
                description = snapshot.get('Description', '')

                # Calculate age
                days_old = (datetime.now(created_time.tzinfo) - created_time).days

                if days_old >= age_threshold:
                    # Calculate monthly cost
                    monthly_cost = size_gb * SNAPSHOT_PRICING_PER_GB

                    # Get tags
                    tags = {}
                    for tag in snapshot.get('Tags', []):
                        tags[tag['Key']] = tag['Value']

                    old_snapshot = EBSOldSnapshot(
                        snapshot_id=snapshot_id,
                        volume_id=volume_id,
                        size_gb=size_gb,
                        created_time=created_time,
                        days_old=days_old,
                        estimated_monthly_cost=round(monthly_cost, 2),
                        region=region,
                        description=description,
                        tags=tags,
                        recommendation=f"Snapshot is {days_old} days old. Review if still needed or implement lifecycle policy."
                    )
                    old_snapshots.append(old_snapshot)

        except Exception as e:
            logger.error(f"Error finding old snapshots: {e}")

        return old_snapshots
