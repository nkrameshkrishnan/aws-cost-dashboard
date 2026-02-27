"""
Unit Cost API endpoints.
"""
from typing import List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.database.base import get_db
from app.schemas.unit_cost import (
    BusinessMetricCreate,
    BusinessMetricResponse,
    UnitCostResponse,
    UnitCostTrendResponse
)
from app.services.unit_cost_service import UnitCostService

router = APIRouter()


@router.post("/business-metrics", response_model=BusinessMetricResponse)
def create_business_metric(
    metric: BusinessMetricCreate,
    db: Session = Depends(get_db)
):
    """
    Create or update business metrics for unit cost calculation.

    This endpoint allows you to store operational metrics (users, transactions, etc.)
    that will be used to calculate unit costs.
    """
    service = UnitCostService(db)
    return service.create_business_metric(metric)


@router.get("/business-metrics", response_model=List[BusinessMetricResponse])
def get_business_metrics(
    profile_name: str = Query(..., description="AWS profile name"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Get business metrics for a date range.
    """
    service = UnitCostService(db)
    return service.get_business_metrics(profile_name, start_date, end_date)


@router.get("/calculate", response_model=UnitCostResponse)
def calculate_unit_costs(
    profile_name: str = Query(..., description="AWS profile name"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    region: str = Query("us-east-2", description="AWS region (default: us-east-2)"),
    db: Session = Depends(get_db)
):
    """
    Calculate unit costs for a period in a specific region.

    Computes various unit cost metrics:
    - Cost per active user
    - Cost per transaction
    - Cost per API call
    - Cost per GB processed
    - Custom metrics

    Requires business metrics to be configured via POST /business-metrics
    """
    service = UnitCostService(db)
    return service.calculate_unit_costs(profile_name, start_date, end_date, region)


@router.get("/trend", response_model=UnitCostTrendResponse)
def get_unit_cost_trend(
    profile_name: str = Query(..., description="AWS profile name"),
    metric_type: str = Query(
        ...,
        description="Metric type: cost_per_user, cost_per_transaction, cost_per_api_call, cost_per_gb"
    ),
    months: int = Query(6, ge=1, le=12, description="Number of months to analyze"),
    region: str = Query("us-east-2", description="AWS region (default: us-east-2)"),
    db: Session = Depends(get_db)
):
    """
    Get unit cost trend over time in a specific region.

    Shows how unit costs have changed month-over-month.
    """
    valid_metrics = ["cost_per_user", "cost_per_transaction", "cost_per_api_call", "cost_per_gb"]
    if metric_type not in valid_metrics:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid metric_type. Must be one of: {', '.join(valid_metrics)}"
        )

    service = UnitCostService(db)
    return service.get_unit_cost_trend(profile_name, metric_type, months, region)
