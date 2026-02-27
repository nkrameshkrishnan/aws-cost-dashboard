"""
Right-sizing recommendations API endpoints.
"""
from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy.orm import Session
import logging

from app.database.base import get_db
from app.aws.session_manager import AWSSessionManager
from app.services.rightsizing_service import RightSizingService
from app.schemas.rightsizing import (
    RightSizingRecommendation,
    RightSizingRecommendationsResponse,
    RightSizingSummary
)
from app.core.cache import cache_manager
from app.core.cache_config import RIGHTSIZING_RECOMMENDATIONS, RIGHTSIZING_SUMMARY

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/recommendations", response_model=RightSizingRecommendationsResponse)
def get_rightsizing_recommendations(
    profile_name: str = Query(..., description="AWS profile name"),
    resource_types: Optional[str] = Query(
        None,
        description="Comma-separated resource types: ec2_instance,ebs_volume,lambda_function,auto_scaling_group"
    ),
    db: Session = Depends(get_db)
):
    """
    Get right-sizing recommendations from AWS Compute Optimizer.

    This endpoint retrieves optimization recommendations for:
    - EC2 instances (over/under-provisioned)
    - EBS volumes (over-provisioned storage)
    - Lambda functions (memory optimization)
    - Auto Scaling Groups (instance type optimization)

    **Requirements:**
    - AWS Compute Optimizer must be enabled in the AWS account
    - Minimum 30 hours of resource utilization data required
    - IAM permissions: compute-optimizer:GetEC2InstanceRecommendations, etc.

    **Savings Potential:**
    Each recommendation includes estimated monthly savings and savings percentage.

    **Caching:** Results are cached for 30 minutes to improve performance.
    """
    # Generate cache key
    cache_key = cache_manager._generate_key(
        'rightsizing:recommendations',
        profile_name,
        resource_types or ''
    )

    # Try to get from cache
    cached_data = cache_manager.get(cache_key)
    if cached_data:
        logger.info(f"Cache hit for right-sizing recommendations: {profile_name}")
        return RightSizingRecommendationsResponse(**cached_data)

    logger.info(f"Cache miss for right-sizing recommendations: {profile_name}, fetching from AWS...")

    try:
        session_manager = AWSSessionManager(db=db)
        service = RightSizingService(session_manager, db=db)

        # Parse resource types if provided
        resource_type_list = None
        if resource_types:
            resource_type_list = [rt.strip() for rt in resource_types.split(',')]

        result = service.get_recommendations(profile_name, resource_type_list)

        # Cache the result
        cache_manager.set(cache_key, result.dict(), ttl=RIGHTSIZING_RECOMMENDATIONS)
        logger.info(f"Cached right-sizing recommendations for {profile_name} (TTL: {RIGHTSIZING_RECOMMENDATIONS}s)")

        return result

    except Exception as e:
        logger.error(f"Error getting right-sizing recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary", response_model=RightSizingSummary)
def get_rightsizing_summary(
    profile_name: str = Query(..., description="AWS profile name"),
    db: Session = Depends(get_db)
):
    """
    Get summary of right-sizing recommendations.

    Returns aggregated metrics:
    - Total recommendations by resource type
    - Total potential monthly savings
    - Breakdown by finding (overprovisioned, underprovisioned, optimized)
    """
    # Generate cache key
    cache_key = cache_manager._generate_key(
        'rightsizing:summary',
        profile_name
    )

    # Try to get from cache
    cached_data = cache_manager.get(cache_key)
    if cached_data:
        logger.info(f"Cache hit for right-sizing summary: {profile_name}")
        return RightSizingSummary(**cached_data)

    logger.info(f"Cache miss for right-sizing summary: {profile_name}, fetching from AWS...")

    try:
        session_manager = AWSSessionManager(db=db)
        service = RightSizingService(session_manager, db=db)
        result = service.get_summary(profile_name)

        # Cache the result
        cache_manager.set(cache_key, result.dict(), ttl=RIGHTSIZING_SUMMARY)
        logger.info(f"Cached right-sizing summary for {profile_name} (TTL: {RIGHTSIZING_SUMMARY}s)")

        return result

    except Exception as e:
        logger.error(f"Error getting right-sizing summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top-opportunities", response_model=List[RightSizingRecommendation])
def get_top_savings_opportunities(
    profile_name: str = Query(..., description="AWS profile name"),
    limit: int = Query(10, ge=1, le=50, description="Number of top opportunities to return"),
    db: Session = Depends(get_db)
):
    """
    Get top savings opportunities sorted by potential savings.

    Returns the recommendations with the highest estimated monthly savings,
    helping prioritize optimization efforts.
    """
    # Generate cache key
    cache_key = cache_manager._generate_key(
        'rightsizing:top-opportunities',
        profile_name,
        str(limit)
    )

    # Try to get from cache
    cached_data = cache_manager.get(cache_key)
    if cached_data:
        logger.info(f"Cache hit for top savings opportunities: {profile_name}")
        return [RightSizingRecommendation(**rec) for rec in cached_data]

    logger.info(f"Cache miss for top savings opportunities: {profile_name}, fetching from AWS...")

    try:
        session_manager = AWSSessionManager(db=db)
        service = RightSizingService(session_manager, db=db)
        result = service.get_top_savings_opportunities(profile_name, limit)

        # Cache the result (convert to list of dicts for caching)
        cache_manager.set(cache_key, [rec.dict() for rec in result], ttl=RIGHTSIZING_RECOMMENDATIONS)
        logger.info(f"Cached top savings opportunities for {profile_name} (TTL: {RIGHTSIZING_RECOMMENDATIONS}s)")

        return result

    except Exception as e:
        logger.error(f"Error getting top savings opportunities: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
