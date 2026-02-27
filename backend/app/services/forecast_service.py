"""
Cost forecasting service using AWS Cost Explorer API and statistical methods.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import boto3
from botocore.exceptions import ClientError
import numpy as np
from sklearn.linear_model import LinearRegression

from app.aws.session_manager_db import db_session_manager
from app.core.cache import cache_manager

logger = logging.getLogger(__name__)


class ForecastService:
    """Service for cost forecasting and trend analysis."""

    def __init__(self):
        """Initialize forecast service."""
        self.cache_ttl = 3600  # 1 hour cache for forecasts

    async def get_cost_forecast(
        self,
        db,
        account_name: str,
        days: int = 30,
        use_fallback: bool = False
    ) -> Dict:
        """
        Get cost forecast for the next N days.

        Args:
            db: Database session
            account_name: AWS account name
            days: Number of days to forecast (default 30)
            use_fallback: Force use of linear regression fallback

        Returns:
            Dictionary with forecast data
        """
        cache_key = f"forecast:{account_name}:{days}"

        # Check cache
        cached = cache_manager.get(cache_key)
        if cached:
            logger.info(f"Returning cached forecast for {account_name}")
            return cached

        try:
            # Try AWS Cost Explorer forecast API first
            if not use_fallback:
                logger.info(f"Attempting AWS Cost Explorer forecast for {account_name}")
                forecast_data = await self._get_aws_forecast(db, account_name, days)

                if forecast_data:
                    cache_manager.set(cache_key, forecast_data, self.cache_ttl)
                    return forecast_data

            # Fallback to statistical forecast
            logger.info(f"Using statistical forecast for {account_name}")
            forecast_data = await self._get_statistical_forecast(db, account_name, days)

            cache_manager.set(cache_key, forecast_data, self.cache_ttl)
            return forecast_data

        except Exception as e:
            logger.error(f"Error generating forecast for {account_name}: {e}")
            # Return empty forecast on error
            return {
                "forecast_dates": [],
                "forecast_values": [],
                "confidence_lower": [],
                "confidence_upper": [],
                "method": "error",
                "error": str(e)
            }

    async def _get_aws_forecast(
        self,
        db,
        account_name: str,
        days: int
    ) -> Optional[Dict]:
        """
        Get forecast from AWS Cost Explorer API.

        Args:
            db: Database session
            account_name: AWS account name
            days: Number of days to forecast

        Returns:
            Forecast data or None if unavailable
        """
        try:
            # Get AWS session
            aws_session = db_session_manager.get_session(db, account_name)
            ce_client = aws_session.client('ce', region_name='us-east-1')

            # Calculate time range
            start_date = datetime.now().date()
            end_date = start_date + timedelta(days=days)

            # Get forecast from AWS
            response = ce_client.get_cost_forecast(
                TimePeriod={
                    'Start': start_date.strftime('%Y-%m-%d'),
                    'End': end_date.strftime('%Y-%m-%d')
                },
                Metric='UNBLENDED_COST',
                Granularity='DAILY',
                PredictionIntervalLevel=95
            )

            # Parse response
            forecast_dates = []
            forecast_values = []
            confidence_lower = []
            confidence_upper = []

            for result in response.get('ForecastResultsByTime', []):
                date = result['TimePeriod']['Start']
                mean_value = float(result['MeanValue'])
                prediction_interval = result.get('PredictionIntervalLowerBound', mean_value)
                prediction_interval_upper = result.get('PredictionIntervalUpperBound', mean_value)

                forecast_dates.append(date)
                forecast_values.append(mean_value)
                confidence_lower.append(float(prediction_interval))
                confidence_upper.append(float(prediction_interval_upper))

            total_forecast = sum(forecast_values)

            return {
                "forecast_dates": forecast_dates,
                "forecast_values": forecast_values,
                "confidence_lower": confidence_lower,
                "confidence_upper": confidence_upper,
                "total_forecast": total_forecast,
                "method": "aws_api",
                "days": days
            }

        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'DataUnavailableException':
                logger.warning(f"AWS forecast unavailable for {account_name}, using fallback")
                return None
            logger.error(f"AWS API error getting forecast: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting AWS forecast: {e}")
            return None

    async def _get_statistical_forecast(
        self,
        db,
        account_name: str,
        days: int
    ) -> Dict:
        """
        Get forecast using linear regression on historical data.

        Args:
            db: Database session
            account_name: AWS account name
            days: Number of days to forecast

        Returns:
            Forecast data
        """
        try:
            # Get historical cost data (last 90 days)
            historical_data = await self._get_historical_costs(db, account_name, lookback_days=90)

            if not historical_data or len(historical_data) < 7:
                # Not enough data for forecast
                return self._generate_empty_forecast(days)

            # Prepare data for linear regression
            dates = [item['date'] for item in historical_data]
            costs = [item['cost'] for item in historical_data]

            # Convert dates to numeric values (days since first date)
            first_date = datetime.strptime(dates[0], '%Y-%m-%d')
            X = np.array([(datetime.strptime(d, '%Y-%m-%d') - first_date).days
                         for d in dates]).reshape(-1, 1)
            y = np.array(costs)

            # Train linear regression model
            model = LinearRegression()
            model.fit(X, y)

            # Generate forecast
            last_date = datetime.strptime(dates[-1], '%Y-%m-%d')
            forecast_dates = []
            forecast_X = []

            for i in range(1, days + 1):
                forecast_date = last_date + timedelta(days=i)
                forecast_dates.append(forecast_date.strftime('%Y-%m-%d'))
                days_since_first = (forecast_date - first_date).days
                forecast_X.append([days_since_first])

            forecast_X = np.array(forecast_X)
            forecast_values = model.predict(forecast_X).tolist()

            # Calculate confidence intervals (simple approach using historical std)
            residuals = y - model.predict(X)
            std_error = np.std(residuals)

            # 95% confidence interval (~2 std deviations)
            confidence_lower = [max(0, val - 2 * std_error) for val in forecast_values]
            confidence_upper = [val + 2 * std_error for val in forecast_values]

            total_forecast = sum(forecast_values)

            return {
                "forecast_dates": forecast_dates,
                "forecast_values": forecast_values,
                "confidence_lower": confidence_lower,
                "confidence_upper": confidence_upper,
                "total_forecast": total_forecast,
                "method": "linear_regression",
                "days": days,
                "r_squared": float(model.score(X, y))
            }

        except Exception as e:
            logger.error(f"Error in statistical forecast: {e}")
            return self._generate_empty_forecast(days)

    async def _get_historical_costs(
        self,
        db,
        account_name: str,
        lookback_days: int = 90
    ) -> List[Dict]:
        """
        Get historical daily costs for forecasting.

        Args:
            db: Database session
            account_name: AWS account name
            lookback_days: Number of days to look back

        Returns:
            List of {date, cost} dictionaries
        """
        try:
            # Get AWS session
            aws_session = db_session_manager.get_session(db, account_name)
            ce_client = aws_session.client('ce', region_name='us-east-1')

            # Calculate time range
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=lookback_days)

            # Get historical costs
            response = ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date.strftime('%Y-%m-%d'),
                    'End': end_date.strftime('%Y-%m-%d')
                },
                Granularity='DAILY',
                Metrics=['UnblendedCost']
            )

            # Parse results
            historical_data = []
            for result in response['ResultsByTime']:
                date = result['TimePeriod']['Start']
                cost = float(result['Total']['UnblendedCost']['Amount'])
                historical_data.append({'date': date, 'cost': cost})

            return historical_data

        except Exception as e:
            logger.error(f"Error getting historical costs: {e}")
            return []

    def _generate_empty_forecast(self, days: int) -> Dict:
        """Generate empty forecast structure."""
        today = datetime.now().date()
        forecast_dates = [(today + timedelta(days=i)).strftime('%Y-%m-%d')
                         for i in range(1, days + 1)]

        return {
            "forecast_dates": forecast_dates,
            "forecast_values": [0.0] * days,
            "confidence_lower": [0.0] * days,
            "confidence_upper": [0.0] * days,
            "total_forecast": 0.0,
            "method": "insufficient_data",
            "days": days
        }

    async def calculate_mom_change(self, db, account_name: str) -> Dict:
        """
        Calculate month-over-month cost change.

        Args:
            db: Database session
            account_name: AWS account name

        Returns:
            MoM comparison data
        """
        cache_key = f"mom:{account_name}"
        cached = cache_manager.get(cache_key)
        if cached:
            return cached

        try:
            # Get current month and previous month costs
            current_month_start, current_month_end = self._get_month_range(offset=0)
            prev_month_start, prev_month_end = self._get_month_range(offset=-1)

            current_cost = await self._get_period_cost(
                db, account_name, current_month_start, current_month_end
            )
            prev_cost = await self._get_period_cost(
                db, account_name, prev_month_start, prev_month_end
            )

            # Calculate change
            if prev_cost > 0:
                change_percent = ((current_cost - prev_cost) / prev_cost) * 100
            else:
                change_percent = 0.0 if current_cost == 0 else 100.0

            change_amount = current_cost - prev_cost

            result = {
                "current_month": {
                    "start": current_month_start.strftime('%Y-%m-%d'),
                    "end": current_month_end.strftime('%Y-%m-%d'),
                    "cost": current_cost
                },
                "previous_month": {
                    "start": prev_month_start.strftime('%Y-%m-%d'),
                    "end": prev_month_end.strftime('%Y-%m-%d'),
                    "cost": prev_cost
                },
                "change_percent": change_percent,
                "change_amount": change_amount,
                "trend": "increasing" if change_amount > 0 else "decreasing" if change_amount < 0 else "stable"
            }

            cache_manager.set(cache_key, result, 3600)  # Cache for 1 hour
            return result

        except Exception as e:
            logger.error(f"Error calculating MoM change: {e}")
            return {"error": str(e)}

    async def calculate_yoy_change(self, db, account_name: str) -> Dict:
        """
        Calculate year-over-year cost change.

        Args:
            db: Database session
            account_name: AWS account name

        Returns:
            YoY comparison data
        """
        cache_key = f"yoy:{account_name}"
        cached = cache_manager.get(cache_key)
        if cached:
            return cached

        try:
            # Get current month and same month last year
            current_month_start, current_month_end = self._get_month_range(offset=0)
            prev_year_start, prev_year_end = self._get_month_range(offset=-12)

            current_cost = await self._get_period_cost(
                db, account_name, current_month_start, current_month_end
            )
            prev_year_cost = await self._get_period_cost(
                db, account_name, prev_year_start, prev_year_end
            )

            # Calculate change
            if prev_year_cost > 0:
                change_percent = ((current_cost - prev_year_cost) / prev_year_cost) * 100
            else:
                change_percent = 0.0 if current_cost == 0 else 100.0

            change_amount = current_cost - prev_year_cost

            result = {
                "current_period": {
                    "start": current_month_start.strftime('%Y-%m-%d'),
                    "end": current_month_end.strftime('%Y-%m-%d'),
                    "cost": current_cost
                },
                "previous_year_period": {
                    "start": prev_year_start.strftime('%Y-%m-%d'),
                    "end": prev_year_end.strftime('%Y-%m-%d'),
                    "cost": prev_year_cost
                },
                "change_percent": change_percent,
                "change_amount": change_amount,
                "trend": "increasing" if change_amount > 0 else "decreasing" if change_amount < 0 else "stable"
            }

            cache_manager.set(cache_key, result, 3600)  # Cache for 1 hour
            return result

        except Exception as e:
            logger.error(f"Error calculating YoY change: {e}")
            return {"error": str(e)}

    async def _get_period_cost(
        self,
        db,
        account_name: str,
        start_date: datetime,
        end_date: datetime
    ) -> float:
        """Get total cost for a specific period."""
        try:
            aws_session = db_session_manager.get_session(db, account_name)
            ce_client = aws_session.client('ce', region_name='us-east-1')

            response = ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date.strftime('%Y-%m-%d'),
                    'End': end_date.strftime('%Y-%m-%d')
                },
                Granularity='MONTHLY',
                Metrics=['UnblendedCost']
            )

            if response['ResultsByTime']:
                return float(response['ResultsByTime'][0]['Total']['UnblendedCost']['Amount'])
            return 0.0

        except Exception as e:
            logger.error(f"Error getting period cost: {e}")
            return 0.0

    def _get_month_range(self, offset: int = 0) -> Tuple[datetime, datetime]:
        """
        Get start and end dates for a month.

        Args:
            offset: Month offset (0 = current, -1 = previous, -12 = same month last year)

        Returns:
            Tuple of (start_date, end_date)
        """
        today = datetime.now().date()

        # Calculate target month
        target_month = today.month + offset
        target_year = today.year

        while target_month <= 0:
            target_month += 12
            target_year -= 1

        while target_month > 12:
            target_month -= 12
            target_year += 1

        # First day of month
        start_date = datetime(target_year, target_month, 1)

        # Last day of month
        if target_month == 12:
            end_date = datetime(target_year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(target_year, target_month + 1, 1) - timedelta(days=1)

        return start_date, end_date


# Singleton instance
forecast_service = ForecastService()
