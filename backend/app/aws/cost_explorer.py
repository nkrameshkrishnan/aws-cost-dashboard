"""
AWS Cost Explorer service wrapper.
Provides methods to fetch cost and usage data from AWS Cost Explorer API.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from botocore.exceptions import ClientError
import logging

from app.aws.session_manager import session_manager

logger = logging.getLogger(__name__)


class CostExplorerService:
    """
    Wrapper for AWS Cost Explorer API.
    Handles cost data retrieval, forecasting, and filtering.
    """

    def __init__(self, profile_name: str = "default"):
        """
        Initialize Cost Explorer service for a specific profile.

        Args:
            profile_name: AWS profile name
        """
        self.profile_name = profile_name
        # Cost Explorer is only available in us-east-1
        self.client = session_manager.get_client(
            'ce',
            profile_name=profile_name,
            region_name='us-east-1'
        )

    def get_cost_and_usage(
        self,
        start_date: str,
        end_date: str,
        granularity: str = "DAILY",
        metrics: Optional[List[str]] = None,
        group_by: Optional[List[Dict]] = None,
        filter_expr: Optional[Dict] = None
    ) -> Dict:
        """
        Get cost and usage data from AWS Cost Explorer.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            granularity: DAILY, MONTHLY, or HOURLY
            metrics: List of metrics (default: ["UnblendedCost"])
            group_by: List of grouping dimensions
            filter_expr: Cost Explorer filter expression

        Returns:
            Cost and usage data from API

        Raises:
            ClientError: If API call fails
        """
        if metrics is None:
            metrics = ["UnblendedCost"]

        try:
            request_params = {
                "TimePeriod": {
                    "Start": start_date,
                    "End": end_date
                },
                "Granularity": granularity,
                "Metrics": metrics
            }

            if group_by:
                request_params["GroupBy"] = group_by

            if filter_expr:
                request_params["Filter"] = filter_expr

            logger.info(
                f"Fetching cost data for {self.profile_name}: "
                f"{start_date} to {end_date}, granularity={granularity}"
            )

            response = self.client.get_cost_and_usage(**request_params)

            logger.debug(f"Retrieved {len(response.get('ResultsByTime', []))} time periods")
            return response

        except ClientError as e:
            logger.error(f"Error fetching cost data: {e}")
            raise

    def get_cost_forecast(
        self,
        start_date: str,
        end_date: str,
        metric: str = "UNBLENDED_COST",
        granularity: str = "MONTHLY",
        filter_expr: Optional[Dict] = None
    ) -> Dict:
        """
        Get cost forecast from AWS Cost Explorer.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            metric: Forecast metric (UNBLENDED_COST or AMORTIZED_COST)
            granularity: DAILY or MONTHLY
            filter_expr: Cost Explorer filter expression

        Returns:
            Cost forecast data from API

        Raises:
            ClientError: If API call fails
        """
        try:
            request_params = {
                "TimePeriod": {
                    "Start": start_date,
                    "End": end_date
                },
                "Metric": metric,
                "Granularity": granularity
            }

            if filter_expr:
                request_params["Filter"] = filter_expr

            logger.info(
                f"Fetching cost forecast for {self.profile_name}: "
                f"{start_date} to {end_date}"
            )

            response = self.client.get_cost_forecast(**request_params)
            return response

        except ClientError as e:
            logger.error(f"Error fetching cost forecast: {e}")
            raise

    def get_dimension_values(
        self,
        dimension: str,
        start_date: str,
        end_date: str,
        filter_expr: Optional[Dict] = None
    ) -> List[str]:
        """
        Get available values for a dimension (e.g., SERVICE, ACCOUNT).

        Args:
            dimension: Dimension name (SERVICE, LINKED_ACCOUNT, etc.)
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            filter_expr: Optional filter expression

        Returns:
            List of dimension values

        Raises:
            ClientError: If API call fails
        """
        try:
            request_params = {
                "TimePeriod": {
                    "Start": start_date,
                    "End": end_date
                },
                "Dimension": dimension
            }

            if filter_expr:
                request_params["Filter"] = filter_expr

            logger.info(f"Fetching {dimension} dimension values for {self.profile_name}")

            response = self.client.get_dimension_values(**request_params)
            values = [item['Value'] for item in response.get('DimensionValues', [])]

            logger.debug(f"Found {len(values)} values for dimension {dimension}")
            return values

        except ClientError as e:
            logger.error(f"Error fetching dimension values: {e}")
            raise

    def get_tags(
        self,
        start_date: str,
        end_date: str,
        tag_key: Optional[str] = None
    ) -> List[str]:
        """
        Get available tag keys or values for a specific tag key.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            tag_key: Specific tag key to get values for (optional)

        Returns:
            List of tag keys or values

        Raises:
            ClientError: If API call fails
        """
        try:
            request_params = {
                "TimePeriod": {
                    "Start": start_date,
                    "End": end_date
                }
            }

            if tag_key:
                request_params["TagKey"] = tag_key

            logger.info(f"Fetching tags for {self.profile_name}")

            response = self.client.get_tags(**request_params)
            tags = response.get('Tags', [])

            logger.debug(f"Found {len(tags)} tags")
            return tags

        except ClientError as e:
            logger.error(f"Error fetching tags: {e}")
            raise

    def get_service_costs(
        self,
        start_date: str,
        end_date: str,
        granularity: str = "MONTHLY"
    ) -> Dict:
        """
        Get costs grouped by AWS service.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            granularity: DAILY or MONTHLY

        Returns:
            Cost data grouped by service
        """
        group_by = [
            {
                "Type": "DIMENSION",
                "Key": "SERVICE"
            }
        ]

        return self.get_cost_and_usage(
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
            group_by=group_by
        )

    def get_daily_costs(
        self,
        days: int = 30,
        end_date: Optional[datetime] = None
    ) -> Dict:
        """
        Get daily costs for the past N days.

        Args:
            days: Number of days to look back
            end_date: End date (defaults to today)

        Returns:
            Daily cost data
        """
        if end_date is None:
            end_date = datetime.now()

        start_date = end_date - timedelta(days=days)

        return self.get_cost_and_usage(
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            granularity="DAILY"
        )

    def get_monthly_costs(
        self,
        months: int = 6,
        end_date: Optional[datetime] = None
    ) -> Dict:
        """
        Get monthly costs for the past N months.

        Args:
            months: Number of months to look back
            end_date: End date (defaults to today)

        Returns:
            Monthly cost data
        """
        if end_date is None:
            end_date = datetime.now()

        # Go back N months
        start_date = end_date - timedelta(days=months * 30)

        return self.get_cost_and_usage(
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            granularity="MONTHLY"
        )

    def get_current_month_forecast(self) -> Dict:
        """
        Get cost forecast for the current month.

        Returns:
            Forecast for current month
        """
        now = datetime.now()
        start_date = now.strftime("%Y-%m-%d")

        # End of current month
        if now.month == 12:
            end_date = datetime(now.year + 1, 1, 1).strftime("%Y-%m-%d")
        else:
            end_date = datetime(now.year, now.month + 1, 1).strftime("%Y-%m-%d")

        return self.get_cost_forecast(
            start_date=start_date,
            end_date=end_date,
            granularity="MONTHLY"
        )


def get_cost_explorer_service(profile_name: str = "default") -> CostExplorerService:
    """
    Factory function to create a CostExplorerService instance.

    Args:
        profile_name: AWS profile name

    Returns:
        CostExplorerService instance
    """
    return CostExplorerService(profile_name=profile_name)
