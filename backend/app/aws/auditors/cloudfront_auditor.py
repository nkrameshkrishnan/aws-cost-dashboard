"""
CloudFront cost optimization auditor.
Identifies unused distributions and distributions without logging.
"""
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class CloudFrontAuditor:
    """Auditor for CloudFront distributions."""

    def __init__(self, session: boto3.Session):
        self.session = session
        self.cloudfront = session.client('cloudfront')
        self.cloudwatch = session.client('cloudwatch', region_name='us-east-1')  # CloudFront metrics in us-east-1

    def audit_unused_distributions(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Find CloudFront distributions with no traffic.

        Args:
            days: Number of days to check for traffic (default: 30)

        Returns:
            List of unused distributions with cost estimates
        """
        unused = []

        try:
            paginator = self.cloudfront.get_paginator('list_distributions')

            for page in paginator.paginate():
                if 'DistributionList' not in page or 'Items' not in page['DistributionList']:
                    continue

                for dist in page['DistributionList']['Items']:
                    dist_id = dist['Id']
                    domain_name = dist['DomainName']
                    enabled = dist['Enabled']

                    # Check CloudWatch metrics for requests
                    end_time = datetime.utcnow()
                    start_time = end_time - timedelta(days=days)

                    try:
                        response = self.cloudwatch.get_metric_statistics(
                            Namespace='AWS/CloudFront',
                            MetricName='Requests',
                            Dimensions=[{'Name': 'DistributionId', 'Value': dist_id}],
                            StartTime=start_time,
                            EndTime=end_time,
                            Period=86400,  # 1 day
                            Statistics=['Sum']
                        )

                        total_requests = sum(point['Sum'] for point in response['Datapoints'])

                        # If no requests in the period, mark as unused
                        if total_requests == 0:
                            unused.append({
                                'distribution_id': dist_id,
                                'domain_name': domain_name,
                                'enabled': enabled,
                                'total_requests': 0,
                                'days_checked': days,
                                'estimated_monthly_cost': 0.60,  # Minimum CloudFront cost
                                'recommendation': 'Disable or delete unused distribution'
                            })
                    except ClientError as e:
                        logger.warning(f"Could not get metrics for distribution {dist_id}: {e}")

        except ClientError as e:
            logger.error(f"Error listing CloudFront distributions: {e}")

        return unused

    def audit_distributions_without_logging(self) -> List[Dict[str, Any]]:
        """
        Find CloudFront distributions without access logging enabled.

        Returns:
            List of distributions without logging
        """
        no_logging = []

        try:
            paginator = self.cloudfront.get_paginator('list_distributions')

            for page in paginator.paginate():
                if 'DistributionList' not in page or 'Items' not in page['DistributionList']:
                    continue

                for dist in page['DistributionList']['Items']:
                    dist_id = dist['Id']

                    # Get distribution config to check logging
                    try:
                        config = self.cloudfront.get_distribution_config(Id=dist_id)
                        logging_config = config['DistributionConfig'].get('Logging', {})

                        if not logging_config.get('Enabled', False):
                            no_logging.append({
                                'distribution_id': dist_id,
                                'domain_name': dist['DomainName'],
                                'enabled': dist['Enabled'],
                                'logging_enabled': False,
                                'recommendation': 'Enable access logging for compliance and debugging'
                            })
                    except ClientError as e:
                        logger.warning(f"Could not get config for distribution {dist_id}: {e}")

        except ClientError as e:
            logger.error(f"Error listing CloudFront distributions: {e}")

        return no_logging
