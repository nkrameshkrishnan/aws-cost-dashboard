"""
Pydantic schemas for Analytics API endpoints.

These models define the request/response structure for:
- Cost forecasting
- Anomaly detection
- Seasonality analysis
"""
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


# Type definitions for enum-like fields
ForecastMethod = Literal["linear", "moving_average", "exponential_smoothing", "ensemble"]
AnomalyMethod = Literal["z_score", "iqr", "spike", "drift", "all"]


class CostDataPoint(BaseModel):
    """Single cost data point for time series analysis."""
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    cost: float = Field(..., description="Cost amount", ge=0)


class ForecastRequest(BaseModel):
    """Request for cost forecast."""
    historical_data: List[CostDataPoint] = Field(
        ...,
        description="Historical cost data for forecasting",
        min_length=2
    )
    days_ahead: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Number of days to forecast"
    )
    method: ForecastMethod = Field(
        default="ensemble",
        description="Forecast method: linear, moving_average, exponential_smoothing, ensemble"
    )


class AnomalyDetectionRequest(BaseModel):
    """Request for anomaly detection."""
    historical_data: List[CostDataPoint] = Field(
        ...,
        description="Historical cost data for anomaly detection",
        min_length=3
    )
    method: AnomalyMethod = Field(
        default="all",
        description="Detection method: z_score, iqr, spike, drift, all"
    )
    threshold: float = Field(
        default=3.0,
        ge=0.1,
        description="Detection sensitivity threshold (higher = less sensitive)"
    )


class ForecastPoint(BaseModel):
    """Single forecast prediction point."""
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    predicted_cost: float = Field(..., description="Predicted cost amount")
    lower_bound: float = Field(..., description="Lower confidence bound")
    upper_bound: float = Field(..., description="Upper confidence bound")


class AnomalyPoint(BaseModel):
    """Detected anomaly data point."""
    date: str = Field(..., description="Date of anomaly")
    cost: float = Field(..., description="Cost amount")
    anomaly_type: str = Field(..., description="Type of anomaly detected")
    severity: str = Field(..., description="Severity: critical, high, medium, low")
    description: str = Field(..., description="Human-readable description")


class ForecastResponse(BaseModel):
    """Response from forecast endpoint."""
    account_name: str
    forecast_method: str
    forecast_period_days: int
    predictions: List[ForecastPoint]
    total_forecasted_cost: float
    confidence_level: str = "95%"
    generated_at: str


class AnomalyResponse(BaseModel):
    """Response from anomaly detection."""
    anomalies: List[AnomalyPoint]
    method: str
    total_anomalies: int
    summary: Optional[dict] = None