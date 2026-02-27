from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class BusinessMetricCreate(BaseModel):
    """Schema for creating business metrics"""
    profile_name: str
    metric_date: str  # YYYY-MM-DD format
    active_users: Optional[int] = Field(None, ge=0)
    total_transactions: Optional[int] = Field(None, ge=0)
    api_calls: Optional[int] = Field(None, ge=0)
    data_processed_gb: Optional[float] = Field(None, ge=0)
    custom_metric_1: Optional[float] = None
    custom_metric_1_name: Optional[str] = None


class BusinessMetricResponse(BaseModel):
    """Schema for business metric response"""
    id: int
    profile_name: str
    metric_date: str
    active_users: Optional[int]
    total_transactions: Optional[int]
    api_calls: Optional[int]
    data_processed_gb: Optional[float]
    custom_metric_1: Optional[float]
    custom_metric_1_name: Optional[str]
    created_at: datetime
    updated_at: datetime


class UnitCostResponse(BaseModel):
    """Schema for unit cost calculations"""
    profile_name: str
    start_date: str
    end_date: str
    total_cost: float

    # Unit costs
    cost_per_user: Optional[float] = None
    cost_per_transaction: Optional[float] = None
    cost_per_api_call: Optional[float] = None
    cost_per_gb: Optional[float] = None
    cost_per_custom_metric: Optional[float] = None

    # Metrics totals
    total_users: Optional[int] = None
    total_transactions: Optional[int] = None
    total_api_calls: Optional[int] = None
    total_gb_processed: Optional[float] = None
    total_custom_metric: Optional[float] = None
    custom_metric_name: Optional[str] = None

    # Trend data
    trend: Optional[str] = None  # "improving", "degrading", "stable"
    mom_change_percent: Optional[float] = None


class UnitCostTrendResponse(BaseModel):
    """Schema for unit cost trend over time"""
    profile_name: str
    metric_type: str  # "cost_per_user", "cost_per_transaction", etc.
    trend_data: list[dict]  # [{date, unit_cost, total_cost, metric_value}]
