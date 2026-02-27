"""
Cost forecasting service with multiple ML models.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


class CostForecastingService:
    """Service for forecasting future AWS costs using multiple models."""

    @staticmethod
    def forecast_linear(
        historical_data: List[Dict[str, Any]],
        days_ahead: int = 30
    ) -> Dict[str, Any]:
        """
        Linear regression forecast.

        Args:
            historical_data: List of {"date": "YYYY-MM-DD", "cost": float}
            days_ahead: Number of days to forecast

        Returns:
            Forecast data with predictions and confidence intervals
        """
        if len(historical_data) < 7:
            return {
                "error": "Need at least 7 days of historical data",
                "predictions": []
            }

        # Convert to pandas
        df = pd.DataFrame(historical_data)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

        # Create numeric x values (days since start)
        df['days'] = (df['date'] - df['date'].min()).dt.days

        # Linear regression
        x = df['days'].values
        y = df['cost'].values

        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

        # Generate predictions
        last_date = df['date'].max()
        predictions = []

        for i in range(1, days_ahead + 1):
            pred_date = last_date + timedelta(days=i)
            pred_days = df['days'].max() + i
            pred_cost = slope * pred_days + intercept

            # Confidence interval (95%)
            # Using standard error of the regression
            se = std_err * np.sqrt(1 + 1/len(x) + (pred_days - x.mean())**2 / ((x - x.mean())**2).sum())
            ci_95 = 1.96 * se

            predictions.append({
                "date": pred_date.strftime("%Y-%m-%d"),
                "predicted_cost": max(0, pred_cost),  # Don't predict negative costs
                "lower_bound": max(0, pred_cost - ci_95),
                "upper_bound": pred_cost + ci_95,
                "confidence": "95%"
            })

        return {
            "method": "linear_regression",
            "r_squared": r_value ** 2,
            "trend": "increasing" if slope > 0 else "decreasing",
            "daily_change": slope,
            "predictions": predictions,
            "accuracy_metrics": {
                "r_squared": r_value ** 2,
                "p_value": p_value,
                "std_error": std_err
            }
        }

    @staticmethod
    def forecast_moving_average(
        historical_data: List[Dict[str, Any]],
        days_ahead: int = 30,
        window: int = 7
    ) -> Dict[str, Any]:
        """
        Simple moving average forecast.

        Args:
            historical_data: List of {"date": "YYYY-MM-DD", "cost": float}
            days_ahead: Number of days to forecast
            window: Moving average window size

        Returns:
            Forecast data with predictions
        """
        if len(historical_data) < window:
            return {
                "error": f"Need at least {window} days of historical data",
                "predictions": []
            }

        # Convert to pandas
        df = pd.DataFrame(historical_data)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

        # Calculate moving average
        recent_avg = df['cost'].tail(window).mean()
        recent_std = df['cost'].tail(window).std()

        # Generate predictions
        last_date = df['date'].max()
        predictions = []

        for i in range(1, days_ahead + 1):
            pred_date = last_date + timedelta(days=i)

            predictions.append({
                "date": pred_date.strftime("%Y-%m-%d"),
                "predicted_cost": recent_avg,
                "lower_bound": max(0, recent_avg - 1.96 * recent_std),
                "upper_bound": recent_avg + 1.96 * recent_std,
                "confidence": "95%"
            })

        return {
            "method": "moving_average",
            "window_size": window,
            "average_daily_cost": recent_avg,
            "r_squared": None,  # Not applicable for moving average
            "trend": "stable",  # Moving average assumes stable costs
            "daily_change": 0,
            "predictions": predictions,
            "accuracy_metrics": {
                "r_squared": None
            }
        }

    @staticmethod
    def forecast_exponential_smoothing(
        historical_data: List[Dict[str, Any]],
        days_ahead: int = 30,
        alpha: float = 0.3
    ) -> Dict[str, Any]:
        """
        Exponential smoothing forecast.

        Args:
            historical_data: List of {"date": "YYYY-MM-DD", "cost": float}
            days_ahead: Number of days to forecast
            alpha: Smoothing factor (0-1, higher = more weight on recent data)

        Returns:
            Forecast data with predictions
        """
        if len(historical_data) < 3:
            return {
                "error": "Need at least 3 days of historical data",
                "predictions": []
            }

        # Convert to pandas
        df = pd.DataFrame(historical_data)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

        # Calculate exponential smoothing
        smoothed = df['cost'].ewm(alpha=alpha, adjust=False).mean()
        last_smoothed = smoothed.iloc[-1]

        # Calculate trend (simple difference)
        if len(df) >= 2:
            trend = smoothed.iloc[-1] - smoothed.iloc[-2]
        else:
            trend = 0

        # Generate predictions
        last_date = df['date'].max()
        predictions = []

        for i in range(1, days_ahead + 1):
            pred_date = last_date + timedelta(days=i)
            pred_cost = last_smoothed + (trend * i)

            # Estimate uncertainty based on recent volatility
            recent_std = df['cost'].tail(7).std()

            predictions.append({
                "date": pred_date.strftime("%Y-%m-%d"),
                "predicted_cost": max(0, pred_cost),
                "lower_bound": max(0, pred_cost - 1.96 * recent_std),
                "upper_bound": pred_cost + 1.96 * recent_std,
                "confidence": "95%"
            })

        return {
            "method": "exponential_smoothing",
            "alpha": alpha,
            "detected_trend": trend,
            "r_squared": None,  # Not applicable for exponential smoothing
            "trend": "increasing" if trend > 0 else "decreasing" if trend < 0 else "stable",
            "daily_change": trend,
            "predictions": predictions,
            "accuracy_metrics": {
                "r_squared": None
            }
        }

    @staticmethod
    def forecast_ensemble(
        historical_data: List[Dict[str, Any]],
        days_ahead: int = 30
    ) -> Dict[str, Any]:
        """
        Ensemble forecast combining multiple models.

        Args:
            historical_data: List of {"date": "YYYY-MM-DD", "cost": float}
            days_ahead: Number of days to forecast

        Returns:
            Combined forecast from multiple models
        """
        # Get forecasts from all models
        linear_forecast = CostForecastingService.forecast_linear(historical_data, days_ahead)
        ma_forecast = CostForecastingService.forecast_moving_average(historical_data, days_ahead)
        es_forecast = CostForecastingService.forecast_exponential_smoothing(historical_data, days_ahead)

        # Check for errors
        if "error" in linear_forecast or "error" in ma_forecast or "error" in es_forecast:
            return {"error": "Insufficient data for ensemble forecast", "predictions": []}

        # Combine predictions (simple average)
        predictions = []
        for i in range(days_ahead):
            linear_pred = linear_forecast["predictions"][i]
            ma_pred = ma_forecast["predictions"][i]
            es_pred = es_forecast["predictions"][i]

            avg_cost = (
                linear_pred["predicted_cost"] +
                ma_pred["predicted_cost"] +
                es_pred["predicted_cost"]
            ) / 3

            # Use widest confidence interval
            lower = min(
                linear_pred["lower_bound"],
                ma_pred["lower_bound"],
                es_pred["lower_bound"]
            )
            upper = max(
                linear_pred["upper_bound"],
                ma_pred["upper_bound"],
                es_pred["upper_bound"]
            )

            predictions.append({
                "date": linear_pred["date"],
                "predicted_cost": avg_cost,
                "lower_bound": lower,
                "upper_bound": upper,
                "confidence": "95%",
                "individual_predictions": {
                    "linear": linear_pred["predicted_cost"],
                    "moving_average": ma_pred["predicted_cost"],
                    "exponential_smoothing": es_pred["predicted_cost"]
                }
            })

        # Get trend and daily change from linear model
        r_squared = linear_forecast.get("r_squared", 0)
        trend = linear_forecast.get("trend", "stable")
        daily_change = linear_forecast.get("daily_change", 0)

        return {
            "method": "ensemble",
            "models_used": ["linear_regression", "moving_average", "exponential_smoothing"],
            "r_squared": r_squared,  # Include at top level for consistency
            "trend": trend,
            "daily_change": daily_change,
            "predictions": predictions,
            "accuracy_metrics": {
                "r_squared": r_squared
            },
            "model_performance": {
                "linear_r_squared": r_squared
            }
        }

    @staticmethod
    def calculate_forecast_accuracy(
        actual_data: List[Dict[str, Any]],
        predicted_data: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Calculate forecast accuracy metrics.

        Args:
            actual_data: Actual costs {"date": "YYYY-MM-DD", "cost": float}
            predicted_data: Predicted costs {"date": "YYYY-MM-DD", "predicted_cost": float}

        Returns:
            Accuracy metrics (MAE, MAPE, RMSE)
        """
        # Align dates
        actual_df = pd.DataFrame(actual_data)
        pred_df = pd.DataFrame(predicted_data)

        actual_df['date'] = pd.to_datetime(actual_df['date'])
        pred_df['date'] = pd.to_datetime(pred_df['date'])

        merged = pd.merge(actual_df, pred_df, on='date', how='inner')

        if len(merged) == 0:
            return {"error": "No overlapping dates"}

        actual = merged['cost'].values
        predicted = merged['predicted_cost'].values

        # Mean Absolute Error
        mae = np.mean(np.abs(actual - predicted))

        # Mean Absolute Percentage Error
        mape = np.mean(np.abs((actual - predicted) / actual)) * 100

        # Root Mean Square Error
        rmse = np.sqrt(np.mean((actual - predicted) ** 2))

        # R-squared
        ss_res = np.sum((actual - predicted) ** 2)
        ss_tot = np.sum((actual - np.mean(actual)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

        return {
            "mae": mae,
            "mape": mape,
            "rmse": rmse,
            "r_squared": r_squared,
            "samples": len(merged)
        }

    @staticmethod
    def detect_seasonality(
        historical_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Detect weekly/monthly seasonality patterns.

        Args:
            historical_data: List of {"date": "YYYY-MM-DD", "cost": float}

        Returns:
            Seasonality analysis
        """
        df = pd.DataFrame(historical_data)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

        # Add day of week and day of month
        df['day_of_week'] = df['date'].dt.dayofweek
        df['day_of_month'] = df['date'].dt.day

        # Weekly seasonality
        weekly_avg = df.groupby('day_of_week')['cost'].mean().to_dict()
        weekly_pattern = {
            ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][k]: v
            for k, v in weekly_avg.items()
        }

        # Monthly seasonality (if enough data)
        monthly_avg = df.groupby('day_of_month')['cost'].mean().to_dict()

        # Calculate coefficient of variation for weekly pattern
        weekly_values = list(weekly_avg.values())
        weekly_cv = (np.std(weekly_values) / np.mean(weekly_values)) * 100 if np.mean(weekly_values) > 0 else 0

        has_weekly_seasonality = weekly_cv > 10  # >10% variation suggests seasonality

        return {
            "has_weekly_seasonality": has_weekly_seasonality,
            "weekly_coefficient_of_variation": weekly_cv,
            "weekly_pattern": weekly_pattern,
            "highest_cost_day": max(weekly_pattern, key=weekly_pattern.get),
            "lowest_cost_day": min(weekly_pattern, key=weekly_pattern.get),
            "monthly_pattern": monthly_avg
        }
