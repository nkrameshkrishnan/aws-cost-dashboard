"""
Right-sizing service for AWS resource optimization recommendations.
"""
from typing import List, Dict, Optional
import logging

from app.aws.session_manager import AWSSessionManager
from app.aws.compute_optimizer import ComputeOptimizerClient
from app.schemas.rightsizing import (
    RightSizingRecommendation,
    RightSizingRecommendationsResponse,
    RightSizingSummary
)

logger = logging.getLogger(__name__)


class RightSizingService:
    """Service for retrieving and processing right-sizing recommendations."""

    def __init__(self, session_manager: AWSSessionManager, db=None):
        self.session_manager = session_manager
        self.db = db

    def get_recommendations(
        self,
        profile_name: str,
        resource_types: Optional[List[str]] = None
    ) -> RightSizingRecommendationsResponse:
        """
        Get right-sizing recommendations for a profile.

        Args:
            profile_name: AWS profile name
            resource_types: Filter by resource types (ec2_instance, ebs_volume, lambda_function, auto_scaling_group)

        Returns:
            Right-sizing recommendations with savings potential
        """
        try:
            # Get region from database if available
            region = 'us-east-1'  # Default
            if self.db:
                from app.models.aws_account import AWSAccount
                account = self.db.query(AWSAccount).filter(AWSAccount.name == profile_name).first()
                if account:
                    region = account.region

            # Get AWS session
            session = self.session_manager.get_session(profile_name)
            optimizer_client = ComputeOptimizerClient(session, region=region)

            # Get all recommendations
            all_recs = optimizer_client.get_all_recommendations()

            # Flatten and filter
            recommendations = []
            for rec_type, rec_list in all_recs.items():
                # Convert rec_type from plural to singular
                resource_type_map = {
                    'ec2_instances': 'ec2_instance',
                    'ebs_volumes': 'ebs_volume',
                    'lambda_functions': 'lambda_function',
                    'auto_scaling_groups': 'auto_scaling_group'
                }
                resource_type = resource_type_map.get(rec_type, rec_type)

                # Filter if resource_types specified
                if resource_types and resource_type not in resource_types:
                    continue

                for rec in rec_list:
                    recommendations.append(RightSizingRecommendation(**rec))

            # Calculate totals
            total_monthly_savings = sum(r.estimated_monthly_savings for r in recommendations)

            # Count by type
            recommendations_by_type = {}
            for rec in recommendations:
                rec_type = rec.resource_type
                recommendations_by_type[rec_type] = recommendations_by_type.get(rec_type, 0) + 1

            return RightSizingRecommendationsResponse(
                profile_name=profile_name,
                total_recommendations=len(recommendations),
                total_monthly_savings=total_monthly_savings,
                recommendations_by_type=recommendations_by_type,
                recommendations=recommendations
            )

        except Exception as e:
            logger.error(f"Error getting right-sizing recommendations: {str(e)}", exc_info=True)
            # Return empty response on error
            return RightSizingRecommendationsResponse(
                profile_name=profile_name,
                total_recommendations=0,
                total_monthly_savings=0.0,
                recommendations_by_type={},
                recommendations=[]
            )

    def get_summary(self, profile_name: str) -> RightSizingSummary:
        """
        Get summary of right-sizing recommendations.

        Args:
            profile_name: AWS profile name

        Returns:
            Summary of recommendations and savings potential
        """
        try:
            # Get all recommendations
            recs_response = self.get_recommendations(profile_name)

            # Count by type
            type_counts = recs_response.recommendations_by_type
            ec2_count = type_counts.get('ec2_instance', 0)
            ebs_count = type_counts.get('ebs_volume', 0)
            lambda_count = type_counts.get('lambda_function', 0)
            asg_count = type_counts.get('auto_scaling_group', 0)

            # Count by finding
            overprovisioned = sum(1 for r in recs_response.recommendations if 'overprovisioned' in r.finding.lower())
            underprovisioned = sum(1 for r in recs_response.recommendations if 'underprovisioned' in r.finding.lower())
            optimized = sum(1 for r in recs_response.recommendations if 'optimized' in r.finding.lower())

            return RightSizingSummary(
                profile_name=profile_name,
                total_ec2_recommendations=ec2_count,
                total_ebs_recommendations=ebs_count,
                total_lambda_recommendations=lambda_count,
                total_asg_recommendations=asg_count,
                total_potential_savings=recs_response.total_monthly_savings,
                overprovisioned_resources=overprovisioned,
                underprovisioned_resources=underprovisioned,
                optimized_resources=optimized
            )

        except Exception as e:
            logger.error(f"Error getting right-sizing summary: {str(e)}", exc_info=True)
            # Return empty summary on error
            return RightSizingSummary(
                profile_name=profile_name,
                total_ec2_recommendations=0,
                total_ebs_recommendations=0,
                total_lambda_recommendations=0,
                total_asg_recommendations=0,
                total_potential_savings=0.0,
                overprovisioned_resources=0,
                underprovisioned_resources=0,
                optimized_resources=0
            )

    def get_top_savings_opportunities(
        self,
        profile_name: str,
        limit: int = 10
    ) -> List[RightSizingRecommendation]:
        """
        Get top savings opportunities.

        Args:
            profile_name: AWS profile name
            limit: Number of top recommendations to return

        Returns:
            Top recommendations sorted by savings potential
        """
        try:
            recs_response = self.get_recommendations(profile_name)

            # Sort by estimated monthly savings
            sorted_recs = sorted(
                recs_response.recommendations,
                key=lambda x: x.estimated_monthly_savings,
                reverse=True
            )

            return sorted_recs[:limit]
        except Exception as e:
            logger.error(f"Error getting top savings opportunities: {str(e)}", exc_info=True)
            return []
