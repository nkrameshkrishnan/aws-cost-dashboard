"""
Cost data API endpoints.
Provides endpoints for fetching and analyzing AWS cost data.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
import logging

from app.schemas.cost import (
    CostSummaryResponse,
    DailyCostsResponse,
    DailyCostRecord,
    ServiceBreakdownResponse,
    ServiceCostRecord,
    CostTrendResponse,
    MoMComparisonResponse,
    YoYComparisonResponse,
    ForecastResponse,
    MultiProfileCostResponse,
    DashboardDataResponse,
    DrillDownResponse,
    DrillDownRecord
)
from app.services.cost_processor import aggregate_multi_profile_costs
from app.services.cost_processor_db import DatabaseCostProcessor
from app.database.base import get_db
from app.core.security import get_current_active_user
from sqlalchemy.orm import Session as DBSession

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/dashboard", response_model=DashboardDataResponse)
async def get_dashboard_data(
    profile_name: str = Query(..., description="AWS account name"),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """
    Optimized endpoint that fetches all dashboard data in a single request.
    Returns last 30 days cost, current month cost, MoM comparison, and current month forecast.
    This reduces the number of API calls from 4+ to just 1.

    Note: Forecast is for the CURRENT MONTH to match Budget page projections.
    """
    from datetime import datetime, timedelta
    from dateutil.relativedelta import relativedelta

    try:
        # Calculate date ranges
        today = datetime.now().date()

        # Last 30 days
        last_30_days_start = (today - timedelta(days=30)).strftime("%Y-%m-%d")
        last_30_days_end = today.strftime("%Y-%m-%d")

        # Current month
        current_month_start = today.replace(day=1).strftime("%Y-%m-%d")
        current_month_end = (today.replace(day=1) + relativedelta(months=1) - timedelta(days=1)).strftime("%Y-%m-%d")

        # Fetch all data (with caching, this should be fast)
        last_30_days = DatabaseCostProcessor.get_cost_summary(
            db, profile_name, last_30_days_start, last_30_days_end
        )

        current_month = DatabaseCostProcessor.get_cost_summary(
            db, profile_name, current_month_start, current_month_end
        )

        mom_comparison = DatabaseCostProcessor.calculate_mom_change(
            db, profile_name, current_month_start, current_month_end
        )

        # Calculate projected month-end cost using AWS Cost Explorer forecast
        # This matches what AWS shows and what the Budget page uses
        current_spend = current_month['total_cost']
        days_remaining_in_month = (datetime.strptime(current_month_end, "%Y-%m-%d").date() - today).days + 1

        try:
            # Get AWS forecast for remainder of month using DAILY granularity
            # DAILY granularity is more accurate for partial month forecasts
            if days_remaining_in_month > 0:
                forecast_data = DatabaseCostProcessor.get_forecast(
                    db,
                    profile_name,
                    days_remaining_in_month,
                    granularity="DAILY"
                )
                forecast_remaining = forecast_data.get('forecasted_cost', 0.0)
                projected_month_total = current_spend + forecast_remaining
            else:
                # Month is over, use current spend
                projected_month_total = current_spend

            # Create forecast response with projected month-end total
            forecast = {
                'profile_name': profile_name,
                'forecast_period_start': current_month_start,
                'forecast_period_end': current_month_end,
                'forecasted_cost': round(projected_month_total, 2),
                'currency': 'USD'
            }

        except Exception as e:
            logger.warning(f"Failed to get AWS forecast, using current spend: {e}")
            # Fallback to current spend if forecast fails
            forecast = {
                'profile_name': profile_name,
                'forecast_period_start': current_month_start,
                'forecast_period_end': current_month_end,
                'forecasted_cost': round(current_spend, 2),
                'currency': 'USD'
            }

        return DashboardDataResponse(
            last_30_days=CostSummaryResponse(**last_30_days),
            current_month=CostSummaryResponse(**current_month),
            mom_comparison=MoMComparisonResponse(**mom_comparison),
            forecast=ForecastResponse(**forecast)
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching dashboard data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary", response_model=CostSummaryResponse)
async def get_cost_summary(
    profile_name: str = Query(..., description="AWS account name"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """
    Get cost summary for a specific account and date range.
    Uses database-stored AWS credentials.
    """
    try:
        summary = DatabaseCostProcessor.get_cost_summary(db, profile_name, start_date, end_date)
        return CostSummaryResponse(**summary)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching cost summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/daily", response_model=DailyCostsResponse)
async def get_daily_costs(
    profile_name: str = Query(..., description="AWS account name"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """
    Get daily cost breakdown using database-stored credentials.
    """
    try:
        daily_costs = DatabaseCostProcessor.get_daily_costs(db, profile_name, start_date, end_date)
        total_cost = sum(record['cost'] for record in daily_costs)

        return DailyCostsResponse(
            profile_name=profile_name,
            start_date=start_date,
            end_date=end_date,
            daily_costs=[DailyCostRecord(**record) for record in daily_costs],
            total_cost=round(total_cost, 2)
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching daily costs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-service", response_model=ServiceBreakdownResponse)
async def get_service_breakdown(
    profile_name: str = Query(..., description="AWS account name"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    top_n: int = Query(10, description="Number of top services to return"),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """
    Get cost breakdown by AWS service using database credentials.
    """
    try:
        services = DatabaseCostProcessor.get_service_breakdown(db, profile_name, start_date, end_date, top_n)
        total_cost = sum(record['cost'] for record in services)

        return ServiceBreakdownResponse(
            profile_name=profile_name,
            start_date=start_date,
            end_date=end_date,
            services=[ServiceCostRecord(**record) for record in services],
            total_cost=round(total_cost, 2)
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching service breakdown: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trend", response_model=CostTrendResponse)
async def get_cost_trend(
    profile_name: str = Query(..., description="AWS profile name"),
    months: int = Query(6, description="Number of months to include"),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """
    Get monthly cost trend for the past N months using database credentials.
    """
    try:
        trend_data = DatabaseCostProcessor.get_cost_trend(db, profile_name, months)

        return CostTrendResponse(
            profile_name=profile_name,
            months=months,
            trend_data=trend_data
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching cost trend: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mom-comparison", response_model=MoMComparisonResponse)
async def get_mom_comparison(
    profile_name: str = Query(..., description="AWS account name"),
    current_month_start: str = Query(..., description="Current month start (YYYY-MM-DD)"),
    current_month_end: str = Query(..., description="Current month end (YYYY-MM-DD)"),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """
    Get month-over-month cost comparison using database credentials.
    """
    try:
        comparison = DatabaseCostProcessor.calculate_mom_change(
            db,
            profile_name,
            current_month_start,
            current_month_end
        )

        return MoMComparisonResponse(**comparison)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error calculating MoM comparison: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/yoy-comparison", response_model=YoYComparisonResponse)
async def get_yoy_comparison(
    profile_name: str = Query(..., description="AWS account name"),
    current_period_start: str = Query(..., description="Current period start (YYYY-MM-DD)"),
    current_period_end: str = Query(..., description="Current period end (YYYY-MM-DD)"),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """
    Get year-over-year cost comparison using database credentials.
    """
    try:
        comparison = DatabaseCostProcessor.calculate_yoy_change(
            db,
            profile_name,
            current_period_start,
            current_period_end
        )

        return YoYComparisonResponse(**comparison)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error calculating YoY comparison: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/forecast", response_model=ForecastResponse)
async def get_cost_forecast(
    profile_name: str = Query(..., description="AWS account name"),
    days: int = Query(30, description="Number of days to forecast"),
    granularity: str = Query("MONTHLY", description="Granularity: DAILY or MONTHLY"),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """
    Get cost forecast for the next N days using database credentials.
    Supports DAILY or MONTHLY granularity.
    """
    try:
        forecast = DatabaseCostProcessor.get_forecast(db, profile_name, days, granularity)

        return ForecastResponse(
            profile_name=profile_name,
            **forecast
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching forecast: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/multi-profile", response_model=MultiProfileCostResponse)
async def get_multi_profile_costs(
    profile_names: List[str] = Query(..., description="List of AWS profile names"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    current_user: dict = Depends(get_current_active_user),
):
    """
    Get aggregated costs across multiple AWS profiles.
    """
    try:
        aggregated = aggregate_multi_profile_costs(
            profile_names,
            start_date,
            end_date
        )

        return MultiProfileCostResponse(**aggregated)
    except Exception as e:
        logger.error(f"Error fetching multi-profile costs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/drill-down", response_model=DrillDownResponse)
async def get_cost_drill_down(
    profile_name: str = Query(..., description="AWS account name"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    dimension: str = Query(..., description="Dimension to drill down by (SERVICE, REGION, LINKED_ACCOUNT, etc.)"),
    service: Optional[str] = Query(None, description="Filter by specific service"),
    region: Optional[str] = Query(None, description="Filter by specific region"),
    account_id: Optional[str] = Query(None, description="Filter by specific linked account"),
    db: DBSession = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """
    Get cost breakdown by a specific dimension with optional filters.

    Supports multi-level drill-down:
    1. Start with SERVICE dimension to see costs by service
    2. Add service filter and use REGION dimension to see regional breakdown for that service
    3. Add region filter and use LINKED_ACCOUNT dimension to see account breakdown

    Available dimensions:
    - SERVICE: AWS service names (e.g., Amazon EC2, Amazon S3)
    - REGION: AWS regions (e.g., us-east-1, eu-west-1)
    - LINKED_ACCOUNT: AWS account IDs for multi-account setups
    - USAGE_TYPE: Specific usage types
    - INSTANCE_TYPE: EC2 instance types (e.g., t3.medium)

    Example drill-down flow:
    1. GET /drill-down?dimension=SERVICE → See all services
    2. GET /drill-down?dimension=REGION&service=Amazon%20EC2 → See EC2 costs by region
    3. GET /drill-down?dimension=LINKED_ACCOUNT&service=Amazon%20EC2&region=us-east-1 → See accounts
    """
    try:
        # Build filters from query parameters
        filters = {}
        if service:
            filters["SERVICE"] = service
        if region:
            filters["REGION"] = region
        if account_id:
            filters["LINKED_ACCOUNT"] = account_id

        drill_down_data = DatabaseCostProcessor.get_cost_drill_down(
            db,
            profile_name,
            start_date,
            end_date,
            dimension,
            filters
        )

        return DrillDownResponse(**drill_down_data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching drill-down data: {e}")
        raise HTTPException(status_code=500, detail=str(e))
