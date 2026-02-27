"""
Analytics API endpoints for cost forecasting and anomaly detection.
"""
import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Query, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from app.services.forecasting_service import CostForecastingService
from app.services.anomaly_detection_service import AnomalyDetectionService
from app.services.forecast_service import forecast_service
from app.database.base import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


# ========== Request/Response Schemas ==========

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


# ========== Endpoints ==========

@router.post("/forecast")
def forecast_costs(request: ForecastRequest):
    """
    Generate cost forecast using specified method.

    Supports multiple forecasting methods:
    - **linear**: Linear regression (good for trends)
    - **moving_average**: Simple moving average (stable, less sensitive to outliers)
    - **exponential_smoothing**: Weighted average favoring recent data
    - **ensemble**: Combines all methods for best accuracy

    Args:
        request: Forecast configuration

    Returns:
        Forecast predictions with confidence intervals

    Example:
        ```
        POST /api/v1/analytics/forecast
        {
            "historical_data": [
                {"date": "2026-01-01", "cost": 100.0},
                {"date": "2026-01-02", "cost": 105.0},
                ...
            ],
            "days_ahead": 30,
            "method": "ensemble"
        }
        ```
    """
    try:
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
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown forecast method: {request.method}"
            )

        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating forecast: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating forecast: {str(e)}"
        )


@router.post("/anomalies")
def detect_anomalies(request: AnomalyDetectionRequest):
    """
    Detect cost anomalies using statistical methods.

    Supports multiple detection methods:
    - **z_score**: Standard deviation-based (sensitive to all outliers)
    - **iqr**: Interquartile range-based (robust to extreme outliers)
    - **spike**: Sudden day-over-day increases
    - **drift**: Gradual cost creep over time
    - **all**: Run all methods and return comprehensive summary

    Args:
        request: Anomaly detection configuration

    Returns:
        Detected anomalies with severity ratings

    Example:
        ```
        POST /api/v1/analytics/anomalies
        {
            "historical_data": [
                {"date": "2026-01-01", "cost": 100.0},
                {"date": "2026-01-02", "cost": 105.0},
                ...
            ],
            "method": "all",
            "threshold": 3.0
        }
        ```
    """
    try:
        historical_data = [{"date": d.date, "cost": d.cost} for d in request.historical_data]

        if request.method == "z_score":
            anomalies = AnomalyDetectionService.detect_z_score_anomalies(
                historical_data, request.threshold
            )
            return {"anomalies": anomalies, "method": "z_score"}

        elif request.method == "iqr":
            anomalies = AnomalyDetectionService.detect_iqr_anomalies(
                historical_data, request.threshold
            )
            return {"anomalies": anomalies, "method": "iqr"}

        elif request.method == "spike":
            anomalies = AnomalyDetectionService.detect_sudden_spikes(
                historical_data, request.threshold
            )
            return {"anomalies": anomalies, "method": "spike"}

        elif request.method == "drift":
            anomalies = AnomalyDetectionService.detect_cost_drift(historical_data)
            return {"anomalies": anomalies, "method": "drift"}

        elif request.method == "all":
            summary = AnomalyDetectionService.get_anomaly_summary(historical_data)
            return summary

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown detection method: {request.method}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error detecting anomalies: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error detecting anomalies: {str(e)}"
        )


@router.post("/seasonality")
def detect_seasonality(data: List[CostDataPoint]):
    """
    Detect weekly/monthly cost seasonality patterns.

    Identifies if costs follow regular weekly or monthly patterns,
    which can improve forecasting accuracy.

    Args:
        data: Historical cost data

    Returns:
        Seasonality analysis with patterns

    Example:
        ```
        POST /api/v1/analytics/seasonality
        [
            {"date": "2026-01-01", "cost": 100.0},
            {"date": "2026-01-02", "cost": 105.0},
            ...
        ]
        ```
    """
    try:
        historical_data = [{"date": d.date, "cost": d.cost} for d in data]
        result = CostForecastingService.detect_seasonality(historical_data)
        return result

    except Exception as e:
        logger.error(f"Error detecting seasonality: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error detecting seasonality: {str(e)}"
        )


