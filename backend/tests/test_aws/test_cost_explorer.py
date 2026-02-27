"""
Tests for AWS Cost Explorer service.
"""
import pytest
from datetime import datetime, timedelta
from moto import mock_ce
import boto3
from decimal import Decimal

from app.aws.cost_explorer import CostExplorerService


@pytest.fixture
def ce_client():
    """Create Cost Explorer client with mocked AWS."""
    with mock_ce():
        yield boto3.client('ce', region_name='us-east-1')


class TestCostExplorerService:
    """Test AWS Cost Explorer service integration."""

    @mock_ce
    def test_get_cost_and_usage_daily(self, aws_credentials):
        """Test getting daily cost and usage data."""
        service = CostExplorerService()

        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)

        result = service.get_cost_and_usage(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            granularity="DAILY"
        )

        assert result is not None
        assert "ResultsByTime" in result

    @mock_ce
    def test_get_cost_and_usage_monthly(self, aws_credentials):
        """Test getting monthly cost and usage data."""
        service = CostExplorerService()

        end_date = datetime.now().date()
        start_date = end_date.replace(day=1) - timedelta(days=90)

        result = service.get_cost_and_usage(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            granularity="MONTHLY"
        )

        assert result is not None
        assert "ResultsByTime" in result

    @mock_ce
    def test_get_cost_by_service(self, aws_credentials):
        """Test getting cost breakdown by service."""
        service = CostExplorerService()

        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)

        result = service.get_cost_by_service(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat()
        )

        assert result is not None
        assert "ResultsByTime" in result

    @mock_ce
    def test_get_cost_forecast(self, aws_credentials):
        """Test getting cost forecast."""
        service = CostExplorerService()

        start_date = datetime.now().date()
        end_date = start_date + timedelta(days=30)

        result = service.get_cost_forecast(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat()
        )

        assert result is not None
        # Forecast API returns different structure
        assert "Total" in result or "ForecastResultsByTime" in result

    @mock_ce
    def test_invalid_date_range(self, aws_credentials):
        """Test handling of invalid date range."""
        service = CostExplorerService()

        # End date before start date
        with pytest.raises(Exception):
            service.get_cost_and_usage(
                start_date="2024-02-01",
                end_date="2024-01-01",
                granularity="DAILY"
            )

    @mock_ce
    def test_get_cost_by_account(self, aws_credentials):
        """Test getting cost breakdown by account."""
        service = CostExplorerService()

        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)

        result = service.get_cost_by_dimension(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            dimension="LINKED_ACCOUNT"
        )

        assert result is not None
        assert "ResultsByTime" in result

    @mock_ce
    def test_get_cost_by_region(self, aws_credentials):
        """Test getting cost breakdown by region."""
        service = CostExplorerService()

        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)

        result = service.get_cost_by_dimension(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            dimension="REGION"
        )

        assert result is not None
        assert "ResultsByTime" in result

    @pytest.mark.unit
    def test_format_date_range(self):
        """Test date range formatting."""
        service = CostExplorerService()

        start = datetime(2024, 1, 1).date()
        end = datetime(2024, 1, 31).date()

        formatted = service._format_date_range(start, end)

        assert formatted["Start"] == "2024-01-01"
        assert formatted["End"] == "2024-01-31"

    @pytest.mark.unit
    def test_validate_granularity(self):
        """Test granularity validation."""
        service = CostExplorerService()

        valid_granularities = ["DAILY", "MONTHLY", "HOURLY"]

        for granularity in valid_granularities:
            assert service._validate_granularity(granularity) is True

        assert service._validate_granularity("INVALID") is False

    @mock_ce
    def test_get_tags(self, aws_credentials):
        """Test getting tag values."""
        service = CostExplorerService()

        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)

        result = service.get_tags(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            tag_key="Environment"
        )

        assert result is not None

    @mock_ce
    def test_get_cost_with_filters(self, aws_credentials):
        """Test getting costs with filters applied."""
        service = CostExplorerService()

        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)

        filters = {
            "Tags": {
                "Key": "Environment",
                "Values": ["production"]
            }
        }

        result = service.get_cost_and_usage(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            granularity="DAILY",
            filters=filters
        )

        assert result is not None

    @pytest.mark.slow
    @mock_ce
    def test_large_date_range(self, aws_credentials):
        """Test handling of large date range (365 days)."""
        service = CostExplorerService()

        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=365)

        result = service.get_cost_and_usage(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            granularity="MONTHLY"
        )

        assert result is not None
        assert "ResultsByTime" in result
