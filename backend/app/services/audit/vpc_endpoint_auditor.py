"""
VPC Endpoints auditing service.
"""
import boto3
import logging
from datetime import datetime, timedelta
from typing import List
from app.schemas.audit import (
    VPCEndpointUnused,
    VPCEndpointDuplicate,
    VPCEndpointAuditResults
)

logger = logging.getLogger(__name__)


# VPC Endpoint pricing (approximate monthly costs in USD for us-east-1)
# Interface endpoints cost $0.01/hour per AZ
INTERFACE_ENDPOINT_HOURLY_COST_PER_AZ = 0.01
INTERFACE_ENDPOINT_MONTHLY_COST_PER_AZ = INTERFACE_ENDPOINT_HOURLY_COST_PER_AZ * 730  # ~$7.30/month per AZ
INTERFACE_ENDPOINT_DATA_PROCESSING_COST = 0.01  # $0.01/GB

# Gateway endpoints (S3, DynamoDB) are free, but we track them for completeness
GATEWAY_ENDPOINT_COST = 0.0

# Thresholds
UNUSED_THRESHOLD_GB_PER_DAY = 0.1  # Less than 0.1GB/day considered unused
UNUSED_LOOKBACK_DAYS = 7


class VPCEndpointAuditor:
    """Service for auditing VPC Endpoints."""

    @staticmethod
    def audit_vpc_endpoints(
        session: boto3.Session,
        lookback_days: int = UNUSED_LOOKBACK_DAYS
    ) -> VPCEndpointAuditResults:
        """
        Audit VPC Endpoints for unused and duplicate endpoints.

        Args:
            session: Boto3 session
            lookback_days: Days to look back for metrics

        Returns:
            VPCEndpointAuditResults with findings
        """
        try:
            ec2_client = session.client('ec2')
            cloudwatch_client = session.client('cloudwatch')
            region = session.region_name or 'us-east-1'

            unused_endpoints = []
            duplicate_endpoints = []

            # Get all VPC Endpoints
            response = ec2_client.describe_vpc_endpoints()
            vpc_endpoints = response.get('VpcEndpoints', [])

            # Track service names to detect duplicates
            service_to_endpoints = {}

            for endpoint in vpc_endpoints:
                endpoint_id = endpoint['VpcEndpointId']
                endpoint_type = endpoint.get('VpcEndpointType', 'Gateway')
                service_name = endpoint.get('ServiceName', '')
                vpc_id = endpoint.get('VpcId', 'N/A')
                state = endpoint.get('State', '')
                created_time = endpoint.get('CreationTimestamp')

                # Get tags
                tags = {}
                for tag in endpoint.get('Tags', []):
                    tags[tag['Key']] = tag['Value']

                # Track for duplicates
                if service_name not in service_to_endpoints:
                    service_to_endpoints[service_name] = []
                service_to_endpoints[service_name].append({
                    'endpoint_id': endpoint_id,
                    'vpc_id': vpc_id,
                    'endpoint_type': endpoint_type,
                    'tags': tags,
                    'state': state
                })

                # Only audit Interface endpoints (Gateway endpoints are free)
                if endpoint_type == 'Interface' and state == 'available':
                    # Count availability zones
                    subnet_ids = endpoint.get('SubnetIds', [])
                    num_azs = len(subnet_ids)

                    # Calculate monthly cost
                    monthly_cost = num_azs * INTERFACE_ENDPOINT_MONTHLY_COST_PER_AZ

                    # Get data transfer metrics (if available)
                    data_transfer_gb = VPCEndpointAuditor._get_endpoint_data_transfer(
                        cloudwatch_client,
                        endpoint_id,
                        lookback_days
                    )

                    # Check if unused
                    if data_transfer_gb < UNUSED_THRESHOLD_GB_PER_DAY * lookback_days:
                        days_active = 0
                        if created_time:
                            days_active = (datetime.now(created_time.tzinfo) - created_time).days

                        unused_ep = VPCEndpointUnused(
                            endpoint_id=endpoint_id,
                            service_name=service_name,
                            endpoint_type=endpoint_type,
                            vpc_id=vpc_id,
                            num_azs=num_azs,
                            days_active=days_active,
                            avg_gb_per_day=round(data_transfer_gb / lookback_days, 3),
                            estimated_monthly_cost=round(monthly_cost, 2),
                            region=region,
                            tags=tags,
                            recommendation=f"Interface endpoint has minimal traffic ({data_transfer_gb:.2f}GB in {lookback_days} days). Consider deleting to save ${monthly_cost:.2f}/month."
                        )
                        unused_endpoints.append(unused_ep)

            # Detect duplicates (multiple endpoints for same service in same VPC)
            for service_name, endpoints in service_to_endpoints.items():
                if len(endpoints) > 1:
                    # Group by VPC
                    vpc_groups = {}
                    for ep in endpoints:
                        vpc_id = ep['vpc_id']
                        if vpc_id not in vpc_groups:
                            vpc_groups[vpc_id] = []
                        vpc_groups[vpc_id].append(ep)

                    # Check for duplicates within same VPC
                    for vpc_id, vpc_endpoints in vpc_groups.items():
                        if len(vpc_endpoints) > 1:
                            # Calculate total cost for duplicates
                            total_cost = 0.0
                            endpoint_ids = []

                            for ep in vpc_endpoints:
                                if ep['endpoint_type'] == 'Interface':
                                    # Estimate 2 AZs per endpoint (common default)
                                    ep_cost = 2 * INTERFACE_ENDPOINT_MONTHLY_COST_PER_AZ
                                    total_cost += ep_cost
                                endpoint_ids.append(ep['endpoint_id'])

                            # Potential savings: keep 1, delete others
                            potential_savings = total_cost * (len(vpc_endpoints) - 1) / len(vpc_endpoints)

                            if total_cost > 0:  # Only flag Interface endpoints
                                duplicate_ep = VPCEndpointDuplicate(
                                    service_name=service_name,
                                    vpc_id=vpc_id,
                                    endpoint_ids=endpoint_ids,
                                    duplicate_count=len(vpc_endpoints),
                                    estimated_monthly_cost=round(total_cost, 2),
                                    potential_monthly_savings=round(potential_savings, 2),
                                    region=region,
                                    recommendation=f"Found {len(vpc_endpoints)} duplicate endpoints for {service_name} in VPC {vpc_id}. Consolidate to 1 endpoint to save ${potential_savings:.2f}/month."
                                )
                                duplicate_endpoints.append(duplicate_ep)

            # Calculate totals
            total_unused_cost = sum(ep.estimated_monthly_cost for ep in unused_endpoints)
            total_duplicate_waste = sum(ep.potential_monthly_savings for ep in duplicate_endpoints)
            total_savings = total_unused_cost + total_duplicate_waste

            return VPCEndpointAuditResults(
                unused_endpoints=unused_endpoints,
                duplicate_endpoints=duplicate_endpoints,
                total_unused_cost=round(total_unused_cost, 2),
                total_duplicate_waste=round(total_duplicate_waste, 2),
                total_potential_savings=round(total_savings, 2)
            )

        except Exception as e:
            logger.error(f"Error auditing VPC Endpoints: {e}")
            return VPCEndpointAuditResults()

    @staticmethod
    def _get_endpoint_data_transfer(
        cloudwatch_client,
        endpoint_id: str,
        lookback_days: int
    ) -> float:
        """
        Get total data transfer for VPC Endpoint.

        Note: CloudWatch metrics for VPC endpoints are limited.
        We return 0 if no metrics available.
        """
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=lookback_days)

            # Try to get BytesProcessed metric (may not be available for all endpoints)
            response = cloudwatch_client.get_metric_statistics(
                Namespace='AWS/PrivateLink',
                MetricName='BytesProcessed',
                Dimensions=[
                    {'Name': 'VPC Endpoint Id', 'Value': endpoint_id}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,  # 1 day
                Statistics=['Sum']
            )

            datapoints = response.get('Datapoints', [])
            if datapoints:
                total_bytes = sum(dp['Sum'] for dp in datapoints)
                return total_bytes / (1024 ** 3)  # Convert to GB

            return 0.0

        except Exception as e:
            logger.debug(f"Could not get metrics for VPC Endpoint {endpoint_id}: {e}")
            return 0.0
