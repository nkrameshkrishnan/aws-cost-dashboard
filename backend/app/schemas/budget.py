"""
Budget API schemas.
Pydantic models for budget request and response data.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class BudgetPeriod(str, Enum):
    """Budget period types."""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class BudgetAlertLevel(str, Enum):
    """Budget alert levels based on spending."""
    NORMAL = "normal"  # Under warning threshold
    WARNING = "warning"  # Over warning threshold
    CRITICAL = "critical"  # Over critical threshold
    EXCEEDED = "exceeded"  # Over 100% regardless of critical threshold


class BudgetCreate(BaseModel):
    """Schema for creating a new budget."""
    name: str = Field(..., min_length=1, max_length=100, description="Budget name")
    description: Optional[str] = Field(None, max_length=500, description="Budget description")
    aws_account_id: int = Field(..., description="AWS account ID")
    amount: float = Field(..., gt=0, description="Budget amount in USD")
    period: BudgetPeriod = Field(default=BudgetPeriod.MONTHLY, description="Budget period")
    start_date: datetime = Field(..., description="Budget start date")
    end_date: Optional[datetime] = Field(None, description="Budget end date (null for ongoing)")
    threshold_warning: float = Field(default=80.0, ge=0, le=100, description="Warning threshold percentage")
    threshold_critical: float = Field(default=100.0, ge=0, le=200, description="Critical threshold percentage")
    is_active: bool = Field(default=True, description="Whether budget is active")


class BudgetUpdate(BaseModel):
    """Schema for updating a budget."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    amount: Optional[float] = Field(None, gt=0)
    period: Optional[BudgetPeriod] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    threshold_warning: Optional[float] = Field(None, ge=0, le=100)
    threshold_critical: Optional[float] = Field(None, ge=0, le=200)
    is_active: Optional[bool] = None


class BudgetResponse(BaseModel):
    """Schema for budget response."""
    id: int
    name: str
    description: Optional[str]
    aws_account_id: int
    amount: float
    period: BudgetPeriod
    start_date: datetime
    end_date: Optional[datetime]
    threshold_warning: float
    threshold_critical: float
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class BudgetStatus(BaseModel):
    """Schema for budget status with current spending."""
    budget_id: int
    budget_name: str
    budget_amount: float
    period: BudgetPeriod
    start_date: datetime
    end_date: Optional[datetime]

    # Current spending
    current_spend: float
    percentage_used: float
    remaining: float
    days_remaining: Optional[int]

    # Alert status
    alert_level: BudgetAlertLevel
    threshold_warning: float
    threshold_critical: float

    # Forecast
    projected_spend: Optional[float] = None
    projected_percentage: Optional[float] = None
    is_projected_to_exceed: bool = False


class BudgetSummary(BaseModel):
    """Schema for budget summary across all budgets."""
    total_budgets: int
    active_budgets: int
    total_budget_amount: float
    total_current_spend: float
    budgets_at_warning: int
    budgets_at_critical: int
    budgets_exceeded: int
