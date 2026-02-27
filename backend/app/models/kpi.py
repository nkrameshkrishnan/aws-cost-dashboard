"""
KPI (Key Performance Indicators) models for AWS Cost Management.
"""
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class KPICategory(str, Enum):
    """KPI categories for AWS cost management."""
    COST_EFFICIENCY = "cost_efficiency"
    BUDGET_PERFORMANCE = "budget_performance"
    SAVINGS_RATE = "savings_rate"
    COST_TREND = "cost_trend"
    RESOURCE_OPTIMIZATION = "resource_optimization"
    SPEND_VELOCITY = "spend_velocity"


class KPIStatus(str, Enum):
    """Status levels for KPI metrics."""
    EXCELLENT = "excellent"  # Green - performing very well
    GOOD = "good"            # Blue - performing well
    WARNING = "warning"      # Yellow - needs attention
    POOR = "poor"            # Red - critical attention needed
    UNKNOWN = "unknown"      # Gray - insufficient data


class KPIThreshold(BaseModel):
    """Threshold values for determining KPI status."""
    excellent: float = Field(..., description="Threshold for excellent status")
    good: float = Field(..., description="Threshold for good status")
    warning: float = Field(..., description="Threshold for warning status")
    poor: float = Field(..., description="Threshold for poor status")


class KPIDefinition(BaseModel):
    """Definition of a KPI metric."""
    id: str = Field(..., description="Unique KPI identifier")
    category: KPICategory = Field(..., description="KPI category")
    name: str = Field(..., description="Display name of the KPI")
    description: str = Field(..., description="Detailed description")
    unit: str = Field(..., description="Unit of measurement (e.g., $, %, days)")
    thresholds: KPIThreshold = Field(..., description="Status thresholds")
    format: str = Field(..., description="Format type: number, percentage, currency, duration")
    higher_is_better: bool = Field(..., description="Whether higher values indicate better performance")


class KPIValue(BaseModel):
    """Actual value of a KPI metric."""
    category: KPICategory = Field(..., description="KPI category")
    value: float = Field(..., description="Current value")
    status: KPIStatus = Field(..., description="Calculated status based on thresholds")
    trend: str = Field(..., description="Trend direction: up, down, stable")
    previous_value: Optional[float] = Field(None, description="Previous period value for comparison")
    profile_name: Optional[str] = Field(None, description="AWS profile/account name")
    calculated_at: datetime = Field(default_factory=datetime.utcnow, description="Calculation timestamp")
    target_value: Optional[float] = Field(None, description="Optional target value")


class KPITrend(BaseModel):
    """Historical trend data point for a KPI."""
    date: str = Field(..., description="Date of the data point")
    value: float = Field(..., description="Value at this date")
    status: KPIStatus = Field(..., description="Status at this date")


class KPIMetrics(BaseModel):
    """Complete KPI metrics with definition, current value, and history."""
    kpi: KPIDefinition = Field(..., description="KPI definition")
    current: KPIValue = Field(..., description="Current value")
    history: List[KPITrend] = Field(default_factory=list, description="Historical trend data")
    target_value: Optional[float] = Field(None, description="Target value to achieve")


# AWS Cost KPI Definitions
AWS_COST_KPI_DEFINITIONS = {
    "cost_efficiency": KPIDefinition(
        id="cost_efficiency",
        category=KPICategory.COST_EFFICIENCY,
        name="Cost Efficiency Score",
        description="Ratio of optimized costs to total costs (based on audit findings)",
        unit="%",
        thresholds=KPIThreshold(
            excellent=90.0,  # >90% efficiency
            good=75.0,       # 75-90%
            warning=60.0,    # 60-75%
            poor=0.0         # <60%
        ),
        format="percentage",
        higher_is_better=True
    ),
    "budget_utilization": KPIDefinition(
        id="budget_utilization",
        category=KPICategory.BUDGET_PERFORMANCE,
        name="Budget Utilization",
        description="Projected end-of-month spending as a percentage of budget (forecasted vs budgeted)",
        unit="%",
        thresholds=KPIThreshold(
            excellent=85.0,  # 85-100% (on track)
            good=100.0,      # 100-110% (slight over)
            warning=120.0,   # 110-120% (over budget)
            poor=200.0       # >120% (critical)
        ),
        format="percentage",
        higher_is_better=False  # Lower utilization (on budget) is better
    ),
    "savings_potential": KPIDefinition(
        id="savings_potential",
        category=KPICategory.SAVINGS_RATE,
        name="Monthly Savings Potential",
        description="Total potential monthly savings from audit recommendations",
        unit="$",
        thresholds=KPIThreshold(
            excellent=0.0,    # <$100 (very optimized)
            good=500.0,       # $100-500
            warning=2000.0,   # $500-2000
            poor=10000.0      # >$2000 (needs attention)
        ),
        format="currency",
        higher_is_better=False  # Lower savings potential means already optimized
    ),
    "cost_growth_rate": KPIDefinition(
        id="cost_growth_rate",
        category=KPICategory.COST_TREND,
        name="Month-over-Month Cost Growth",
        description="Percentage change in costs compared to previous month",
        unit="%",
        thresholds=KPIThreshold(
            excellent=-5.0,   # Cost reduction
            good=5.0,         # -5% to +5% (stable)
            warning=15.0,     # 5-15% increase
            poor=100.0        # >15% increase
        ),
        format="percentage",
        higher_is_better=False  # Lower growth is better
    ),
    "resource_waste_ratio": KPIDefinition(
        id="resource_waste_ratio",
        category=KPICategory.RESOURCE_OPTIMIZATION,
        name="Resource Waste Ratio",
        description="Percentage of wasteful spending (idle resources, unattached volumes, etc.)",
        unit="%",
        thresholds=KPIThreshold(
            excellent=5.0,    # <5% waste
            good=10.0,        # 5-10%
            warning=20.0,     # 10-20%
            poor=100.0        # >20%
        ),
        format="percentage",
        higher_is_better=False  # Lower waste is better
    ),
    "daily_spend_rate": KPIDefinition(
        id="daily_spend_rate",
        category=KPICategory.SPEND_VELOCITY,
        name="Average Daily Spend",
        description="Average cost per day in the current month",
        unit="$/day",
        thresholds=KPIThreshold(
            excellent=0.0,    # Defined per organization
            good=100.0,       # Defined per organization
            warning=500.0,    # Defined per organization
            poor=1000.0       # Defined per organization
        ),
        format="currency",
        higher_is_better=False  # Lower daily spend is generally better
    ),
}
