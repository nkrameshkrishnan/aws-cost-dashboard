"""
API Gateway cost optimization auditor.
Identifies unused APIs and APIs without caching.
"""
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError

from app.schemas.audit import APIGatewayUnusedAPI, APIGatewayNoCaching
from app.auditors.base import AuditorBase

logger = logging.getLogger(__name__)


class APIGatewayAuditor(AuditorBase):
    """Auditor for API Gateway REST APIs."""

    def __init__(self, session: boto3.Session, region: str):
        super().__init__(session, region)
        self.apigateway = session.client('apigateway', region_name=region)
        self.cloudwatch = session.client('cloudwatch', region_name=region)

    def run(self, days: int = 30, **kwargs) -> dict:
        """Run all API Gateway audit checks."""
        return {
            'unused_apis': self.audit_unused_apis(days=days),
            'apis_without_caching': self.audit_apis_without_caching(),
        }

    def audit_unused_apis(self, days: int = 30) -> List[APIGatewayUnusedAPI]:
        """
        Find API Gateway APIs with no request activity.

        Args:
            days: Number of days to check for activity (default: 30)

        Returns:
            List of unused APIs
        """
        unused = []

        try:
            paginator = self.apigateway.get_paginator('get_rest_apis')

            for page in paginator.paginate():
                for api in page.get('items', []):
                    api_id = api['id']
                    api_name = api['name']

                    # Get stages
                    try:
                        stages = self.apigateway.get_stages(restApiId=api_id)

                        for stage in stages.get('item', []):
                            stage_name = stage['stageName']

                            # Check CloudWatch metrics for requests
                            end_time = datetime.utcnow()
                            start_time = end_time - timedelta(days=days)

                            try:
                                metrics = self.cloudwatch.get_metric_statistics(
                                    Namespace='AWS/ApiGateway',
                                    MetricName='Count',
                                    Dimensions=[
                                        {'Name': 'ApiName', 'Value': api_name},
                                        {'Name': 'Stage', 'Value': stage_name}
                                    ],
                                    StartTime=start_time,
                                    EndTime=end_time,
                                    Period=86400,
                                    Statistics=['Sum']
                                )

                                total_requests = sum(point['Sum'] for point in metrics['Datapoints'])

                                # If no requests in period, mark as unused
                                if total_requests == 0:
                                    unused.append(APIGatewayUnusedAPI(
                                        api_id=api_id,
                                        api_name=api_name,
                                        stage=stage_name,
                                        region=self.region,
                                        total_requests=0,
                                        days_checked=days,
                                        created_date=stage.get('createdDate', '').isoformat() if stage.get('createdDate') else None,
                                        recommendation='Delete unused API or stage'
                                    ))
                            except ClientError as e:
                                logger.warning(f"Could not get metrics for API {api_name} stage {stage_name}: {e}")

                    except ClientError as e:
                        logger.warning(f"Could not get stages for API {api_id}: {e}")

        except ClientError as e:
            logger.error(f"Error listing API Gateway APIs: {e}")

        return unused

    def audit_apis_without_caching(self) -> List[APIGatewayNoCaching]:
        """
        Find API Gateway APIs without caching enabled on high-traffic endpoints.

        Returns:
            List of APIs without caching
        """
        no_caching = []

        try:
            paginator = self.apigateway.get_paginator('get_rest_apis')

            for page in paginator.paginate():
                for api in page.get('items', []):
                    api_id = api['id']
                    api_name = api['name']

                    try:
                        stages = self.apigateway.get_stages(restApiId=api_id)

                        for stage in stages.get('item', []):
                            stage_name = stage['stageName']
                            cache_enabled = stage.get('cacheClusterEnabled', False)
                            cache_size = stage.get('cacheClusterSize')

                            # Check if stage has high traffic but no caching
                            if not cache_enabled:
                                # Check recent request volume
                                end_time = datetime.utcnow()
                                start_time = end_time - timedelta(days=7)

                                try:
                                    metrics = self.cloudwatch.get_metric_statistics(
                                        Namespace='AWS/ApiGateway',
                                        MetricName='Count',
                                        Dimensions=[
                                            {'Name': 'ApiName', 'Value': api_name},
                                            {'Name': 'Stage', 'Value': stage_name}
                                        ],
                                        StartTime=start_time,
                                        EndTime=end_time,
                                        Period=86400,
                                        Statistics=['Sum']
                                    )

                                    total_requests = sum(point['Sum'] for point in metrics['Datapoints'])
                                    avg_daily_requests = total_requests / 7 if total_requests > 0 else 0

                                    # Flag APIs with >1000 requests/day without caching
                                    if avg_daily_requests > 1000:
                                        no_caching.append(APIGatewayNoCaching(
                                            api_id=api_id,
                                            api_name=api_name,
                                            stage=stage_name,
                                            region=self.region,
                                            cache_enabled=False,
                                            avg_daily_requests=round(avg_daily_requests),
                                            potential_cost_savings=round(avg_daily_requests * 0.0001, 2),  # Rough estimate
                                            recommendation='Enable caching to reduce backend load and costs'
                                        ))
                                except ClientError as e:
                                    logger.warning(f"Could not get metrics for API {api_name}: {e}")

                    except ClientError as e:
                        logger.warning(f"Could not get stages for API {api_id}: {e}")

        except ClientError as e:
            logger.error(f"Error listing API Gateway APIs: {e}")

        return no_caching
