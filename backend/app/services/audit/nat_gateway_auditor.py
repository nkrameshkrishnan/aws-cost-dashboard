"""
NAT Gateway auditing service.
"""
import boto3
import logging
from datetime import datetime, timedelta
from typing import List
from app.schemas.audit import (
    NATGatewayIdle,
    NATGatewayUnused,
    NATGatewayAuditResults
)

logger = logging.getLogger(__name__)


# NAT Gateway pricing (approximate monthly costs in USD for us-east-1)
NAT_GATEWAY_HOURLY_COST = 0.045  # $0.045/hour
NAT_GATEWAY_MONTHLY_COST = NAT_GATEWAY_HOURLY_COST * 730  # ~$32.85/month
NAT_GATEWAY_DATA_PROCESSING_COST = 0.045  # $0.045/GB processed

# Thresholds
IDLE_THRESHOLD_GB_PER_DAY = 1.0  # Less than 1GB/day considered idle
UNUSED_THRESHOLD_GB_PER_DAY = 0.01  # Less than 0.01GB/day considered unused


class NATGatewayAuditor:
    """Service for auditing NAT Gateways."""

    @staticmethod
    def audit_nat_gateways(
        session: boto3.Session,
        idle_threshold_gb: float = IDLE_THRESHOLD_GB_PER_DAY,
        lookback_days: int = 7
    ) -> NATGatewayAuditResults:
        """
        Audit NAT Gateways for idle and unused instances.

        Args:
            session: Boto3 session
            idle_threshold_gb: GB per day threshold for idle classification
            lookback_days: Days to look back for metrics

        Returns:
            NATGatewayAuditResults with findings
        """
        try:
            ec2_client = session.client('ec2')
            cloudwatch_client = session.client('cloudwatch')
            region = session.region_name or 'us-east-1'

            idle_gateways = []
            unused_gateways = []

            # Get all NAT Gateways
            response = ec2_client.describe_nat_gateways(
                Filters=[{'Name': 'state', 'Values': ['available']}]
            )
            nat_gateways = response.get('NatGateways', [])

            for nat_gw in nat_gateways:
                nat_gateway_id = nat_gw['NatGatewayId']
                created_time = nat_gw['CreateTime']
                days_active = (datetime.now(created_time.tzinfo) - created_time).days
                subnet_id = nat_gw.get('SubnetId', 'N/A')
                vpc_id = nat_gw.get('VpcId', 'N/A')

                # Get tags
                tags = {}
                for tag in nat_gw.get('Tags', []):
                    tags[tag['Key']] = tag['Value']

                # Get data transfer metrics
                avg_bytes_out, avg_bytes_in = NATGatewayAuditor._get_nat_gateway_metrics(
                    cloudwatch_client,
                    nat_gateway_id,
                    lookback_days
                )

                # Calculate total data transfer in GB per day
                if avg_bytes_out is not None and avg_bytes_in is not None:
                    avg_gb_out_per_day = avg_bytes_out / (1024 ** 3)  # Convert to GB
                    avg_gb_in_per_day = avg_bytes_in / (1024 ** 3)
                    total_gb_per_day = avg_gb_out_per_day + avg_gb_in_per_day

                    # Calculate costs
                    monthly_fixed_cost = NAT_GATEWAY_MONTHLY_COST
                    monthly_data_cost = total_gb_per_day * 30 * NAT_GATEWAY_DATA_PROCESSING_COST
                    total_monthly_cost = monthly_fixed_cost + monthly_data_cost

                    # Check if unused (almost no traffic)
                    if total_gb_per_day < UNUSED_THRESHOLD_GB_PER_DAY:
                        unused_gw = NATGatewayUnused(
                            nat_gateway_id=nat_gateway_id,
                            subnet_id=subnet_id,
                            vpc_id=vpc_id,
                            created_time=created_time,
                            days_active=days_active,
                            avg_gb_out_per_day=round(avg_gb_out_per_day, 3),
                            avg_gb_in_per_day=round(avg_gb_in_per_day, 3),
                            estimated_monthly_cost=round(total_monthly_cost, 2),
                            region=region,
                            tags=tags,
                            recommendation=f"NAT Gateway has no traffic ({total_gb_per_day:.3f} GB/day). Consider deleting to save ${total_monthly_cost:.2f}/month."
                        )
                        unused_gateways.append(unused_gw)

                    # Check if idle (low traffic but not unused)
                    elif total_gb_per_day < idle_threshold_gb:
                        # Potential savings: data processing cost could be eliminated
                        potential_savings = monthly_data_cost + (monthly_fixed_cost * 0.5)  # Assume 50% consolidation

                        idle_gw = NATGatewayIdle(
                            nat_gateway_id=nat_gateway_id,
                            subnet_id=subnet_id,
                            vpc_id=vpc_id,
                            created_time=created_time,
                            days_active=days_active,
                            avg_gb_out_per_day=round(avg_gb_out_per_day, 3),
                            avg_gb_in_per_day=round(avg_gb_in_per_day, 3),
                            estimated_monthly_cost=round(total_monthly_cost, 2),
                            potential_monthly_savings=round(potential_savings, 2),
                            region=region,
                            tags=tags,
                            recommendation=f"NAT Gateway has low traffic ({total_gb_per_day:.2f} GB/day). Consider consolidating with other NAT Gateways to save ~${potential_savings:.2f}/month."
                        )
                        idle_gateways.append(idle_gw)

            # Calculate totals
            total_unused_cost = sum(gw.estimated_monthly_cost for gw in unused_gateways)
            total_idle_waste = sum(gw.potential_monthly_savings for gw in idle_gateways)
            total_savings = total_unused_cost + total_idle_waste

            return NATGatewayAuditResults(
                idle_gateways=idle_gateways,
                unused_gateways=unused_gateways,
                total_idle_waste=round(total_idle_waste, 2),
                total_unused_cost=round(total_unused_cost, 2),
                total_potential_savings=round(total_savings, 2)
            )

        except Exception as e:
            logger.error(f"Error auditing NAT Gateways: {e}")
            return NATGatewayAuditResults()

    @staticmethod
    def _get_nat_gateway_metrics(
        cloudwatch_client,
        nat_gateway_id: str,
        lookback_days: int
    ) -> tuple:
        """Get average bytes in/out per day for NAT Gateway."""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=lookback_days)

            # Get BytesOutToDestination metric
            response_out = cloudwatch_client.get_metric_statistics(
                Namespace='AWS/NATGateway',
                MetricName='BytesOutToDestination',
                Dimensions=[
                    {'Name': 'NatGatewayId', 'Value': nat_gateway_id}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,  # 1 day
                Statistics=['Sum']
            )

            # Get BytesInFromSource metric
            response_in = cloudwatch_client.get_metric_statistics(
                Namespace='AWS/NATGateway',
                MetricName='BytesInFromSource',
                Dimensions=[
                    {'Name': 'NatGatewayId', 'Value': nat_gateway_id}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,  # 1 day
                Statistics=['Sum']
            )

            # Calculate averages
            datapoints_out = response_out.get('Datapoints', [])
            datapoints_in = response_in.get('Datapoints', [])

            avg_bytes_out = 0.0
            avg_bytes_in = 0.0

            if datapoints_out:
                avg_bytes_out = sum(dp['Sum'] for dp in datapoints_out) / len(datapoints_out)

            if datapoints_in:
                avg_bytes_in = sum(dp['Sum'] for dp in datapoints_in) / len(datapoints_in)

            return avg_bytes_out, avg_bytes_in

        except Exception as e:
            logger.warning(f"Could not get metrics for NAT Gateway {nat_gateway_id}: {e}")
            return 0.0, 0.0