@router.post("/anomalies/{anomaly_id}/recommendations")
def get_anomaly_recommendations(
    anomaly_id: str,
    anomaly_type: str = Query(..., description="Anomaly type (spike, drift, etc.)"),
    severity: str = Query(..., description="Severity (critical, high, medium, low)")
):
    """
    Get recommended actions for a detected anomaly.

    Args:
        anomaly_id: Anomaly identifier
        anomaly_type: Type of anomaly
        severity: Severity level

    Returns:
        List of recommended actions
    """
    try:
        anomaly = {
            "id": anomaly_id,
            "type": anomaly_type,
            "severity": severity
        }

        recommendations = AnomalyDetectionService.recommend_actions(anomaly)

        return {
            "anomaly_id": anomaly_id,
            "recommendations": recommendations
        }

    except Exception as e:
        logger.error(f"Error getting recommendations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting recommendations: {str(e)}"
        )


# ========== AWS Cost Explorer Integration Endpoints ==========

@router.get("/aws/forecast")
async def get_aws_cost_forecast(
    account_name: str = Query(..., description="AWS account name"),
    days: int = Query(default=30, ge=1, le=90, description="Days to forecast"),
    use_fallback: bool = Query(default=False, description="Force use of statistical forecast"),
    db: DBSession = Depends(get_db)
):
    """
    Get cost forecast from AWS Cost Explorer API or statistical fallback.

    Uses AWS Cost Forecast API when available, falls back to linear regression
    when AWS forecast is unavailable.

    Args:
        account_name: AWS account name
        days: Number of days to forecast (1-90)
        use_fallback: Force statistical forecast instead of AWS API
        db: Database session

    Returns:
        Forecast data with confidence intervals
    """
    try:
        result = await forecast_service.get_cost_forecast(
            db, account_name, days, use_fallback
        )

        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result["error"]
            )

        # Transform data to match frontend expectations
        predictions = []
        forecast_dates = result.get("forecast_dates", [])
        forecast_values = result.get("forecast_values", [])
        confidence_lower = result.get("confidence_lower", [])
        confidence_upper = result.get("confidence_upper", [])

        for i in range(len(forecast_dates)):
            predictions.append({
                "date": forecast_dates[i],
                "predicted_cost": forecast_values[i],
                "lower_bound": confidence_lower[i] if i < len(confidence_lower) else forecast_values[i],
                "upper_bound": confidence_upper[i] if i < len(confidence_upper) else forecast_values[i]
            })

        # Map method name
        method = result.get("method", "statistical")
        forecast_method = "aws_api" if method == "aws_api" else "statistical"

        return {
            "account_name": account_name,
            "forecast_method": forecast_method,
            "forecast_period_days": result.get("days", days),
            "predictions": predictions,
            "total_forecasted_cost": result.get("total_forecast", 0),
            "confidence_level": "95%",
            "generated_at": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting AWS forecast: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating forecast: {str(e)}"
        )


@router.get("/aws/comparison/mom")
async def get_month_over_month_comparison(
    account_name: str = Query(..., description="AWS account name"),
    db: DBSession = Depends(get_db)
):
    """
    Get month-over-month cost comparison.
    
    Compares current month costs to previous month with percentage change.
    
    Args:
        account_name: AWS account name
        db: Database session
    
    Returns:
        MoM comparison data with trend
    """
    try:
        result = await forecast_service.calculate_mom_change(db, account_name)
        
        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result["error"]
            )
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating MoM: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating month-over-month comparison: {str(e)}"
        )


@router.get("/aws/comparison/yoy")
async def get_year_over_year_comparison(
    account_name: str = Query(..., description="AWS account name"),
    db: DBSession = Depends(get_db)
):
    """
    Get year-over-year cost comparison.
    
    Compares current month costs to same month last year with percentage change.
    
    Args:
        account_name: AWS account name
        db: Database session
    
    Returns:
        YoY comparison data with trend
    """
    try:
        result = await forecast_service.calculate_yoy_change(db, account_name)
        
        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result["error"]
            )
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating YoY: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating year-over-year comparison: {str(e)}"
        )
