"""
Data Transfer cost analysis auditing service.
"""
import boto3
import logging
from datetime import datetime, timedelta
from typing import List
from app.schemas.audit import (
    DataTransferHighCost,
    DataTransferAuditResults
)

logger = logging.getLogger(__name__)


# Data Transfer pricing thresholds
HIGH_COST_THRESHOLD = 50.0  # Flag transfers costing > $50/month
CROSS_AZ_DATA_TRANSFER_COST = 0.01  # $0.01/GB for cross-AZ
INTERNET_DATA_TRANSFER_COST = 0.09  # $0.09/GB for internet egress (average)


class DataTransferAuditor:
    """Service for analyzing data transfer costs."""

    @staticmethod
    def audit_data_transfer(
        session: boto3.Session,
        lookback_days: int = 30,
        high_cost_threshold: float = HIGH_COST_THRESHOLD
    ) -> DataTransferAuditResults:
        """
        Audit data transfer costs using Cost Explorer.

        Args:
            session: Boto3 session
            lookback_days: Days to analyze
            high_cost_threshold: Cost threshold for flagging

        Returns:
            DataTransferAuditResults with findings
        """
        try:
            ce_client = session.client('ce')
            region = session.region_name or 'us-east-1'

            high_cost_transfers = []

            # Calculate date range
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=lookback_days)

            # Get data transfer costs by usage type
            response = ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date.strftime('%Y-%m-%d'),
                    'End': end_date.strftime('%Y-%m-%d')
                },
                Granularity='MONTHLY',
                Metrics=['UnblendedCost', 'UsageQuantity'],
                GroupBy=[
                    {'Type': 'DIMENSION', 'Key': 'SERVICE'},
                    {'Type': 'DIMENSION', 'Key': 'USAGE_TYPE'}
                ],
                Filter={
                    'Or': [
                        {
                            'Dimensions': {
                                'Key': 'USAGE_TYPE',
                                'Values': ['DataTransfer-Out-Bytes', 'DataTransfer-Regional-Bytes']
                            }
                        },
                        {
                            'Dimensions': {
                                'Key': 'USAGE_TYPE_GROUP',
                                'Values': ['EC2: Data Transfer', 'S3: Data Transfer']
                            }
                        }
                    ]
                }
            )

            # Process results
            for result_by_time in response.get('ResultsByTime', []):
                for group in result_by_time.get('Groups', []):
                    keys = group.get('Keys', [])
                    if len(keys) >= 2:
                        service = keys[0]
                        usage_type = keys[1]

                        metrics = group.get('Metrics', {})
                        cost = float(metrics.get('UnblendedCost', {}).get('Amount', 0))
                        usage_gb = float(metrics.get('UsageQuantity', {}).get('Amount', 0))

                        # Only flag high-cost transfers
                        if cost >= high_cost_threshold:
                            # Determine transfer type
                            transfer_type = 'unknown'
                            if 'Regional' in usage_type or 'AZ' in usage_type:
                                transfer_type = 'cross-az'
                            elif 'Out' in usage_type or 'Internet' in usage_type:
                                transfer_type = 'internet'
                            elif 'Inter-Region' in usage_type:
                                transfer_type = 'cross-region'

                            # Extract regions if possible
                            source_region = region
                            dest_region = None
                            if 'to' in usage_type:
                                parts = usage_type.split('-to-')
                                if len(parts) > 1:
                                    dest_region = parts[1].split('-')[0]

                            # Calculate potential savings
                            potential_savings = 0.0
                            recommendation = ""

                            if transfer_type == 'cross-az':
                                # Recommend VPC endpoints or consolidation
                                potential_savings = cost * 0.5  # Assume 50% reduction possible
                                recommendation = f"High cross-AZ data transfer cost (${cost:.2f}/month, {usage_gb:.1f}GB). Consider using VPC endpoints or consolidating resources in the same AZ to save ~${potential_savings:.2f}/month."
                            elif transfer_type == 'internet':
                                # Recommend CloudFront or optimization
                                potential_savings = cost * 0.30  # Assume 30% reduction with CloudFront
                                recommendation = f"High internet data transfer cost (${cost:.2f}/month, {usage_gb:.1f}GB). Consider using CloudFront CDN or compressing data to save ~${potential_savings:.2f}/month."
                            elif transfer_type == 'cross-region':
                                # Recommend architecture optimization
                                potential_savings = cost * 0.40  # Assume 40% reduction possible
                                recommendation = f"High cross-region data transfer cost (${cost:.2f}/month, {usage_gb:.1f}GB). Consider regional architecture or caching to save ~${potential_savings:.2f}/month."
                            else:
                                potential_savings = cost * 0.20
                                recommendation = f"High data transfer cost (${cost:.2f}/month, {usage_gb:.1f}GB). Review architecture and optimize data flow to reduce costs."

                            transfer = DataTransferHighCost(
                                service=service,
                                transfer_type=transfer_type,
                                source_region=source_region,
                                dest_region=dest_region,
                                monthly_gb=round(usage_gb, 2),
                                estimated_monthly_cost=round(cost, 2),
                                potential_monthly_savings=round(potential_savings, 2),
                                recommendation=recommendation
                            )
                            high_cost_transfers.append(transfer)

            # Calculate totals
            total_transfer_cost = sum(t.estimated_monthly_cost for t in high_cost_transfers)
            total_savings = sum(t.potential_monthly_savings for t in high_cost_transfers)

            return DataTransferAuditResults(
                high_cost_transfers=high_cost_transfers,
                total_transfer_cost=round(total_transfer_cost, 2),
                total_potential_savings=round(total_savings, 2)
            )

        except Exception as e:
            logger.error(f"Error auditing data transfer costs: {e}")
            return DataTransferAuditResults()
