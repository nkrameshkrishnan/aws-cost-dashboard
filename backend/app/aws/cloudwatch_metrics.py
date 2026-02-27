"""
CloudWatch Metrics Collector for automatic business metric derivation.
Queries CloudWatch for operational metrics to calculate unit costs.
"""
import boto3
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)


class CloudWatchMetricsCollector:
    """Collects operational metrics from CloudWatch for unit cost calculations."""

    def __init__(self, session: boto3.Session, region: str = 'us-east-1'):
        self.session = session
        self.region = region
        self.cloudwatch = session.client('cloudwatch', region_name=region)

    def get_metric_statistics(
        self,
        namespace: str,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        statistic: str = 'Sum',
        dimensions: Optional[List[Dict]] = None,
        unit: Optional[str] = None
    ) -> float:
        """
        Get CloudWatch metric statistics.

        Args:
            namespace: AWS namespace (e.g., 'AWS/ApiGateway')
            metric_name: Metric name (e.g., 'Count')
            start_time: Start datetime
            end_time: End datetime
            statistic: Sum, Average, Maximum, etc.
            dimensions: Metric dimensions
            unit: Unit (e.g., 'Count', 'Bytes')

        Returns:
            Aggregated metric value
        """
        try:
            params = {
                'Namespace': namespace,
                'MetricName': metric_name,
                'StartTime': start_time,
                'EndTime': end_time,
                'Period': 86400,  # 1 day
                'Statistics': [statistic]
            }

            if dimensions:
                params['Dimensions'] = dimensions
            if unit:
                params['Unit'] = unit

            response = self.cloudwatch.get_metric_statistics(**params)

            datapoints = response.get('Datapoints', [])
            if not datapoints:
                return 0.0

            # Sum all datapoints
            total = sum(dp.get(statistic, 0) for dp in datapoints)
            return float(total)

        except Exception as e:
            logger.error(f"Error fetching metric {namespace}/{metric_name}: {str(e)}")
            return 0.0

    def get_api_gateway_requests(
        self,
        start_date: str,
        end_date: str
    ) -> int:
        """
        Get total API Gateway requests.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Total request count
        """
        start_time = datetime.strptime(start_date, "%Y-%m-%d")
        end_time = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

        total = self.get_metric_statistics(
            namespace='AWS/ApiGateway',
            metric_name='Count',
            start_time=start_time,
            end_time=end_time,
            statistic='Sum'
        )

        return int(total)

    def get_lambda_invocations(
        self,
        start_date: str,
        end_date: str
    ) -> int:
        """
        Get total Lambda function invocations.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Total invocation count
        """
        start_time = datetime.strptime(start_date, "%Y-%m-%d")
        end_time = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

        total = self.get_metric_statistics(
            namespace='AWS/Lambda',
            metric_name='Invocations',
            start_time=start_time,
            end_time=end_time,
            statistic='Sum'
        )

        return int(total)

    def get_alb_requests(
        self,
        start_date: str,
        end_date: str
    ) -> int:
        """
        Get total Application Load Balancer requests.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Total request count
        """
        start_time = datetime.strptime(start_date, "%Y-%m-%d")
        end_time = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

        total = self.get_metric_statistics(
            namespace='AWS/ApplicationELB',
            metric_name='RequestCount',
            start_time=start_time,
            end_time=end_time,
            statistic='Sum'
        )

        return int(total)

    def get_s3_data_transferred(
        self,
        start_date: str,
        end_date: str
    ) -> float:
        """
        Get total S3 data transferred (bytes downloaded).

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Total bytes transferred
        """
        start_time = datetime.strptime(start_date, "%Y-%m-%d")
        end_time = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

        total_bytes = self.get_metric_statistics(
            namespace='AWS/S3',
            metric_name='BytesDownloaded',
            start_time=start_time,
            end_time=end_time,
            statistic='Sum',
            unit='Bytes'
        )

        # Convert bytes to GB
        return total_bytes / (1024 ** 3)

    def get_cloudfront_data_served(
        self,
        start_date: str,
        end_date: str
    ) -> float:
        """
        Get total CloudFront data served.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Total GB served
        """
        start_time = datetime.strptime(start_date, "%Y-%m-%d")
        end_time = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

        total_bytes = self.get_metric_statistics(
            namespace='AWS/CloudFront',
            metric_name='BytesDownloaded',
            start_time=start_time,
            end_time=end_time,
            statistic='Sum',
            unit='Bytes'
        )

        # Convert bytes to GB
        return total_bytes / (1024 ** 3)

    def get_cognito_active_users(
        self,
        user_pool_id: Optional[str],
        start_date: str,
        end_date: str
    ) -> Optional[int]:
        """
        Get Cognito active users (if available).

        Note: Cognito doesn't provide DAU metrics in CloudWatch by default.
        This is a placeholder for custom metrics if configured.

        Args:
            user_pool_id: Cognito User Pool ID
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Active user count or None
        """
        if not user_pool_id:
            return None

        # Cognito doesn't have built-in DAU metrics
        # Would need custom CloudWatch metrics or Cognito APIs
        logger.info("Cognito active users not available via CloudWatch")
        return None

    def get_dynamodb_requests(
        self,
        start_date: str,
        end_date: str
    ) -> int:
        """
        Get total DynamoDB read/write requests.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Total request count
        """
        start_time = datetime.strptime(start_date, "%Y-%m-%d")
        end_time = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

        # Get consumed read capacity units
        read_units = self.get_metric_statistics(
            namespace='AWS/DynamoDB',
            metric_name='ConsumedReadCapacityUnits',
            start_time=start_time,
            end_time=end_time,
            statistic='Sum'
        )

        # Get consumed write capacity units
        write_units = self.get_metric_statistics(
            namespace='AWS/DynamoDB',
            metric_name='ConsumedWriteCapacityUnits',
            start_time=start_time,
            end_time=end_time,
            statistic='Sum'
        )

        # Approximate: 1 read unit ≈ 1 request (4KB)
        return int(read_units + write_units)

    def get_ec2_instance_hours(
        self,
        start_date: str,
        end_date: str
    ) -> float:
        """
        Get total EC2 instance hours (sum of all running instances).
        Uses EC2 service to list instances and calculate hours.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Total instance hours
        """
        try:
            ec2 = self.session.client('ec2', region_name=self.region)

            # Get all EC2 instances
            response = ec2.describe_instances()

            # Count running instances
            instance_count = 0
            for reservation in response.get('Reservations', []):
                for instance in reservation.get('Instances', []):
                    # Count instances that are running or stopped (but still incur costs)
                    if instance['State']['Name'] in ['running', 'stopped']:
                        instance_count += 1

            # Calculate hours in the date range
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            hours_in_period = (end_dt - start_dt).total_seconds() / 3600

            # Total instance hours = number of instances * hours in period
            total_instance_hours = instance_count * hours_in_period

            return total_instance_hours
        except Exception as e:
            logger.error(f"Error calculating EC2 instance hours: {str(e)}")
            return 0.0

    def get_business_metrics(
        self,
        start_date: str,
        end_date: str,
        user_pool_id: Optional[str] = None
    ) -> Dict:
        """
        Automatically collect all business metrics from CloudWatch.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            user_pool_id: Optional Cognito User Pool ID

        Returns:
            Dictionary with all derived metrics
        """
        logger.info(f"Collecting CloudWatch metrics for {start_date} to {end_date} in region {self.region}")

        # API Calls (API Gateway only)
        api_calls = self.get_api_gateway_requests(start_date, end_date)
        logger.debug(f"API Gateway requests: {api_calls}")

        # Total Transactions (API Gateway + Lambda + ALB + DynamoDB)
        api_gateway_requests = api_calls
        lambda_invocations = self.get_lambda_invocations(start_date, end_date)
        logger.debug(f"Lambda invocations: {lambda_invocations}")

        alb_requests = self.get_alb_requests(start_date, end_date)
        logger.debug(f"ALB requests: {alb_requests}")

        dynamodb_requests = self.get_dynamodb_requests(start_date, end_date)
        logger.debug(f"DynamoDB requests: {dynamodb_requests}")

        total_transactions = (
            api_gateway_requests +
            lambda_invocations +
            alb_requests +
            dynamodb_requests
        )

        # Data Processed (S3 + CloudFront)
        s3_gb = self.get_s3_data_transferred(start_date, end_date)
        logger.debug(f"S3 data transferred: {s3_gb} GB")

        cloudfront_gb = self.get_cloudfront_data_served(start_date, end_date)
        logger.debug(f"CloudFront data served: {cloudfront_gb} GB")

        total_gb = s3_gb + cloudfront_gb

        # Active Users (from Cognito if available)
        active_users = self.get_cognito_active_users(user_pool_id, start_date, end_date)

        # EC2 Instance Hours (for basic infrastructure)
        ec2_instance_hours = self.get_ec2_instance_hours(start_date, end_date)
        logger.debug(f"EC2 instance hours: {ec2_instance_hours}")

        metrics = {
            'active_users': active_users,
            'total_transactions': total_transactions if total_transactions > 0 else None,
            'api_calls': api_calls if api_calls > 0 else None,
            'data_processed_gb': total_gb if total_gb > 0 else None,
            'ec2_instance_hours': ec2_instance_hours if ec2_instance_hours > 0 else None,
            'breakdown': {
                'api_gateway_requests': api_gateway_requests,
                'lambda_invocations': lambda_invocations,
                'alb_requests': alb_requests,
                'dynamodb_requests': dynamodb_requests,
                's3_gb': s3_gb,
                'cloudfront_gb': cloudfront_gb,
                'ec2_instance_hours': ec2_instance_hours
            }
        }

        if all(v == 0 or v is None for k, v in metrics.items() if k != 'breakdown'):
            logger.warning(
                f"No CloudWatch metrics found for {start_date} to {end_date}. "
                f"This account may not have active API Gateway, Lambda, ALB, DynamoDB, S3, or CloudFront resources in {self.region}. "
                f"Breakdown: {metrics['breakdown']}"
            )
        else:
            logger.info(f"Successfully collected metrics: {metrics}")

        return metrics
