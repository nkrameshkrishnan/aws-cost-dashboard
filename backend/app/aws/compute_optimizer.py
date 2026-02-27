"""
AWS Compute Optimizer client for right-sizing recommendations.
Falls back to basic CloudWatch-based analysis if Compute Optimizer is not enabled.
"""
import boto3
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging

from app.aws.basic_rightsizing import BasicRightSizingAnalyzer

logger = logging.getLogger(__name__)


class ComputeOptimizerClient:
    """Client for AWS Compute Optimizer API."""

    def __init__(self, session: boto3.Session, region: str = 'us-east-1'):
        """
        Initialize Compute Optimizer client.

        Args:
            session: Boto3 session with AWS credentials
            region: AWS region for analysis
        """
        self.session = session
        self.region = region
        self.client = session.client('compute-optimizer')
        self.pricing_client = session.client('pricing', region_name='us-east-1')
        self.ec2_client = session.client('ec2', region_name=region)

        # Initialize basic analyzer as fallback
        self.basic_analyzer = BasicRightSizingAnalyzer(session, region)

    def _extract_region_from_arn(self, arn: str) -> str:
        """Extract region from an ARN."""
        try:
            # ARN format: arn:partition:service:region:account-id:resource
            parts = arn.split(':')
            if len(parts) >= 4:
                return parts[3] or self.region
        except Exception:
            pass
        return self.region

    def get_ec2_recommendations(
        self,
        account_ids: Optional[List[str]] = None,
        filters: Optional[List[Dict]] = None
    ) -> List[Dict]:
        """
        Get EC2 instance right-sizing recommendations.

        Args:
            account_ids: List of AWS account IDs to filter
            filters: Additional filters for recommendations

        Returns:
            List of EC2 recommendations with savings potential
        """
        try:
            params = {}
            if account_ids:
                params['accountIds'] = account_ids
            if filters:
                params['filters'] = filters

            recommendations = []
            next_token = None

            while True:
                if next_token:
                    params['nextToken'] = next_token

                response = self.client.get_ec2_instance_recommendations(**params)

                for rec in response.get('instanceRecommendations', []):
                    # Parse recommendation
                    instance_arn = rec.get('instanceArn', '')
                    instance_name = rec.get('instanceName', '')
                    current_instance_type = rec.get('currentInstanceType', '')
                    finding = rec.get('finding', '')
                    utilization = rec.get('utilizationMetrics', [])

                    # Get recommended options
                    recommended_options = rec.get('recommendationOptions', [])
                    if recommended_options:
                        best_option = recommended_options[0]  # Top recommendation

                        recommended_type = best_option.get('instanceType', '')
                        performance_risk = best_option.get('performanceRisk', 0)

                        # Calculate savings (estimated monthly)
                        savings_opportunity = best_option.get('savingsOpportunity', {})
                        estimated_monthly_savings = savings_opportunity.get('estimatedMonthlySavings', {}).get('value', 0)
                        savings_percentage = savings_opportunity.get('savingsOpportunityPercentage', 0)

                        # Get utilization metrics
                        cpu_utilization = None
                        memory_utilization = None
                        for metric in utilization:
                            if metric.get('name') == 'Cpu':
                                cpu_utilization = metric.get('statistic', {}).get('maximum', 0)
                            elif metric.get('name') == 'Memory':
                                memory_utilization = metric.get('statistic', {}).get('maximum', 0)

                        recommendations.append({
                            'resource_arn': instance_arn,
                            'resource_name': instance_name,
                            'resource_type': 'ec2_instance',
                            'current_config': current_instance_type,
                            'recommended_config': recommended_type,
                            'finding': finding,  # Underprovisioned, Overprovisioned, Optimized
                            'region': self._extract_region_from_arn(instance_arn),
                            'cpu_utilization': cpu_utilization,
                            'memory_utilization': memory_utilization,
                            'performance_risk': performance_risk,  # 0-5 scale
                            'estimated_monthly_savings': estimated_monthly_savings,
                            'savings_percentage': savings_percentage,
                            'recommendation_source': 'aws_compute_optimizer'
                        })

                next_token = response.get('nextToken')
                if not next_token:
                    break

            return recommendations

        except self.client.exceptions.OptInRequiredException:
            logger.warning("AWS Compute Optimizer not enabled for this account")
            return []
        except Exception as e:
            logger.error(f"Error getting EC2 recommendations: {str(e)}")
            return []

    def get_ebs_recommendations(self) -> List[Dict]:
        """
        Get EBS volume right-sizing recommendations.

        Returns:
            List of EBS volume recommendations
        """
        try:
            recommendations = []
            next_token = None

            while True:
                params = {}
                if next_token:
                    params['nextToken'] = next_token

                response = self.client.get_ebs_volume_recommendations(**params)

                for rec in response.get('volumeRecommendations', []):
                    volume_arn = rec.get('volumeArn', '')
                    current_config = rec.get('currentConfiguration', {})
                    finding = rec.get('finding', '')

                    volume_type = current_config.get('volumeType', '')
                    volume_size = current_config.get('volumeSize', 0)
                    baseline_iops = current_config.get('volumeBaselineIOPS', 0)

                    # Get recommended options
                    recommended_options = rec.get('volumeRecommendationOptions', [])
                    if recommended_options:
                        best_option = recommended_options[0]

                        recommended_config = best_option.get('configuration', {})
                        recommended_type = recommended_config.get('volumeType', '')
                        recommended_size = recommended_config.get('volumeSize', 0)

                        savings_opportunity = best_option.get('savingsOpportunity', {})
                        estimated_monthly_savings = savings_opportunity.get('estimatedMonthlySavings', {}).get('value', 0)
                        savings_percentage = savings_opportunity.get('savingsOpportunityPercentage', 0)

                        recommendations.append({
                            'resource_arn': volume_arn,
                            'resource_name': volume_arn.split('/')[-1],
                            'resource_type': 'ebs_volume',
                            'current_config': f"{volume_type} {volume_size}GB",
                            'recommended_config': f"{recommended_type} {recommended_size}GB",
                            'finding': finding,
                            'region': self._extract_region_from_arn(volume_arn),
                            'estimated_monthly_savings': estimated_monthly_savings,
                            'savings_percentage': savings_percentage,
                            'recommendation_source': 'aws_compute_optimizer'
                        })

                next_token = response.get('nextToken')
                if not next_token:
                    break

            return recommendations

        except self.client.exceptions.OptInRequiredException:
            logger.warning("AWS Compute Optimizer not enabled for EBS volumes")
            return []
        except Exception as e:
            logger.error(f"Error getting EBS recommendations: {str(e)}")
            return []

    def get_lambda_recommendations(self) -> List[Dict]:
        """
        Get Lambda function right-sizing recommendations.

        Returns:
            List of Lambda recommendations
        """
        try:
            recommendations = []
            next_token = None

            while True:
                params = {}
                if next_token:
                    params['nextToken'] = next_token

                response = self.client.get_lambda_function_recommendations(**params)

                for rec in response.get('lambdaFunctionRecommendations', []):
                    function_arn = rec.get('functionArn', '')
                    current_memory = rec.get('currentMemorySize', 0)
                    finding = rec.get('finding', '')

                    # Get recommended options
                    recommended_options = rec.get('memorySizeRecommendationOptions', [])
                    if recommended_options:
                        best_option = recommended_options[0]

                        recommended_memory = best_option.get('memorySize', 0)
                        savings_opportunity = best_option.get('savingsOpportunity', {})
                        estimated_monthly_savings = savings_opportunity.get('estimatedMonthlySavings', {}).get('value', 0)

                        recommendations.append({
                            'resource_arn': function_arn,
                            'resource_name': function_arn.split(':')[-1],
                            'resource_type': 'lambda_function',
                            'current_config': f"{current_memory}MB",
                            'recommended_config': f"{recommended_memory}MB",
                            'finding': finding,
                            'region': self._extract_region_from_arn(function_arn),
                            'estimated_monthly_savings': estimated_monthly_savings,
                            'recommendation_source': 'aws_compute_optimizer'
                        })

                next_token = response.get('nextToken')
                if not next_token:
                    break

            return recommendations

        except self.client.exceptions.OptInRequiredException:
            logger.warning("AWS Compute Optimizer not enabled for Lambda functions")
            return []
        except Exception as e:
            logger.error(f"Error getting Lambda recommendations: {str(e)}")
            return []

    def get_auto_scaling_group_recommendations(self) -> List[Dict]:
        """
        Get Auto Scaling Group recommendations.

        Returns:
            List of ASG recommendations
        """
        try:
            recommendations = []
            next_token = None

            while True:
                params = {}
                if next_token:
                    params['nextToken'] = next_token

                response = self.client.get_auto_scaling_group_recommendations(**params)

                for rec in response.get('autoScalingGroupRecommendations', []):
                    asg_arn = rec.get('autoScalingGroupArn', '')
                    asg_name = rec.get('autoScalingGroupName', '')
                    current_config = rec.get('currentConfiguration', {})
                    finding = rec.get('finding', '')

                    current_instance_type = current_config.get('instanceType', '')

                    # Get recommended options
                    recommended_options = rec.get('recommendationOptions', [])
                    if recommended_options:
                        best_option = recommended_options[0]

                        recommended_config = best_option.get('configuration', {})
                        recommended_instance_type = recommended_config.get('instanceType', '')

                        savings_opportunity = best_option.get('savingsOpportunity', {})
                        estimated_monthly_savings = savings_opportunity.get('estimatedMonthlySavings', {}).get('value', 0)

                        recommendations.append({
                            'resource_arn': asg_arn,
                            'resource_name': asg_name,
                            'resource_type': 'auto_scaling_group',
                            'current_config': current_instance_type,
                            'recommended_config': recommended_instance_type,
                            'finding': finding,
                            'region': self._extract_region_from_arn(asg_arn),
                            'estimated_monthly_savings': estimated_monthly_savings,
                            'recommendation_source': 'aws_compute_optimizer'
                        })

                next_token = response.get('nextToken')
                if not next_token:
                    break

            return recommendations

        except self.client.exceptions.OptInRequiredException:
            logger.warning("AWS Compute Optimizer not enabled for Auto Scaling Groups")
            return []
        except Exception as e:
            logger.error(f"Error getting ASG recommendations: {str(e)}")
            return []

    def get_all_recommendations(self) -> Dict[str, List[Dict]]:
        """
        Get all types of recommendations.
        Falls back to basic CloudWatch analysis if Compute Optimizer is not enabled.

        Returns:
            Dictionary with recommendations by type
        """
        # Try Compute Optimizer first
        recommendations = {
            'ec2_instances': self.get_ec2_recommendations(),
            'ebs_volumes': self.get_ebs_recommendations(),
            'lambda_functions': self.get_lambda_recommendations(),
            'auto_scaling_groups': self.get_auto_scaling_group_recommendations()
        }

        # Check if Compute Optimizer returned any results
        total_recs = sum(len(recs) for recs in recommendations.values())

        if total_recs == 0:
            # Fallback to basic CloudWatch-based analysis
            logger.info("Compute Optimizer returned no recommendations, using basic CloudWatch analysis")
            recommendations = self.basic_analyzer.get_all_recommendations()

        return recommendations
