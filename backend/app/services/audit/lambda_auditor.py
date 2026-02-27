"""
Lambda function auditing service.
"""
import boto3
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from app.schemas.audit import (
    LambdaUnusedFunction,
    LambdaOverProvisionedFunction,
    LambdaAuditResults
)

logger = logging.getLogger(__name__)


# Lambda pricing (USD)
# Request pricing: $0.20 per 1M requests
# Duration pricing: $0.0000166667 per GB-second
LAMBDA_REQUEST_COST_PER_MILLION = 0.20
LAMBDA_DURATION_COST_PER_GB_SECOND = 0.0000166667


class LambdaAuditor:
    """Service for auditing Lambda functions."""

    @staticmethod
    def audit_lambda_functions(
        session: boto3.Session,
        days_unused_threshold: int = 30,
        memory_utilization_threshold: float = 60.0,
        lookback_days: int = 14
    ) -> LambdaAuditResults:
        """
        Audit Lambda functions for unused and over-provisioned functions.

        Args:
            session: Boto3 session
            days_unused_threshold: Days without invocations to consider unused
            memory_utilization_threshold: Memory utilization threshold (%)
            lookback_days: Days to look back for metrics

        Returns:
            LambdaAuditResults with findings
        """
        try:
            lambda_client = session.client('lambda')
            cloudwatch_client = session.client('cloudwatch')
            region = session.region_name or 'us-east-1'

            # Get all Lambda functions
            functions = []
            paginator = lambda_client.get_paginator('list_functions')
            for page in paginator.paginate():
                functions.extend(page.get('Functions', []))

            unused_functions = []
            over_provisioned_functions = []

            for function in functions:
                function_name = function['FunctionName']
                function_arn = function['FunctionArn']
                runtime = function.get('Runtime', 'unknown')
                memory_mb = function['MemorySize']
                last_modified = datetime.strptime(function['LastModified'], '%Y-%m-%dT%H:%M:%S.%f%z')

                # Get tags
                tags = {}
                try:
                    tags_response = lambda_client.list_tags(Resource=function_arn)
                    tags = tags_response.get('Tags', {})
                except Exception as e:
                    logger.warning(f"Could not get tags for {function_name}: {e}")

                # Get invocation metrics
                invocations = LambdaAuditor._get_total_invocations(
                    cloudwatch_client,
                    function_name,
                    lookback_days
                )

                # Check if unused
                if invocations == 0:
                    days_since_modified = (datetime.now(last_modified.tzinfo) - last_modified).days

                    if days_since_modified >= days_unused_threshold:
                        # Estimate cost (minimal if not invoked)
                        estimated_cost = 0.0  # No invocations = no cost

                        unused_function = LambdaUnusedFunction(
                            function_name=function_name,
                            function_arn=function_arn,
                            runtime=runtime,
                            memory_mb=memory_mb,
                            last_modified=last_modified,
                            days_since_invocation=days_since_modified,
                            estimated_monthly_cost=estimated_cost,
                            region=region,
                            tags=tags,
                            recommendation=f"Function not invoked in {days_since_modified} days. Consider deleting if no longer needed."
                        )
                        unused_functions.append(unused_function)

                # Check if over-provisioned (only for functions with invocations)
                elif invocations > 0:
                    avg_memory_used = LambdaAuditor._get_average_memory_used(
                        cloudwatch_client,
                        function_name,
                        lookback_days
                    )

                    if avg_memory_used is not None:
                        memory_utilization = (avg_memory_used / memory_mb) * 100

                        if memory_utilization < memory_utilization_threshold:
                            # Calculate costs and savings
                            avg_duration_ms = LambdaAuditor._get_average_duration(
                                cloudwatch_client,
                                function_name,
                                lookback_days
                            )

                            if avg_duration_ms:
                                # Estimate monthly invocations (scale up lookback to 30 days)
                                monthly_invocations = int(invocations * (30 / lookback_days))

                                # Calculate current cost
                                duration_seconds = avg_duration_ms / 1000
                                gb_memory = memory_mb / 1024
                                current_monthly_cost = (
                                    (monthly_invocations / 1000000) * LAMBDA_REQUEST_COST_PER_MILLION +
                                    monthly_invocations * duration_seconds * gb_memory * LAMBDA_DURATION_COST_PER_GB_SECOND
                                )

                                # Calculate optimal memory and potential savings
                                optimal_memory_mb = int(avg_memory_used * 1.2)  # 20% buffer
                                optimal_gb_memory = optimal_memory_mb / 1024
                                optimal_monthly_cost = (
                                    (monthly_invocations / 1000000) * LAMBDA_REQUEST_COST_PER_MILLION +
                                    monthly_invocations * duration_seconds * optimal_gb_memory * LAMBDA_DURATION_COST_PER_GB_SECOND
                                )

                                potential_savings = current_monthly_cost - optimal_monthly_cost

                                if potential_savings > 0.10:  # Only flag if savings > $0.10/month
                                    over_provisioned_function = LambdaOverProvisionedFunction(
                                        function_name=function_name,
                                        function_arn=function_arn,
                                        runtime=runtime,
                                        configured_memory_mb=memory_mb,
                                        avg_memory_used_mb=round(avg_memory_used, 0),
                                        memory_utilization_percent=round(memory_utilization, 1),
                                        monthly_invocations=monthly_invocations,
                                        estimated_monthly_cost=round(current_monthly_cost, 2),
                                        potential_monthly_savings=round(potential_savings, 2),
                                        region=region,
                                        tags=tags,
                                        recommendation=f"Memory utilization is {memory_utilization:.1f}%. Consider reducing memory from {memory_mb}MB to {optimal_memory_mb}MB to save ~${potential_savings:.2f}/month."
                                    )
                                    over_provisioned_functions.append(over_provisioned_function)

            # Calculate totals
            total_unused_cost = sum(f.estimated_monthly_cost for f in unused_functions)
            total_over_provisioned_waste = sum(f.potential_monthly_savings for f in over_provisioned_functions)
            total_savings = total_unused_cost + total_over_provisioned_waste

            return LambdaAuditResults(
                unused_functions=unused_functions,
                over_provisioned_functions=over_provisioned_functions,
                total_unused_cost=round(total_unused_cost, 2),
                total_over_provisioned_waste=round(total_over_provisioned_waste, 2),
                total_potential_savings=round(total_savings, 2)
            )

        except Exception as e:
            logger.error(f"Error auditing Lambda functions: {e}")
            return LambdaAuditResults()

    @staticmethod
    def _get_total_invocations(
        cloudwatch_client,
        function_name: str,
        lookback_days: int
    ) -> int:
        """Get total number of invocations for a Lambda function."""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=lookback_days)

            response = cloudwatch_client.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Invocations',
                Dimensions=[
                    {'Name': 'FunctionName', 'Value': function_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,  # 1 day
                Statistics=['Sum']
            )

            datapoints = response.get('Datapoints', [])
            if datapoints:
                total_invocations = sum(dp['Sum'] for dp in datapoints)
                return int(total_invocations)
            return 0

        except Exception as e:
            logger.warning(f"Could not get invocation metrics for {function_name}: {e}")
            return 0

    @staticmethod
    def _get_average_memory_used(
        cloudwatch_client,
        function_name: str,
        lookback_days: int
    ) -> Optional[float]:
        """Get average memory used by a Lambda function."""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=lookback_days)

            # CloudWatch Insights query would be better, but using available metrics
            # This is an approximation using duration and memory size
            response = cloudwatch_client.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Duration',
                Dimensions=[
                    {'Name': 'FunctionName', 'Value': function_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,  # 1 day
                Statistics=['Average']
            )

            datapoints = response.get('Datapoints', [])
            if datapoints:
                # Since we can't get actual memory used from basic CloudWatch metrics,
                # we'll use a heuristic based on duration
                # In practice, you'd want to use CloudWatch Logs Insights or X-Ray
                # For now, estimate at 70% of configured memory as a baseline
                # This should be replaced with actual memory usage data in production
                return None  # Return None to skip over-provisioned check without actual data
            return None

        except Exception as e:
            logger.warning(f"Could not get memory metrics for {function_name}: {e}")
            return None

    @staticmethod
    def _get_average_duration(
        cloudwatch_client,
        function_name: str,
        lookback_days: int
    ) -> Optional[float]:
        """Get average duration (ms) for a Lambda function."""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=lookback_days)

            response = cloudwatch_client.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Duration',
                Dimensions=[
                    {'Name': 'FunctionName', 'Value': function_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,  # 1 day
                Statistics=['Average']
            )

            datapoints = response.get('Datapoints', [])
            if datapoints:
                avg_duration = sum(dp['Average'] for dp in datapoints) / len(datapoints)
                return avg_duration
            return None

        except Exception as e:
            logger.warning(f"Could not get duration metrics for {function_name}: {e}")
            return None
