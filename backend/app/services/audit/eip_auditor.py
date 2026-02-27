"""
Elastic IP auditing service.
"""
import boto3
import logging
from datetime import datetime, timedelta
from typing import List
from app.schemas.audit import (
    ElasticIPUnattached,
    ElasticIPAuditResults
)

logger = logging.getLogger(__name__)


# Elastic IP pricing (USD per hour when unattached)
EIP_HOURLY_COST = 0.005  # $0.005 per hour = $3.60 per month


class ElasticIPAuditor:
    """Service for auditing Elastic IPs."""

    @staticmethod
    def audit_elastic_ips(session: boto3.Session) -> ElasticIPAuditResults:
        """
        Audit Elastic IPs for unattached IPs.

        Args:
            session: Boto3 session

        Returns:
            ElasticIPAuditResults with findings
        """
        try:
            ec2_client = session.client('ec2')
            region = session.region_name or 'us-east-1'

            # Get all Elastic IPs
            response = ec2_client.describe_addresses()

            unattached_ips = []
            total_cost = 0.0

            for address in response.get('Addresses', []):
                # Check if IP is not associated with an instance
                if 'AssociationId' not in address:
                    allocation_id = address.get('AllocationId', '')
                    public_ip = address.get('PublicIp', '')

                    # Estimate days unattached (simplified - in production, track this)
                    days_unattached = 30  # Default estimate

                    # Calculate monthly cost
                    hours_per_month = 730  # Average hours in a month
                    monthly_cost = EIP_HOURLY_COST * hours_per_month

                    # Get tags
                    tags = {}
                    for tag in address.get('Tags', []):
                        tags[tag['Key']] = tag['Value']

                    unattached_ip = ElasticIPUnattached(
                        allocation_id=allocation_id,
                        public_ip=public_ip,
                        days_unattached=days_unattached,
                        estimated_monthly_cost=round(monthly_cost, 2),
                        region=region,
                        tags=tags,
                        recommendation=f"Elastic IP {public_ip} is not associated with any instance. Consider releasing it to save ${monthly_cost:.2f}/month."
                    )
                    unattached_ips.append(unattached_ip)
                    total_cost += monthly_cost

            return ElasticIPAuditResults(
                unattached_ips=unattached_ips,
                total_cost=round(total_cost, 2)
            )

        except Exception as e:
            logger.error(f"Error auditing Elastic IPs: {e}")
            return ElasticIPAuditResults()
