"""
Unit Cost API endpoints.
"""
from typing import List
from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.database.base import get_db
from app.schemas.unit_cost import (
    BusinessMetricCreate,
    BusinessMetricResponse,
    UnitCostResponse,
    UnitCostTrendResponse
)
from app.services.unit_cost_service import UnitCostService
from app.services.async_job_service import AsyncJobService
from app.models.async_job import JobType

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


# ==============================================================================
# Async Job Endpoints (for long-running operations)
# ==============================================================================


@router.post("/calculate/async")
def calculate_unit_costs_async(
    background_tasks: BackgroundTasks,
    profile_name: str = Query(..., description="AWS profile name"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    region: str = Query("us-east-2", description="AWS region (default: us-east-2)"),
    db: Session = Depends(get_db)
):
    """
    Calculate unit costs asynchronously (for slow AWS Cost Explorer API calls).

    Returns a job_id immediately. Poll GET /unit-costs/jobs/{job_id} to check status.
    """
    job_service = AsyncJobService(db)

    parameters = {
        "profile_name": profile_name,
        "start_date": start_date,
        "end_date": end_date,
        "region": region
    }

    job_id = job_service.create_job(JobType.UNIT_COST_CALCULATE, parameters)

    # Process job in background
    background_tasks.add_task(job_service.process_job, job_id)

    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Job created. Poll GET /unit-costs/jobs/{job_id} for status."
    }


@router.post("/trend/async")
def get_unit_cost_trend_async(
    background_tasks: BackgroundTasks,
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
    Get unit cost trend asynchronously (for slow AWS Cost Explorer API calls).

    Returns a job_id immediately. Poll GET /unit-costs/jobs/{job_id} to check status.
    """
    valid_metrics = ["cost_per_user", "cost_per_transaction", "cost_per_api_call", "cost_per_gb"]
    if metric_type not in valid_metrics:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid metric_type. Must be one of: {', '.join(valid_metrics)}"
        )

    job_service = AsyncJobService(db)

    parameters = {
        "profile_name": profile_name,
        "metric_type": metric_type,
        "months": months,
        "region": region
    }

    job_id = job_service.create_job(JobType.UNIT_COST_TREND, parameters)

    # Process job in background
    background_tasks.add_task(job_service.process_job, job_id)

    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Job created. Poll GET /unit-costs/jobs/{job_id} for status."
    }


@router.get("/jobs/{job_id}")
def get_job_status(
    job_id: str,
    db: Session = Depends(get_db)
):
    """
    Get the status of an async job.

    Response statuses:
    - pending: Job is queued
    - running: Job is currently executing
    - completed: Job finished successfully (includes result)
    - failed: Job failed (includes error message)
    """
    job_service = AsyncJobService(db)
    job_status = job_service.get_job_status(job_id)

    if not job_status:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return job_status
