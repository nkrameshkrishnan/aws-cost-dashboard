"""
Health check and diagnostic endpoints.
"""
from fastapi import APIRouter, HTTPException
import logging

from app.config import settings
from app.aws.session_manager import session_manager
from app.core.cache import cache_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/status")
async def get_system_status():
    """
    Get system status including AWS and Redis connectivity.
    """
    status = {
        "app": {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT
        },
        "aws": {
            "configured": False,
            "profiles": [],
            "error": None
        },
        "cache": {
            "connected": False,
            "error": None
        }
    }

    # Check AWS profiles
    try:
        profiles = session_manager.list_profiles()
        status["aws"]["profiles"] = profiles
        status["aws"]["configured"] = len(profiles) > 0
    except Exception as e:
        status["aws"]["error"] = str(e)
        logger.error(f"AWS profile check failed: {e}")

    # Check Redis connection
    try:
        cache_stats = cache_manager.get_stats()
        status["cache"]["connected"] = cache_stats.get("connected", False)
        status["cache"]["stats"] = cache_stats
    except Exception as e:
        status["cache"]["error"] = str(e)
        logger.error(f"Cache check failed: {e}")

    return status


@router.get("/test-aws/{profile_name}")
async def test_aws_profile(profile_name: str):
    """
    Test AWS profile connectivity and permissions.
    """
    try:
        # Validate the profile
        validation = session_manager.validate_profile(profile_name)

        if not validation["valid"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid AWS profile: {validation.get('error', 'Unknown error')}"
            )

        return {
            "status": "success",
            "profile": profile_name,
            "account_id": validation.get("account_id"),
            "user_id": validation.get("user_id"),
            "arn": validation.get("arn")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AWS profile test failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"AWS connection failed: {str(e)}"
        )
