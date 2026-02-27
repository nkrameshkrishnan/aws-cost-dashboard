"""
Route53 cost optimization auditor.
Identifies unused hosted zones.
"""
import logging
from typing import List, Dict, Any
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class Route53Auditor:
    """Auditor for Route53 hosted zones."""

    def __init__(self, session: boto3.Session):
        self.session = session
        self.route53 = session.client('route53')

    def audit_unused_hosted_zones(self) -> List[Dict[str, Any]]:
        """
        Find Route53 hosted zones with no or minimal records.

        Returns:
            List of potentially unused hosted zones
        """
        unused = []

        try:
            paginator = self.route53.get_paginator('list_hosted_zones')

            for page in paginator.paginate():
                for zone in page['HostedZones']:
                    zone_id = zone['Id'].split('/')[-1]
                    zone_name = zone['Name']
                    is_private = zone.get('Config', {}).get('PrivateZone', False)

                    # List records in the zone
                    try:
                        records_response = self.route53.list_resource_record_sets(
                            HostedZoneId=zone_id
                        )
                        records = records_response['ResourceRecordSets']

                        # Filter out default NS and SOA records
                        user_records = [
                            r for r in records
                            if r['Type'] not in ['NS', 'SOA']
                        ]

                        # If only default records exist, zone is likely unused
                        if len(user_records) == 0:
                            unused.append({
                                'hosted_zone_id': zone_id,
                                'hosted_zone_name': zone_name,
                                'is_private': is_private,
                                'total_records': len(records),
                                'user_records': 0,
                                'estimated_monthly_cost': 0.50 if not is_private else 0.10,
                                'recommendation': 'Delete unused hosted zone if not needed'
                            })
                        elif len(user_records) <= 2:
                            unused.append({
                                'hosted_zone_id': zone_id,
                                'hosted_zone_name': zone_name,
                                'is_private': is_private,
                                'total_records': len(records),
                                'user_records': len(user_records),
                                'estimated_monthly_cost': 0.50 if not is_private else 0.10,
                                'recommendation': 'Review if hosted zone is still needed'
                            })

                    except ClientError as e:
                        logger.warning(f"Could not list records for zone {zone_id}: {e}")

        except ClientError as e:
            logger.error(f"Error listing Route53 hosted zones: {e}")

        return unused
