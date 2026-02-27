"""
Basic right-sizing analyzer using CloudWatch metrics and Trusted Advisor.
Alternative to AWS Compute Optimizer that works immediately.
"""
import boto3
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class BasicRightSizingAnalyzer:
    """Analyzes resources using CloudWatch metrics for right-sizing recommendations."""

    def __init__(self, session: boto3.Session, region: str):
        """
        Initialize analyzer.

        Args:
            session: Boto3 session with AWS credentials
            region: AWS region to analyze
        """
        self.session = session
        self.region = region
        self.ec2 = session.client('ec2', region_name=region)
        self.cloudwatch = session.client('cloudwatch', region_name=region)
        self.pricing_client = session.client('pricing', region_name='us-east-1')

        # Try to get Trusted Advisor client
        try:
            self.support = session.client('support', region_name='us-east-1')
            self.trusted_advisor_available = True
        except Exception as e:
            logger.warning(f"Trusted Advisor not available: {e}")
            self.trusted_advisor_available = False

    def get_ec2_recommendations(self, days: int = 7) -> List[Dict]:
        """
        Analyze EC2 instances using CloudWatch CPU metrics.

        Args:
            days: Number of days to analyze (default: 7)

        Returns:
            List of EC2 right-sizing recommendations
        """
        recommendations = []

        try:
            # Get all EC2 instances
            response = self.ec2.describe_instances()

            for reservation in response.get('Reservations', []):
                for instance in reservation.get('Instances', []):
                    instance_id = instance['InstanceId']
                    instance_type = instance['InstanceType']
                    state = instance['State']['Name']

                    # Skip terminated instances
                    if state == 'terminated':
                        continue

                    # Get instance name from tags
                    instance_name = instance_id
                    for tag in instance.get('Tags', []):
                        if tag['Key'] == 'Name':
                            instance_name = tag['Value']
                            break

                    # Get CPU utilization for running instances
                    if state == 'running':
                        cpu_stats = self._get_cpu_utilization(instance_id, days)

                        if cpu_stats:
                            avg_cpu = cpu_stats['average']
                            max_cpu = cpu_stats['max']

                            # Determine finding based on CPU utilization
                            finding = None
                            recommendation = None
                            estimated_savings = 0.0

                            if avg_cpu < 10:
                                finding = "Idle"
                                recommendation = "Consider stopping or terminating this instance"
                                estimated_savings = self._estimate_instance_cost(instance_type) * 0.95
                            elif avg_cpu < 40:
                                finding = "Overprovisioned"
                                smaller_type = self._suggest_smaller_instance(instance_type)
                                if smaller_type:
                                    recommendation = smaller_type
                                    current_cost = self._estimate_instance_cost(instance_type)
                                    new_cost = self._estimate_instance_cost(smaller_type)
                                    estimated_savings = current_cost - new_cost
                            elif max_cpu > 90:
                                finding = "Underprovisioned"
                                recommendation = self._suggest_larger_instance(instance_type)
                            else:
                                finding = "Optimized"
                                recommendation = "No changes recommended"

                            if finding in ['Idle', 'Overprovisioned', 'Underprovisioned']:
                                recommendations.append({
                                    'resource_arn': f"arn:aws:ec2:{self.region}::instance/{instance_id}",
                                    'resource_name': str(instance_name),
                                    'resource_type': 'ec2_instance',
                                    'current_config': str(instance_type),
                                    'recommended_config': str(recommendation) if recommendation else "Stop or terminate",
                                    'finding': str(finding),
                                    'region': str(self.region),
                                    'cpu_utilization': float(avg_cpu) if avg_cpu is not None else None,
                                    'memory_utilization': None,
                                    'performance_risk': 1.0 if finding == 'Underprovisioned' else 0.0,
                                    'estimated_monthly_savings': float(estimated_savings),
                                    'savings_percentage': float((estimated_savings / self._estimate_instance_cost(instance_type) * 100)) if estimated_savings > 0 else 0.0,
                                    'recommendation_source': 'cloudwatch_metrics'
                                })

                    # Flag stopped instances
                    elif state == 'stopped':
                        # Check how long it's been stopped
                        state_transition = instance.get('StateTransitionReason', '')

                        recommendations.append({
                            'resource_arn': f"arn:aws:ec2:{self.region}::instance/{instance_id}",
                            'resource_name': str(instance_name),
                            'resource_type': 'ec2_instance',
                            'current_config': str(instance_type),
                            'recommended_config': 'Terminate if no longer needed',
                            'finding': 'Stopped',
                            'region': str(self.region),
                            'cpu_utilization': 0.0,
                            'memory_utilization': None,
                            'performance_risk': 0.0,
                            'estimated_monthly_savings': float(self._estimate_instance_cost(instance_type) * 0.3),  # EBS costs remain
                            'savings_percentage': 70.0,
                            'recommendation_source': 'cloudwatch_metrics'
                        })

            return recommendations

        except Exception as e:
            logger.error(f"Error analyzing EC2 instances: {str(e)}", exc_info=True)
            return []

    def get_ebs_recommendations(self, days: int = 7) -> List[Dict]:
        """
        Analyze EBS volumes using CloudWatch IOPS metrics.

        Args:
            days: Number of days to analyze

        Returns:
            List of EBS volume recommendations
        """
        recommendations = []

        try:
            # Get all EBS volumes
            response = self.ec2.describe_volumes()

            for volume in response.get('Volumes', []):
                volume_id = volume['VolumeId']
                volume_type = volume['VolumeType']
                volume_size = volume['Size']
                state = volume['State']

                # Get volume name from tags
                volume_name = volume_id
                for tag in volume.get('Tags', []):
                    if tag['Key'] == 'Name':
                        volume_name = tag['Value']
                        break

                # Check if volume is unattached
                if state == 'available':
                    recommendations.append({
                        'resource_arn': f"arn:aws:ec2:{self.region}::volume/{volume_id}",
                        'resource_name': str(volume_name),
                        'resource_type': 'ebs_volume',
                        'current_config': f"{volume_type} {volume_size}GB",
                        'recommended_config': 'Delete unused volume',
                        'finding': 'Unattached',
                        'region': str(self.region),
                        'cpu_utilization': None,
                        'memory_utilization': None,
                        'performance_risk': 0.0,
                        'estimated_monthly_savings': float(self._estimate_ebs_cost(volume_type, volume_size)),
                        'savings_percentage': 100.0,
                        'recommendation_source': 'cloudwatch_metrics'
                    })

                # Check IOPS utilization for attached volumes
                elif state == 'in-use':
                    iops_stats = self._get_volume_iops(volume_id, days)

                    if iops_stats and iops_stats['max'] < 100:
                        # Very low IOPS usage
                        if volume_type in ['io1', 'io2']:
                            recommendations.append({
                                'resource_arn': f"arn:aws:ec2:{self.region}::volume/{volume_id}",
                                'resource_name': str(volume_name),
                                'resource_type': 'ebs_volume',
                                'current_config': f"{volume_type} {volume_size}GB",
                                'recommended_config': f"gp3 {volume_size}GB",
                                'finding': 'Overprovisioned',
                                'region': str(self.region),
                                'cpu_utilization': None,
                                'memory_utilization': None,
                                'performance_risk': 0.0,
                                'estimated_monthly_savings': float(self._estimate_ebs_cost(volume_type, volume_size) - self._estimate_ebs_cost('gp3', volume_size)),
                                'savings_percentage': 40.0,
                                'recommendation_source': 'cloudwatch_metrics'
                            })

            return recommendations

        except Exception as e:
            logger.error(f"Error analyzing EBS volumes: {str(e)}", exc_info=True)
            return []

    def get_lambda_recommendations(self) -> List[Dict]:
        """
        Analyze Lambda functions for over-provisioned memory.

        Returns:
            List of Lambda recommendations
        """
        recommendations = []

        try:
            lambda_client = self.session.client('lambda', region_name=self.region)

            # Get all Lambda functions
            paginator = lambda_client.get_paginator('list_functions')

            for page in paginator.paginate():
                for function in page['Functions']:
                    function_name = function['FunctionName']
                    memory_size = function['MemorySize']

                    # Get function statistics
                    stats = self._get_lambda_stats(function_name, days=7)

                    if stats:
                        avg_duration = stats.get('avg_duration', 0)
                        max_memory_used = stats.get('max_memory_used', 0)

                        # If max memory used is < 60% of allocated, recommend downsizing
                        if max_memory_used and max_memory_used < (memory_size * 0.6):
                            recommended_memory = self._round_to_lambda_memory(max_memory_used * 1.2)

                            if recommended_memory < memory_size:
                                # Estimate savings (Lambda pricing is proportional to memory)
                                savings_percentage = float(((memory_size - recommended_memory) / memory_size) * 100)

                                recommendations.append({
                                    'resource_arn': str(function['FunctionArn']),
                                    'resource_name': str(function_name),
                                    'resource_type': 'lambda_function',
                                    'current_config': f"{memory_size}MB",
                                    'recommended_config': f"{recommended_memory}MB",
                                    'finding': 'Overprovisioned',
                                    'region': str(self.region),
                                    'cpu_utilization': None,
                                    'memory_utilization': float((max_memory_used / memory_size) * 100),
                                    'performance_risk': 0.0,
                                    'estimated_monthly_savings': float(5.0 * (savings_percentage / 100)),  # Rough estimate
                                    'savings_percentage': savings_percentage,
                                    'recommendation_source': 'cloudwatch_metrics'
                                })

            return recommendations

        except Exception as e:
            logger.error(f"Error analyzing Lambda functions: {str(e)}", exc_info=True)
            return []

    def get_all_recommendations(self, days: int = 7) -> Dict[str, List[Dict]]:
        """
        Get all right-sizing recommendations.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with recommendations by resource type
        """
        return {
            'ec2_instances': self.get_ec2_recommendations(days),
            'ebs_volumes': self.get_ebs_recommendations(days),
            'lambda_functions': self.get_lambda_recommendations(),
            'auto_scaling_groups': []  # Not implemented in basic analyzer
        }

    # Helper methods

    def _get_cpu_utilization(self, instance_id: str, days: int) -> Optional[Dict]:
        """Get CPU utilization statistics for an instance."""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=days)

            response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/EC2',
                MetricName='CPUUtilization',
                Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,  # 1 hour periods
                Statistics=['Average', 'Maximum']
            )

            datapoints = response.get('Datapoints', [])
            if not datapoints:
                return None

            averages = [dp['Average'] for dp in datapoints]
            maximums = [dp['Maximum'] for dp in datapoints]

            return {
                'average': sum(averages) / len(averages),
                'max': max(maximums) if maximums else 0
            }

        except Exception as e:
            logger.debug(f"Could not get CPU metrics for {instance_id}: {e}")
            return None

    def _get_volume_iops(self, volume_id: str, days: int) -> Optional[Dict]:
        """Get IOPS statistics for a volume."""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=days)

            response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/EBS',
                MetricName='VolumeReadOps',
                Dimensions=[{'Name': 'VolumeId', 'Value': volume_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=['Sum']
            )

            datapoints = response.get('Datapoints', [])
            if not datapoints:
                return {'max': 0, 'average': 0}

            sums = [dp['Sum'] for dp in datapoints]
            return {
                'max': max(sums) if sums else 0,
                'average': sum(sums) / len(sums) if sums else 0
            }

        except Exception as e:
            logger.debug(f"Could not get IOPS metrics for {volume_id}: {e}")
            return None

    def _get_lambda_stats(self, function_name: str, days: int) -> Optional[Dict]:
        """Get Lambda function statistics."""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=days)

            # Get duration
            duration_response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Duration',
                Dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=['Average']
            )

            # Get memory used (if available)
            memory_response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='MaxMemoryUsed',
                Dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=['Maximum']
            )

            duration_points = duration_response.get('Datapoints', [])
            memory_points = memory_response.get('Datapoints', [])

            return {
                'avg_duration': sum(dp['Average'] for dp in duration_points) / len(duration_points) if duration_points else 0,
                'max_memory_used': max(dp['Maximum'] for dp in memory_points) if memory_points else 0
            }

        except Exception as e:
            logger.debug(f"Could not get Lambda stats for {function_name}: {e}")
            return None

    def _suggest_smaller_instance(self, instance_type: str) -> Optional[str]:
        """Suggest a smaller instance type."""
        # Simple mapping for common instance families
        downsize_map = {
            't3.2xlarge': 't3.xlarge',
            't3.xlarge': 't3.large',
            't3.large': 't3.medium',
            't3.medium': 't3.small',
            't3.small': 't3.micro',
            't2.2xlarge': 't2.xlarge',
            't2.xlarge': 't2.large',
            't2.large': 't2.medium',
            't2.medium': 't2.small',
            't2.small': 't2.micro',
            'm5.2xlarge': 'm5.xlarge',
            'm5.xlarge': 'm5.large',
            'm5.large': 'm5.medium',
            'm5n.2xlarge': 'm5n.xlarge',
            'm5n.xlarge': 'm5n.large',
            'm5a.2xlarge': 'm5a.xlarge',
            'm5a.xlarge': 'm5a.large',
            'm5a.large': 'm5a.medium',
        }
        return downsize_map.get(instance_type)

    def _suggest_larger_instance(self, instance_type: str) -> str:
        """Suggest a larger instance type."""
        # Simple mapping for common instance families
        upsize_map = {
            't3.micro': 't3.small',
            't3.small': 't3.medium',
            't3.medium': 't3.large',
            't3.large': 't3.xlarge',
            't3.xlarge': 't3.2xlarge',
            't2.micro': 't2.small',
            't2.small': 't2.medium',
            't2.medium': 't2.large',
            't2.large': 't2.xlarge',
            't2.xlarge': 't2.2xlarge',
            'm5.medium': 'm5.large',
            'm5.large': 'm5.xlarge',
            'm5.xlarge': 'm5.2xlarge',
            'm5n.large': 'm5n.xlarge',
            'm5n.xlarge': 'm5n.2xlarge',
            'm5a.medium': 'm5a.large',
            'm5a.large': 'm5a.xlarge',
            'm5a.xlarge': 'm5a.2xlarge',
        }
        return upsize_map.get(instance_type, instance_type)

    def _estimate_instance_cost(self, instance_type: str) -> float:
        """Estimate monthly cost for an instance type (rough estimate)."""
        # Simplified pricing (actual varies by region)
        pricing_map = {
            't2.micro': 8.5,
            't2.small': 17.0,
            't2.medium': 34.0,
            't2.large': 68.0,
            't3.micro': 7.5,
            't3.small': 15.0,
            't3.medium': 30.0,
            't3.large': 60.0,
            't3.xlarge': 120.0,
            't3.2xlarge': 240.0,
            'm5.medium': 44.0,
            'm5.large': 88.0,
            'm5.xlarge': 176.0,
            'm5.2xlarge': 352.0,
            'm5n.large': 92.0,
            'm5n.xlarge': 184.0,
            'm5n.2xlarge': 368.0,
            'm5a.medium': 39.0,
            'm5a.large': 78.0,
            'm5a.xlarge': 156.0,
            'm5a.2xlarge': 312.0,
        }
        return pricing_map.get(instance_type, 50.0)  # Default estimate

    def _estimate_ebs_cost(self, volume_type: str, size_gb: int) -> float:
        """Estimate monthly cost for EBS volume."""
        # Price per GB per month
        pricing_map = {
            'gp2': 0.10,
            'gp3': 0.08,
            'io1': 0.125,
            'io2': 0.125,
            'st1': 0.045,
            'sc1': 0.025
        }
        price_per_gb = pricing_map.get(volume_type, 0.10)
        return size_gb * price_per_gb

    def _round_to_lambda_memory(self, memory_mb: float) -> int:
        """Round memory to valid Lambda memory size (64MB increments)."""
        valid_sizes = [128, 256, 512, 1024, 1536, 2048, 3008]
        for size in valid_sizes:
            if memory_mb <= size:
                return size
        return 3008  # Max
