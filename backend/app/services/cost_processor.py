"""
Cost data processor service.
Handles aggregation, transformation, and analysis of AWS cost data.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

from app.aws.cost_explorer import CostExplorerService
from app.core.cache import cache_manager, cached
from app.config import settings

logger = logging.getLogger(__name__)


class CostProcessor:
    """
    Processes and aggregates AWS cost data.
    Implements business logic for cost analysis.
    """

    def __init__(self, profile_name: str = "default"):
        """
        Initialize cost processor for a specific AWS profile.

        Args:
            profile_name: AWS profile name
        """
        self.profile_name = profile_name
        self.ce_service = CostExplorerService(profile_name)

    def get_cost_summary(
        self,
        start_date: str,
        end_date: str
    ) -> Dict:
        """
        Get aggregated cost summary for a date range.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            Dictionary with cost summary data
        """
        cache_key = f"costs:summary:{self.profile_name}:{start_date}:{end_date}"

        def fetch_summary():
            response = self.ce_service.get_cost_and_usage(
                start_date=start_date,
                end_date=end_date,
                granularity="MONTHLY"
            )

            total_cost = 0.0
            results = response.get('ResultsByTime', [])

            for result in results:
                amount = result.get('Total', {}).get('UnblendedCost', {}).get('Amount', '0')
                total_cost += float(amount)

            return {
                'profile_name': self.profile_name,
                'start_date': start_date,
                'end_date': end_date,
                'total_cost': round(total_cost, 2),
                'currency': results[0].get('Total', {}).get('UnblendedCost', {}).get('Unit', 'USD') if results else 'USD',
                'period_count': len(results)
            }

        # Use cache with appropriate TTL
        ttl = self._get_ttl_for_date_range(start_date, end_date)
        return cache_manager.get_or_fetch(cache_key, fetch_summary, ttl)

    def get_daily_costs(
        self,
        start_date: str,
        end_date: str
    ) -> List[Dict]:
        """
        Get daily cost breakdown for a date range.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            List of daily cost records
        """
        cache_key = f"costs:daily:{self.profile_name}:{start_date}:{end_date}"

        def fetch_daily():
            response = self.ce_service.get_cost_and_usage(
                start_date=start_date,
                end_date=end_date,
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

        ttl = self._get_ttl_for_date_range(start_date, end_date)
        return cache_manager.get_or_fetch(cache_key, fetch_daily, ttl)

    def get_service_breakdown(
        self,
        start_date: str,
        end_date: str,
        top_n: int = 10
    ) -> List[Dict]:
        """
        Get cost breakdown by AWS service.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            top_n: Number of top services to return

        Returns:
            List of service cost records
        """
        cache_key = f"costs:services:{self.profile_name}:{start_date}:{end_date}:{top_n}"

        def fetch_services():
            response = self.ce_service.get_service_costs(
                start_date=start_date,
                end_date=end_date,
                granularity="MONTHLY"
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

            # Sort by cost descending
            sorted_services = sorted(
                service_costs.items(),
                key=lambda x: x[1],
                reverse=True
            )

            # Get top N services
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

            # Add "Others" category if there are more services
            if other_cost > 0:
                top_services.append({
                    'service': 'Others',
                    'cost': round(other_cost, 2)
                })

            return top_services

        ttl = settings.CACHE_TTL_SERVICE_BREAKDOWN
        return cache_manager.get_or_fetch(cache_key, fetch_services, ttl)

    def calculate_mom_change(
        self,
        current_month_start: str,
        current_month_end: str
    ) -> Dict:
        """
        Calculate month-over-month cost change.

        Args:
            current_month_start: Current month start date
            current_month_end: Current month end date

        Returns:
            Dictionary with MoM comparison data
        """
        # Calculate previous month dates
        current_start = datetime.strptime(current_month_start, "%Y-%m-%d")
        prev_month_start = current_start - timedelta(days=current_start.day)
        prev_month_start = prev_month_start.replace(day=1)
        prev_month_end = current_start - timedelta(days=1)

        # Get costs for both months
        current_cost = self.get_cost_summary(
            current_month_start,
            current_month_end
        )['total_cost']

        previous_cost = self.get_cost_summary(
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

    def get_cost_trend(
        self,
        months: int = 6
    ) -> List[Dict]:
        """
        Get monthly cost trend for the past N months.

        Args:
            months: Number of months to include

        Returns:
            List of monthly cost records with MoM changes
        """
        cache_key = f"costs:trend:{self.profile_name}:{months}"

        def fetch_trend():
            end_date = datetime.now()
            start_date = end_date - timedelta(days=months * 30)

            response = self.ce_service.get_cost_and_usage(
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
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

            return trend_data

        return cache_manager.get_or_fetch(cache_key, fetch_trend, settings.CACHE_TTL_HISTORICAL)

    def get_forecast(
        self,
        days: int = 30
    ) -> Dict:
        """
        Get cost forecast for the next N days.

        Args:
            days: Number of days to forecast

        Returns:
            Forecast data
        """
        cache_key = f"costs:forecast:{self.profile_name}:{days}"

        def fetch_forecast():
            start_date = datetime.now().strftime("%Y-%m-%d")
            end_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")

            try:
                response = self.ce_service.get_cost_forecast(
                    start_date=start_date,
                    end_date=end_date,
                    granularity="MONTHLY"
                )

                total = response.get('Total', {})
                forecast_amount = float(total.get('Amount', '0'))

                return {
                    'forecast_period_start': start_date,
                    'forecast_period_end': end_date,
                    'forecasted_cost': round(forecast_amount, 2),
                    'currency': total.get('Unit', 'USD')
                }
            except Exception as e:
                logger.warning(f"Forecast not available: {e}")
                return {
                    'forecast_period_start': start_date,
                    'forecast_period_end': end_date,
                    'forecasted_cost': 0.0,
                    'currency': 'USD',
                    'error': 'Forecast not available'
                }

        return cache_manager.get_or_fetch(cache_key, fetch_forecast, settings.CACHE_TTL_FORECAST)

    @staticmethod
    def _get_ttl_for_date_range(start_date: str, end_date: str) -> int:
        """
        Determine appropriate cache TTL based on date range.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            TTL in seconds
        """
        end = datetime.strptime(end_date, "%Y-%m-%d")
        now = datetime.now()

        # If end date is in the past (completed period), cache longer
        if end < now.replace(hour=0, minute=0, second=0, microsecond=0):
            return settings.CACHE_TTL_HISTORICAL

        # Current period, cache for shorter time
        return settings.CACHE_TTL_CURRENT_MONTH


def aggregate_multi_profile_costs(
    profile_names: List[str],
    start_date: str,
    end_date: str
) -> Dict:
    """
    Aggregate costs across multiple AWS profiles.

    Args:
        profile_names: List of AWS profile names
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        Aggregated cost data across all profiles
    """
    total_cost = 0.0
    profile_costs = []

    for profile in profile_names:
        processor = CostProcessor(profile)
        summary = processor.get_cost_summary(start_date, end_date)

        total_cost += summary['total_cost']
        profile_costs.append({
            'profile': profile,
            'cost': summary['total_cost']
        })

    return {
        'profiles': profile_names,
        'start_date': start_date,
        'end_date': end_date,
        'total_cost': round(total_cost, 2),
        'profile_breakdown': profile_costs
    }
