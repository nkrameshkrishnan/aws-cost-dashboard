"""
Pydantic schemas for cost-related API requests and responses.
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date


class CostSummaryRequest(BaseModel):
    """Request schema for cost summary."""
    profile_names: List[str] = Field(..., description="List of AWS profile names")
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format")


class CostSummaryResponse(BaseModel):
    """Response schema for cost summary."""
    profile_name: str
    start_date: str
    end_date: str
    total_cost: float
    currency: str = "USD"
    period_count: int


class DailyCostRecord(BaseModel):
    """Schema for a single daily cost record."""
    date: str
    cost: float


class DailyCostsResponse(BaseModel):
    """Response schema for daily costs."""
    profile_name: str
    start_date: str
    end_date: str
    daily_costs: List[DailyCostRecord]
    total_cost: float


class ServiceCostRecord(BaseModel):
    """Schema for a single service cost record."""
    service: str
    cost: float


class ServiceBreakdownResponse(BaseModel):
    """Response schema for service breakdown."""
    profile_name: str
    start_date: str
    end_date: str
    services: List[ServiceCostRecord]
    total_cost: float


class MonthlyTrendRecord(BaseModel):
    """Schema for monthly cost trend record."""
    month: str
    cost: float
    mom_change_percent: Optional[float] = None


class CostTrendResponse(BaseModel):
    """Response schema for cost trend."""
    profile_name: str
    months: int
    trend_data: List[MonthlyTrendRecord]


class MoMComparisonResponse(BaseModel):
    """Response schema for month-over-month comparison."""
    current_month: dict
    previous_month: dict
    change_amount: float
    change_percent: float


class YoYComparisonResponse(BaseModel):
    """Response schema for year-over-year comparison."""
    current_period: dict
    previous_year_period: dict
    change_amount: float
    change_percent: float


class DailyForecastRecord(BaseModel):
    """Schema for a single daily forecast record."""
    date: str
    forecasted_cost: float


class ForecastResponse(BaseModel):
    """Response schema for cost forecast."""
    profile_name: str
    forecast_period_start: str
    forecast_period_end: str
    forecasted_cost: float
    currency: str = "USD"
    error: Optional[str] = None
    daily_forecast: Optional[List[DailyForecastRecord]] = None


class MultiProfileCostResponse(BaseModel):
    """Response schema for multi-profile aggregated costs."""
    profiles: List[str]
    start_date: str
    end_date: str
    total_cost: float
    profile_breakdown: List[dict]


class DashboardDataResponse(BaseModel):
    """Optimized response schema with all dashboard data in one response."""
    last_30_days: CostSummaryResponse
    current_month: CostSummaryResponse
    mom_comparison: MoMComparisonResponse
    forecast: ForecastResponse


class DrillDownRecord(BaseModel):
    """Schema for a single drill-down cost record."""
    dimension_value: str = Field(..., description="Value of the dimension (e.g., service name, region)")
    cost: float = Field(..., description="Cost for this dimension value")
    percentage: float = Field(..., description="Percentage of total cost")


class DrillDownResponse(BaseModel):
    """Response schema for drill-down cost analysis."""
    profile_name: str
    start_date: str
    end_date: str
    dimension: str = Field(..., description="Dimension used for drill-down (SERVICE, REGION, etc.)")
    filters: dict = Field(default_factory=dict, description="Applied filters")
    total_cost: float
    breakdown: List[DrillDownRecord]
    currency: str = "USD"
