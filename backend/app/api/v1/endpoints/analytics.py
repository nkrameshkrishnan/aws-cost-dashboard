"""Analytics API endpoints for cost forecasting and anomaly detection."""

import logging
from typing import List
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.forecasting_service import CostForecastingService
from app.services.anomaly_detection_service import AnomalyDetectionService

# Shared utilities
from ..utils import handle_exceptions

router = APIRouter()
logger = logging.getLogger(__name__)

# ---------- Schemas ----------
class CostDataPoint(BaseModel):
    """Single cost data point."""
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    cost: float = Field(..., description="Cost amount")

class ForecastRequest(BaseModel):
    """Request for cost forecast."""
    historical_data: List[CostDataPoint] = Field(..., description="Historical cost data")
    days_ahead: int = Field(default=30, ge=1, le=365, description="Days to forecast")
    method: str = Field(
        default="ensemble",
        description="Forecast method: linear, moving_average, exponential_smoothing, ensemble"
    )

class AnomalyDetectionRequest(BaseModel):
    """Request for anomaly detection."""
    historical_data: List[CostDataPoint] = Field(..., description="Historical cost data")
    method: str = Field(
        default="all",
        description="Detection method: z_score, iqr, spike, drift, all"
    )
    threshold: float = Field(default=3.0, description="Detection sensitivity threshold")

# ---------- Endpoints ----------
@router.post("/forecast")
async def forecast_costs(request: ForecastRequest):
    """Generate cost forecast using specified method."""
    historical_data = [{"date": d.date, "cost": d.cost} for d in request.historical_data]
    if request.method == "linear":
        result = CostForecastingService.forecast_linear(historical_data, request.days_ahead)
    elif request.method == "moving_average":
        result = CostForecastingService.forecast_moving_average(historical_data, request.days_ahead)
    elif request.method == "exponential_smoothing":
        result = CostForecastingService.forecast_exponential_smoothing(historical_data, request.days_ahead)
    elif request.method == "ensemble":
        result = CostForecastingService.forecast_ensemble(historical_data, request.days_ahead)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown forecast method: {request.method}")

    if "error" in result:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])

    return await handle_exceptions(asyncio.ensure_future(asyncio.sleep(0)))  # dummy to keep async signature

@router.post("/anomalies")
async def detect_anomalies(request: AnomalyDetectionRequest):
    """Detect cost anomalies using statistical methods."""
    historical_data = [{"date": d.date, "cost": d.cost} for d in request.historical_data]
    if request.method == "z_score":
        anomalies = AnomalyDetectionService.detect_z_score_anomalies(historical_data, request.threshold)
        return {"anomalies": anomalies, "method": "z_score"}
    elif request.method == "iqr":
        anomalies = AnomalyDetectionService.detect_iqr_anomalies(historical_data, request.threshold)
        return {"anomalies": anomalies, "method": "iqr"}
    elif request.method == "spike":
        anomalies = AnomalyDetectionService.detect_sudden_spikes(historical_data, request.threshold)
        return {"anomalies": anomalies, "method": "spike"}
    elif request.method == "drift":
        anomalies = AnomalyDetectionService.detect_cost_drift(historical_data)
        return {"anomalies": anomalies, "method": "drift"}
    elif request.method == "all":
        summary = AnomalyDetectionService.get_anomaly_summary(historical_data)
        return summary
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown detection method: {request.method}")

@router.post("/seasonality")
async def detect_seasonality(data: List[CostDataPoint]):
    """Detect weekly/monthly cost seasonality patterns."""
    # Implementation omitted – retain existing logic
    pass
