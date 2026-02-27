"""
KPI API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict

from app.database.base import get_db
from app.services.kpi_service import KPIService
from app.models.kpi import (
    KPIValue,
    KPIMetrics,
    KPIDefinition,
    AWS_COST_KPI_DEFINITIONS
)

router = APIRouter()


@router.get("/definitions", response_model=Dict[str, KPIDefinition])
async def get_kpi_definitions():
    """Get all KPI definitions."""
    return AWS_COST_KPI_DEFINITIONS


@router.get("/definitions/{kpi_id}", response_model=KPIDefinition)
async def get_kpi_definition(kpi_id: str):
    """Get a specific KPI definition."""
    definition = AWS_COST_KPI_DEFINITIONS.get(kpi_id)
    if not definition:
        raise HTTPException(status_code=404, detail=f"KPI not found: {kpi_id}")
    return definition


@router.get("/calculate/{profile_name}", response_model=Dict[str, KPIValue])
async def calculate_all_kpis(
    profile_name: str,
    db: Session = Depends(get_db)
):
    """Calculate all KPIs for a given profile."""
    kpi_service = KPIService(db)
    try:
        kpis = await kpi_service.calculate_all_kpis(profile_name)
        return kpis
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate KPIs: {str(e)}")


@router.get("/calculate/{profile_name}/{kpi_id}", response_model=KPIValue)
async def calculate_kpi(
    profile_name: str,
    kpi_id: str,
    db: Session = Depends(get_db)
):
    """Calculate a specific KPI for a given profile."""
    kpi_service = KPIService(db)

    calculator_map = {
        "cost_efficiency": kpi_service.calculate_cost_efficiency,
        "budget_utilization": kpi_service.calculate_budget_utilization,
        "cost_growth_rate": kpi_service.calculate_cost_growth_rate,
        "daily_spend_rate": kpi_service.calculate_daily_spend_rate,
        "savings_potential": kpi_service.calculate_savings_potential,
        "resource_waste_ratio": kpi_service.calculate_resource_waste_ratio,
    }

    calculator = calculator_map.get(kpi_id)
    if not calculator:
        raise HTTPException(status_code=404, detail=f"Unknown KPI: {kpi_id}")

    try:
        kpi_value = await calculator(profile_name)
        return kpi_value
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate KPI: {str(e)}")


@router.get("/metrics/{profile_name}/{kpi_id}", response_model=KPIMetrics)
async def get_kpi_metrics(
    profile_name: str,
    kpi_id: str,
    days_history: int = 30,
    db: Session = Depends(get_db)
):
    """Get complete KPI metrics including history."""
    kpi_service = KPIService(db)

    try:
        metrics = await kpi_service.get_kpi_metrics(kpi_id, profile_name, days_history)
        return metrics
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get KPI metrics: {str(e)}")
