"""
Elastic Beanstalk auditing service.
"""
import boto3
import logging
from datetime import datetime, timedelta
from typing import List
from app.schemas.audit import (
    ElasticBeanstalkUnusedEnvironment,
    ElasticBeanstalkNonProdRunning,
    ElasticBeanstalkAuditResults
)

logger = logging.getLogger(__name__)


# EC2 instance pricing (approximate for t3.medium in us-east-1)
# Beanstalk environments typically use t3.medium or similar
DEFAULT_INSTANCE_MONTHLY_COST = 30.0  # ~$0.042/hour * 730 hours
ALB_MONTHLY_COST = 22.50  # ~$0.0225/hour * 730 + LCU costs

# Thresholds
UNUSED_LOOKBACK_DAYS = 14
UNUSED_REQUEST_THRESHOLD = 10  # Requests per day
NONPROD_SAVINGS_PERCENTAGE = 0.65  # 65% savings from stopping non-prod during off-hours


class ElasticBeanstalkAuditor:
    """Service for auditing Elastic Beanstalk environments."""

    @staticmethod
    def audit_beanstalk_environments(
        session: boto3.Session,
        lookback_days: int = UNUSED_LOOKBACK_DAYS
    ) -> ElasticBeanstalkAuditResults:
        """
        Audit Elastic Beanstalk environments for unused and non-production waste.

        Args:
            session: Boto3 session
            lookback_days: Days to look back for metrics

        Returns:
            ElasticBeanstalkAuditResults with findings
        """
        try:
            eb_client = session.client('elasticbeanstalk')
            cloudwatch_client = session.client('cloudwatch')
            region = session.region_name or 'us-east-1'

            unused_environments = []
            nonprod_running_247 = []

            # Get all Beanstalk applications
            apps_response = eb_client.describe_applications()
            applications = apps_response.get('Applications', [])

            for app in applications:
                app_name = app['ApplicationName']

                # Get environments for this application
                envs_response = eb_client.describe_environments(ApplicationName=app_name)
                environments = envs_response.get('Environments', [])

                for env in environments:
                    env_name = env['EnvironmentName']
                    env_id = env['EnvironmentId']
                    status = env['Status']
                    health = env.get('Health', 'Unknown')
                    tier = env.get('Tier', {}).get('Name', 'WebServer')

                    # Skip terminated environments
                    if status in ['Terminated', 'Terminating']:
                        continue

                    # Get tags
                    tags = {}
                    try:
                        tags_response = eb_client.list_tags_for_resource(
                            ResourceArn=env['EnvironmentArn']
                        )
                        for tag in tags_response.get('ResourceTags', []):
                            tags[tag['Key']] = tag['Value']
                    except Exception:
                        pass

                    # Determine environment type from tags
                    env_type = tags.get('Environment', tags.get('environment', '')).lower()
                    if not env_type:
                        # Try to infer from name
                        env_name_lower = env_name.lower()
                        if any(x in env_name_lower for x in ['dev', 'development']):
                            env_type = 'dev'
                        elif any(x in env_name_lower for x in ['test', 'testing', 'qa']):
                            env_type = 'test'
                        elif any(x in env_name_lower for x in ['stag', 'staging']):
                            env_type = 'staging'
                        elif any(x in env_name_lower for x in ['prod', 'production']):
                            env_type = 'production'

                    # Get deployment info
                    days_since_deployment = 0
                    if 'DateUpdated' in env:
                        update_time = env['DateUpdated']
                        days_since_deployment = (datetime.now(update_time.tzinfo) - update_time).days

                    # Get request metrics
                    request_count_per_day = ElasticBeanstalkAuditor._get_request_metrics(
                        cloudwatch_client,
                        env_name,
                        lookback_days
                    )

                    # Get environment resources to estimate cost
                    try:
                        resources_response = eb_client.describe_environment_resources(
                            EnvironmentName=env_name
                        )
                        instances = resources_response.get('EnvironmentResources', {}).get('Instances', [])
                        instance_count = len(instances)

                        # Check for load balancer
                        load_balancers = resources_response.get('EnvironmentResources', {}).get('LoadBalancers', [])
                        has_lb = len(load_balancers) > 0
                    except Exception:
                        instance_count = 1  # Assume at least 1 instance
                        has_lb = True  # Assume has LB

                    # Estimate monthly cost
                    estimated_cost = instance_count * DEFAULT_INSTANCE_MONTHLY_COST
                    if has_lb:
                        estimated_cost += ALB_MONTHLY_COST

                    # Check if unused (low traffic)
                    if request_count_per_day < UNUSED_REQUEST_THRESHOLD and status == 'Ready':
                        unused_env = ElasticBeanstalkUnusedEnvironment(
                            environment_name=env_name,
                            environment_id=env_id,
                            application_name=app_name,
                            status=status,
                            health=health,
                            days_since_deployment=days_since_deployment,
                            request_count_per_day=round(request_count_per_day, 1),
                            estimated_monthly_cost=round(estimated_cost, 2),
                            region=region,
                            tags=tags,
                            recommendation=f"Environment has low traffic ({request_count_per_day:.1f} requests/day). Consider terminating to save ${estimated_cost:.2f}/month."
                        )
                        unused_environments.append(unused_env)

                    # Check if non-prod running 24/7
                    elif env_type in ['dev', 'test', 'staging'] and status == 'Ready':
                        # Potential savings from stopping during off-hours
                        potential_savings = estimated_cost * NONPROD_SAVINGS_PERCENTAGE

                        if potential_savings > 10.0:  # Only flag if savings > $10/month
                            nonprod_env = ElasticBeanstalkNonProdRunning(
                                environment_name=env_name,
                                environment_id=env_id,
                                application_name=app_name,
                                tier=tier,
                                environment_type=env_type,
                                instance_count=instance_count,
                                estimated_monthly_cost=round(estimated_cost, 2),
                                potential_monthly_savings=round(potential_savings, 2),
                                region=region,
                                tags=tags,
                                recommendation=f"Non-production ({env_type}) environment running 24/7. Implement automated start/stop schedule to save ~${potential_savings:.2f}/month."
                            )
                            nonprod_running_247.append(nonprod_env)

            # Calculate totals
            total_unused_cost = sum(e.estimated_monthly_cost for e in unused_environments)
            total_nonprod_waste = sum(e.potential_monthly_savings for e in nonprod_running_247)
            total_savings = total_unused_cost + total_nonprod_waste

            return ElasticBeanstalkAuditResults(
                unused_environments=unused_environments,
                nonprod_running_24_7=nonprod_running_247,
                total_unused_cost=round(total_unused_cost, 2),
                total_nonprod_waste=round(total_nonprod_waste, 2),
                total_potential_savings=round(total_savings, 2)
            )

        except Exception as e:
            logger.error(f"Error auditing Elastic Beanstalk environments: {e}")
            return ElasticBeanstalkAuditResults()

    @staticmethod
    def _get_request_metrics(
        cloudwatch_client,
        environment_name: str,
        lookback_days: int
    ) -> float:
        """Get average request count per day for Beanstalk environment."""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=lookback_days)

            # Try to get ApplicationRequests metric
            response = cloudwatch_client.get_metric_statistics(
                Namespace='AWS/ElasticBeanstalk',
                MetricName='ApplicationRequests',
                Dimensions=[
                    {'Name': 'EnvironmentName', 'Value': environment_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,  # 1 day
                Statistics=['Sum']
            )

            datapoints = response.get('Datapoints', [])
            if datapoints:
                total_requests = sum(dp['Sum'] for dp in datapoints)
                avg_requests_per_day = total_requests / lookback_days
                return avg_requests_per_day

            return 0.0

        except Exception as e:
            logger.debug(f"Could not get metrics for Beanstalk environment {environment_name}: {e}")
            return 0.0
