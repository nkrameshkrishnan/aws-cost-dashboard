"""
EBS Snapshot optimization auditing service.
"""
import boto3
import logging
from datetime import datetime
from typing import List, Dict, Set
from app.schemas.audit import (
    EBSOrphanedSnapshot,
    EBSDuplicateSnapshot,
    EBSSnapshotAuditResults
)

logger = logging.getLogger(__name__)


# EBS Snapshot pricing (approximate monthly costs in USD for us-east-1)
EBS_SNAPSHOT_COST_PER_GB = 0.05  # $0.05/GB/month

# Thresholds
MINIMUM_SNAPSHOT_AGE_DAYS = 30  # Only flag snapshots older than this


class EBSSnapshotAuditor:
    """Service for optimizing EBS snapshots."""

    @staticmethod
    def audit_ebs_snapshots(
        session: boto3.Session,
        min_age_days: int = MINIMUM_SNAPSHOT_AGE_DAYS
    ) -> EBSSnapshotAuditResults:
        """
        Audit EBS snapshots for orphaned and duplicate snapshots.

        Args:
            session: Boto3 session
            min_age_days: Minimum age for snapshots to be flagged

        Returns:
            EBSSnapshotAuditResults with findings
        """
        try:
            ec2_client = session.client('ec2')
            region = session.region_name or 'us-east-1'

            orphaned_snapshots = []
            duplicate_snapshots = []

            # Get all snapshots owned by this account
            response = ec2_client.describe_snapshots(OwnerIds=['self'])
            snapshots = response.get('Snapshots', [])

            # Get all AMIs to check which snapshots are in use
            ami_response = ec2_client.describe_images(Owners=['self'])
            amis = ami_response.get('Images', [])

            # Build set of snapshot IDs used by AMIs
            ami_snapshot_ids: Set[str] = set()
            for ami in amis:
                for bdm in ami.get('BlockDeviceMappings', []):
                    if 'Ebs' in bdm and 'SnapshotId' in bdm['Ebs']:
                        ami_snapshot_ids.add(bdm['Ebs']['SnapshotId'])

            # Track snapshots by volume ID for duplicate detection
            volume_snapshots: Dict[str, List[dict]] = {}

            for snapshot in snapshots:
                snapshot_id = snapshot['SnapshotId']
                volume_id = snapshot.get('VolumeId', None)
                size_gb = snapshot.get('VolumeSize', 0)
                start_time = snapshot['StartTime']
                description = snapshot.get('Description', '')

                # Calculate age
                days_old = (datetime.now(start_time.tzinfo) - start_time).days

                # Skip recent snapshots
                if days_old < min_age_days:
                    continue

                # Get tags
                tags = {}
                for tag in snapshot.get('Tags', []):
                    tags[tag['Key']] = tag['Value']

                # Calculate cost
                monthly_cost = size_gb * EBS_SNAPSHOT_COST_PER_GB

                # Check if snapshot is orphaned (not used by any AMI)
                # Determine if snapshot was created from an AMI
                ami_id = None
                if 'Created by CreateImage' in description:
                    # Extract AMI ID from description
                    parts = description.split('ami-')
                    if len(parts) > 1:
                        ami_id = 'ami-' + parts[1].split()[0].rstrip('.')

                # Check if this snapshot's AMI still exists
                ami_deleted = False
                if ami_id:
                    # Check if AMI still exists
                    try:
                        ec2_client.describe_images(ImageIds=[ami_id])
                        ami_deleted = False
                    except ec2_client.exceptions.ClientError as e:
                        if 'InvalidAMIID.NotFound' in str(e):
                            ami_deleted = True

                # Check if orphaned (not used by any AMI)
                if snapshot_id not in ami_snapshot_ids and monthly_cost > 0.10:  # Min $0.10/month
                    orphaned_snap = EBSOrphanedSnapshot(
                        snapshot_id=snapshot_id,
                        volume_id=volume_id,
                        size_gb=size_gb,
                        created_time=start_time,
                        days_old=days_old,
                        ami_id=ami_id,
                        ami_deleted=ami_deleted if ami_id else False,
                        estimated_monthly_cost=round(monthly_cost, 2),
                        region=region,
                        description=description,
                        tags=tags,
                        recommendation=f"Snapshot not used by any AMI ({days_old} days old, {size_gb}GB). Consider deleting to save ${monthly_cost:.2f}/month." +
                                     (f" Original AMI {ami_id} has been deleted." if ami_deleted else "")
                    )
                    orphaned_snapshots.append(orphaned_snap)

                # Track for duplicate detection
                if volume_id:
                    if volume_id not in volume_snapshots:
                        volume_snapshots[volume_id] = []
                    volume_snapshots[volume_id].append({
                        'snapshot_id': snapshot_id,
                        'start_time': start_time,
                        'size_gb': size_gb,
                        'monthly_cost': monthly_cost
                    })

            # Detect duplicates (multiple snapshots of the same volume)
            for volume_id, snaps in volume_snapshots.items():
                if len(snaps) > 3:  # More than 3 snapshots of same volume might indicate excess
                    # Sort by date (newest first)
                    snaps.sorted = sorted(snaps, key=lambda x: x['start_time'], reverse=True)

                    # Keep the 3 most recent, flag the rest as potential duplicates
                    old_snapshots = snaps[3:]

                    if len(old_snapshots) > 0:
                        snapshot_ids = [s['snapshot_id'] for s in old_snapshots]
                        total_size = sum(s['size_gb'] for s in old_snapshots)
                        total_cost = sum(s['monthly_cost'] for s in old_snapshots)

                        # Potential savings: delete old snapshots, keep 3 most recent
                        potential_savings = total_cost * 0.7  # Assume 70% can be safely deleted

                        if potential_savings > 1.0:  # Only flag if savings > $1/month
                            duplicate_snap = EBSDuplicateSnapshot(
                                volume_id=volume_id,
                                snapshot_ids=snapshot_ids,
                                duplicate_count=len(old_snapshots),
                                size_gb=total_size,
                                estimated_monthly_cost=round(total_cost, 2),
                                potential_monthly_savings=round(potential_savings, 2),
                                region=region,
                                recommendation=f"Volume has {len(snaps)} snapshots (keeping 3 most recent recommended). Delete {len(old_snapshots)} old snapshots to save ~${potential_savings:.2f}/month."
                            )
                            duplicate_snapshots.append(duplicate_snap)

            # Calculate totals
            total_orphaned_cost = sum(s.estimated_monthly_cost for s in orphaned_snapshots)
            total_duplicate_waste = sum(s.potential_monthly_savings for s in duplicate_snapshots)
            total_savings = total_orphaned_cost + total_duplicate_waste

            return EBSSnapshotAuditResults(
                orphaned_snapshots=orphaned_snapshots,
                duplicate_snapshots=duplicate_snapshots,
                total_orphaned_cost=round(total_orphaned_cost, 2),
                total_duplicate_waste=round(total_duplicate_waste, 2),
                total_potential_savings=round(total_savings, 2)
            )

        except Exception as e:
            logger.error(f"Error auditing EBS snapshots: {e}")
            return EBSSnapshotAuditResults()
