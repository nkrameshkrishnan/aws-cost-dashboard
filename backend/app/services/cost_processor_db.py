"""
Cost data processor using database-stored AWS credentials.
Enhanced version that works with database-stored accounts.
"""
from datetime import datetime, timedelta
from typing import Dict, List
from sqlalchemy.orm import Session
import logging

from app.aws.session_manager_db import db_session_manager
from app.core.encryption import credential_encryption
from app.models.aws_account import AWSAccount
from app.core.cache import cache_manager
from app.config import settings

logger = logging.getLogger(__name__)


class DatabaseCostProcessor:
    """
    Processes cost data using database-stored AWS credentials.
    """

    @staticmethod
    def get_cost_explorer_client(db: Session, account_name: str):
        """
        Get a Cost Explorer client for a database account.

        Args:
            db: Database session
            account_name: AWS account name from database

        Returns:
            Boto3 Cost Explorer client
        """
        # Cost Explorer is only available in us-east-1
        return db_session_manager.get_client(
            db,
            account_name,
            'ce',
            region_name='us-east-1'
        )

    @staticmethod
    def get_cost_and_usage(
        db: Session,
        account_name: str,
        start_date: str,
        end_date: str,
        granularity: str = "DAILY",
        metrics: List[str] = None
    ) -> Dict:
        """
        Get cost and usage data using database credentials.
        Uses Redis caching to minimize AWS Cost Explorer API calls.

        Args:
            db: Database session
            account_name: AWS account name from database
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            granularity: DAILY or MONTHLY
            metrics: List of metrics (defaults to UnblendedCost)

        Returns:
            Cost and usage data from AWS
        """
        if metrics is None:
            metrics = ["UnblendedCost"]

        # Generate cache key
        cache_key = cache_manager._generate_key(
            "costs:usage",
            account_name,
            start_date,
            end_date,
            granularity,
            tuple(sorted(metrics))
        )

        # Determine TTL based on date range
        today = datetime.now().date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()

        # If end date is in the past (historical data), cache longer
        if end_dt < today:
            ttl = settings.CACHE_TTL_HISTORICAL  # 24 hours
        else:
            ttl = settings.CACHE_TTL_CURRENT_MONTH  # 5 minutes

        # Try to get from cache
        cached_data = cache_manager.get(cache_key)
        if cached_data is not None:
            logger.info(f"Cache hit for cost data: {account_name} ({start_date} to {end_date})")
            return cached_data

        # Cache miss - fetch from AWS
        logger.info(f"Cache miss - fetching from AWS: {account_name} ({start_date} to {end_date})")

        try:
            client = DatabaseCostProcessor.get_cost_explorer_client(db, account_name)

            response = client.get_cost_and_usage(
                TimePeriod={
                    "Start": start_date,
                    "End": end_date
                },
                Granularity=granularity,
                Metrics=metrics
            )

            # Cache the response
            cache_manager.set(cache_key, response, ttl)
            logger.debug(f"Cached cost data with TTL {ttl}s: {cache_key}")

            return response

        except Exception as e:
            logger.error(f"Error fetching cost data for {account_name}: {e}")
            raise

    @staticmethod
    def get_cost_summary(
        db: Session,
        account_name: str,
        start_date: str,
        end_date: str
    ) -> Dict:
        """
        Get cost summary for an account.

        Returns:
            Dictionary with total cost and metadata
        """
        response = DatabaseCostProcessor.get_cost_and_usage(
            db,
            account_name,
            start_date,
            end_date,
            granularity="MONTHLY"
        )

        total_cost = 0.0
        results = response.get('ResultsByTime', [])

        for result in results:
            amount = result.get('Total', {}).get('UnblendedCost', {}).get('Amount', '0')
            total_cost += float(amount)

        return {
            'profile_name': account_name,  # Keep same key for compatibility
            'start_date': start_date,
            'end_date': end_date,
            'total_cost': round(total_cost, 2),
            'currency': results[0].get('Total', {}).get('UnblendedCost', {}).get('Unit', 'USD') if results else 'USD',
            'period_count': len(results)
        }

    @staticmethod
    def get_daily_costs(
        db: Session,
        account_name: str,
        start_date: str,
        end_date: str
    ) -> List[Dict]:
        """
        Get daily cost breakdown.

        Returns:
            List of daily cost records
        """
        response = DatabaseCostProcessor.get_cost_and_usage(
            db,
            account_name,
            start_date,
            end_date,
            granularity="DAILY"
        )

        daily_costs = []
        for result in response.get('ResultsByTime', []):
            date = result['TimePeriod']['Start']
            amount = float(result.get('Total', {}).get('UnblendedCost', {}).get('Amount', '0'))

            daily_costs.append({
                'date': date,
                'cost': round(amount, 2)
            })

        return daily_costs

    @staticmethod
    def get_service_breakdown(
        db: Session,
        account_name: str,
        start_date: str,
        end_date: str,
        top_n: int = 10
    ) -> List[Dict]:
        """
        Get cost breakdown by AWS service.
        Uses Redis caching to minimize AWS Cost Explorer API calls.

        Returns:
            List of service cost records
        """
        # Generate cache key
        cache_key = cache_manager._generate_key(
            "costs:services",
            account_name,
            start_date,
            end_date,
            top_n
        )

        # Try to get from cache
        cached_data = cache_manager.get(cache_key)
        if cached_data is not None:
            logger.info(f"Cache hit for service breakdown: {account_name}")
            return cached_data

        # Cache miss - fetch from AWS
        logger.info(f"Cache miss - fetching service breakdown from AWS: {account_name}")

        try:
            client = DatabaseCostProcessor.get_cost_explorer_client(db, account_name)

            response = client.get_cost_and_usage(
                TimePeriod={
                    "Start": start_date,
                    "End": end_date
                },
                Granularity="MONTHLY",
                Metrics=["UnblendedCost"],
                GroupBy=[{
                    "Type": "DIMENSION",
                    "Key": "SERVICE"
                }]
            )

            # Aggregate costs by service
            service_costs = {}
            for result in response.get('ResultsByTime', []):
                for group in result.get('Groups', []):
                    service = group['Keys'][0] if group.get('Keys') else 'Unknown'
                    amount = float(group.get('Metrics', {}).get('UnblendedCost', {}).get('Amount', '0'))

                    if service in service_costs:
                        service_costs[service] += amount
                    else:
                        service_costs[service] = amount

            # Sort and get top N
            sorted_services = sorted(
                service_costs.items(),
                key=lambda x: x[1],
                reverse=True
            )

            top_services = []
            other_cost = 0.0

            for i, (service, cost) in enumerate(sorted_services):
                if i < top_n:
                    top_services.append({
                        'service': service,
                        'cost': round(cost, 2)
                    })
                else:
                    other_cost += cost

            if other_cost > 0:
                top_services.append({
                    'service': 'Others',
                    'cost': round(other_cost, 2)
                })

            # Cache the result
            cache_manager.set(cache_key, top_services, settings.CACHE_TTL_SERVICE_BREAKDOWN)
            logger.debug(f"Cached service breakdown: {cache_key}")

            return top_services

        except Exception as e:
            logger.error(f"Error fetching service breakdown for {account_name}: {e}")
            raise

    @staticmethod
    def calculate_mom_change(
        db: Session,
        account_name: str,
        current_month_start: str,
        current_month_end: str
    ) -> Dict:
        """
        Calculate month-over-month cost change using database credentials.

        Args:
            db: Database session
            account_name: AWS account name from database
            current_month_start: Current month start date (YYYY-MM-DD)
            current_month_end: Current month end date (YYYY-MM-DD)

        Returns:
            Dictionary with MoM comparison data
        """
        # Calculate previous month dates
        current_start = datetime.strptime(current_month_start, "%Y-%m-%d")
        prev_month_start = current_start - timedelta(days=current_start.day)
        prev_month_start = prev_month_start.replace(day=1)
        prev_month_end = current_start - timedelta(days=1)

        # Get costs for both months
        current_cost = DatabaseCostProcessor.get_cost_summary(
            db,
            account_name,
            current_month_start,
            current_month_end
        )['total_cost']

        previous_cost = DatabaseCostProcessor.get_cost_summary(
            db,
            account_name,
            prev_month_start.strftime("%Y-%m-%d"),
            prev_month_end.strftime("%Y-%m-%d")
        )['total_cost']

        # Calculate change
        if previous_cost > 0:
            change_percent = ((current_cost - previous_cost) / previous_cost) * 100
        else:
            change_percent = 0.0

        change_amount = current_cost - previous_cost

        return {
            'current_month': {
                'start': current_month_start,
                'end': current_month_end,
                'cost': current_cost
            },
            'previous_month': {
                'start': prev_month_start.strftime("%Y-%m-%d"),
                'end': prev_month_end.strftime("%Y-%m-%d"),
                'cost': previous_cost
            },
            'change_amount': round(change_amount, 2),
            'change_percent': round(change_percent, 2)
        }

    @staticmethod
    def calculate_yoy_change(
        db: Session,
        account_name: str,
        current_period_start: str,
        current_period_end: str
    ) -> Dict:
        """
        Calculate year-over-year cost change using database credentials.

        Args:
            db: Database session
            account_name: AWS account name from database
            current_period_start: Current period start date (YYYY-MM-DD)
            current_period_end: Current period end date (YYYY-MM-DD)

        Returns:
            Dictionary with YoY comparison data
        """
        from dateutil.relativedelta import relativedelta

        # Parse dates
        current_start = datetime.strptime(current_period_start, "%Y-%m-%d")
        current_end = datetime.strptime(current_period_end, "%Y-%m-%d")

        # Calculate same period last year
        prev_start = current_start - relativedelta(years=1)
        prev_end = current_end - relativedelta(years=1)

        # Get costs for both periods
        current_cost = DatabaseCostProcessor.get_cost_summary(
            db,
            account_name,
            current_period_start,
            current_period_end
        )['total_cost']

        previous_cost = DatabaseCostProcessor.get_cost_summary(
            db,
            account_name,
            prev_start.strftime("%Y-%m-%d"),
            prev_end.strftime("%Y-%m-%d")
        )['total_cost']

        # Calculate change
        if previous_cost > 0:
            change_percent = ((current_cost - previous_cost) / previous_cost) * 100
        else:
            change_percent = 0.0

        change_amount = current_cost - previous_cost

        return {
            'current_period': {
                'start': current_period_start,
                'end': current_period_end,
                'cost': round(current_cost, 2)
            },
            'previous_year_period': {
                'start': prev_start.strftime("%Y-%m-%d"),
                'end': prev_end.strftime("%Y-%m-%d"),
                'cost': round(previous_cost, 2)
            },
            'change_amount': round(change_amount, 2),
            'change_percent': round(change_percent, 2)
        }

    @staticmethod
    def get_forecast(
        db: Session,
        account_name: str,
        days: int = 30,
        granularity: str = "MONTHLY"
    ) -> Dict:
        """
        Get cost forecast for the next N days using database credentials.
        Uses Redis caching to minimize AWS Cost Explorer API calls.

        Args:
            db: Database session
            account_name: AWS account name from database
            days: Number of days to forecast
            granularity: DAILY or MONTHLY

        Returns:
            Forecast data with optional daily breakdown
        """
        start_date = datetime.now().strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")

        # Generate cache key including granularity
        cache_key = cache_manager._generate_key(
            "costs:forecast",
            account_name,
            start_date,
            days,
            granularity
        )

        # Try to get from cache
        cached_data = cache_manager.get(cache_key)
        if cached_data is not None:
            logger.info(f"Cache hit for forecast: {account_name}")
            return cached_data

        # Cache miss - fetch from AWS
        logger.info(f"Cache miss - fetching forecast from AWS: {account_name}")

        try:
            client = DatabaseCostProcessor.get_cost_explorer_client(db, account_name)

            response = client.get_cost_forecast(
                TimePeriod={
                    "Start": start_date,
                    "End": end_date
                },
                Granularity=granularity,
                Metric="UNBLENDED_COST"
            )

            if granularity == "DAILY":
                # Extract daily forecast values
                forecast_data = []
                for result_item in response.get('ForecastResultsByTime', []):
                    period_start = result_item['TimePeriod']['Start']
                    mean_value = float(result_item.get('MeanValue', '0'))
                    forecast_data.append({
                        'date': period_start,
                        'forecasted_cost': round(mean_value, 2)
                    })

                total_forecast = sum(item['forecasted_cost'] for item in forecast_data)

                result = {
                    'forecast_period_start': start_date,
                    'forecast_period_end': end_date,
                    'forecasted_cost': round(total_forecast, 2),
                    'currency': 'USD',
                    'daily_forecast': forecast_data
                }
            else:
                # Monthly granularity
                total = response.get('Total', {})
                forecast_amount = float(total.get('Amount', '0'))

                result = {
                    'forecast_period_start': start_date,
                    'forecast_period_end': end_date,
                    'forecasted_cost': round(forecast_amount, 2),
                    'currency': total.get('Unit', 'USD')
                }

            # Cache the result
            cache_manager.set(cache_key, result, settings.CACHE_TTL_FORECAST)
            logger.debug(f"Cached forecast data: {cache_key}")

            return result

        except Exception as e:
            logger.warning(f"Forecast not available for {account_name}: {e}")
            error_result = {
                'forecast_period_start': start_date,
                'forecast_period_end': end_date,
                'forecasted_cost': 0.0,
                'currency': 'USD',
                'error': 'Forecast not available'
            }
            # Cache the error result too (with shorter TTL)
            cache_manager.set(cache_key, error_result, 300)  # 5 minutes
            return error_result

    @staticmethod
    def get_cost_trend(
        db: Session,
        account_name: str,
        months: int = 6
    ) -> List[Dict]:
        """
        Get monthly cost trend for the past N months using database credentials.
        Uses Redis caching to minimize AWS Cost Explorer API calls.

        Args:
            db: Database session
            account_name: AWS account name from database
            months: Number of months to include

        Returns:
            List of monthly cost records with MoM changes
        """
        # Generate cache key
        cache_key = cache_manager._generate_key(
            "costs:trend",
            account_name,
            months
        )

        # Try to get from cache
        cached_data = cache_manager.get(cache_key)
        if cached_data is not None:
            logger.info(f"Cache hit for cost trend: {account_name}")
            return cached_data

        # Cache miss - fetch from AWS
        logger.info(f"Cache miss - fetching cost trend from AWS: {account_name}")

        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=months * 30)

            response = DatabaseCostProcessor.get_cost_and_usage(
                db,
                account_name,
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
                granularity="MONTHLY"
            )

            trend_data = []
            previous_cost = None

            for result in response.get('ResultsByTime', []):
                period_start = result['TimePeriod']['Start']
                cost = float(result.get('Total', {}).get('UnblendedCost', {}).get('Amount', '0'))

                # Calculate MoM change
                mom_change = None
                if previous_cost is not None and previous_cost > 0:
                    mom_change = ((cost - previous_cost) / previous_cost) * 100

                trend_data.append({
                    'month': period_start,
                    'cost': round(cost, 2),
                    'mom_change_percent': round(mom_change, 2) if mom_change is not None else None
                })

                previous_cost = cost

            # Cache the result
            cache_manager.set(cache_key, trend_data, settings.CACHE_TTL_HISTORICAL)
            logger.debug(f"Cached cost trend data: {cache_key}")

            return trend_data

        except Exception as e:
            logger.error(f"Error fetching cost trend for {account_name}: {e}")
            raise

    @staticmethod
    def get_cost_drill_down(
        db: Session,
        account_name: str,
        start_date: str,
        end_date: str,
        dimension: str,
        filters: Dict[str, str] = None
    ) -> Dict:
        """
        Get cost breakdown by a specific dimension with optional filters.
        Supports multi-level drill-down (e.g., SERVICE -> REGION -> LINKED_ACCOUNT).

        Args:
            db: Database session
            account_name: AWS account name from database
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            dimension: AWS dimension to group by (SERVICE, REGION, LINKED_ACCOUNT, etc.)
            filters: Optional filters to apply (e.g., {"SERVICE": "Amazon EC2"})

        Returns:
            Dictionary with breakdown by dimension including costs and percentages
        """
        if filters is None:
            filters = {}

        # Generate cache key including filters
        cache_key = cache_manager._generate_key(
            "costs:drilldown",
            account_name,
            start_date,
            end_date,
            dimension,
            tuple(sorted(filters.items()))
        )

        # Try to get from cache
        cached_data = cache_manager.get(cache_key)
        if cached_data is not None:
            logger.info(f"Cache hit for drill-down: {account_name} ({dimension})")
            return cached_data

        # Cache miss - fetch from AWS
        logger.info(f"Cache miss - fetching drill-down from AWS: {account_name} ({dimension})")

        try:
            client = DatabaseCostProcessor.get_cost_explorer_client(db, account_name)

            # Build request parameters
            request_params = {
                "TimePeriod": {
                    "Start": start_date,
                    "End": end_date
                },
                "Granularity": "MONTHLY",
                "Metrics": ["UnblendedCost"],
                "GroupBy": [{
                    "Type": "DIMENSION",
                    "Key": dimension
                }]
            }

            # Add filters if provided
            if filters:
                filter_expressions = []
                for filter_dim, filter_value in filters.items():
                    filter_expressions.append({
                        "Dimensions": {
                            "Key": filter_dim,
                            "Values": [filter_value]
                        }
                    })

                # Combine filters with AND logic if multiple
                if len(filter_expressions) == 1:
                    request_params["Filter"] = filter_expressions[0]
                else:
                    request_params["Filter"] = {
                        "And": filter_expressions
                    }

            response = client.get_cost_and_usage(**request_params)

            # Aggregate costs by dimension
            dimension_costs = {}
            for result in response.get('ResultsByTime', []):
                for group in result.get('Groups', []):
                    dim_value = group['Keys'][0] if group.get('Keys') else 'Unknown'
                    amount = float(group.get('Metrics', {}).get('UnblendedCost', {}).get('Amount', '0'))

                    if dim_value in dimension_costs:
                        dimension_costs[dim_value] += amount
                    else:
                        dimension_costs[dim_value] = amount

            # Calculate total cost
            total_cost = sum(dimension_costs.values())

            # Build breakdown with percentages
            breakdown = []
            for dim_value, cost in sorted(dimension_costs.items(), key=lambda x: x[1], reverse=True):
                percentage = (cost / total_cost * 100) if total_cost > 0 else 0
                breakdown.append({
                    'dimension_value': dim_value,
                    'cost': round(cost, 2),
                    'percentage': round(percentage, 2)
                })

            result_data = {
                'profile_name': account_name,
                'start_date': start_date,
                'end_date': end_date,
                'dimension': dimension,
                'filters': filters,
                'total_cost': round(total_cost, 2),
                'breakdown': breakdown,
                'currency': 'USD'
            }

            # Cache the result
            cache_manager.set(cache_key, result_data, settings.CACHE_TTL_SERVICE_BREAKDOWN)
            logger.debug(f"Cached drill-down data: {cache_key}")

            return result_data

        except Exception as e:
            logger.error(f"Error fetching drill-down for {account_name}: {e}")
            raise
