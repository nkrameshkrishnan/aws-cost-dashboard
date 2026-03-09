"""
Tests for AWS Cost Explorer service.
Uses unittest.mock to avoid requiring real AWS credentials.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, call
from botocore.exceptions import ClientError

from app.aws.cost_explorer import CostExplorerService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service():
    """Create CostExplorerService with mocked boto3 CE client."""
    mock_client = MagicMock()
    with patch("app.aws.session_manager.AWSSessionManager.get_client", return_value=mock_client):
        svc = CostExplorerService()
    svc.client = mock_client
    return svc, mock_client


def _ce_response(result_count: int = 1) -> dict:
    """Build a minimal Cost Explorer ResultsByTime payload."""
    results = []
    for i in range(result_count):
        d = datetime.now().date() - timedelta(days=i)
        results.append(
            {
                "TimePeriod": {
                    "Start": d.isoformat(),
                    "End": (d + timedelta(days=1)).isoformat(),
                },
                "Total": {"UnblendedCost": {"Amount": "10.00", "Unit": "USD"}},
                "Groups": [],
                "Estimated": False,
            }
        )
    return {"ResultsByTime": results, "ResponseMetadata": {}}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCostExplorerService:
    """Test AWS Cost Explorer service integration."""

    def test_get_cost_and_usage_daily(self):
        """Test getting daily cost and usage data."""
        svc, mock_client = _make_service()
        mock_client.get_cost_and_usage.return_value = _ce_response(30)

        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)

        result = svc.get_cost_and_usage(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            granularity="DAILY",
        )

        assert result is not None
        assert "ResultsByTime" in result
        mock_client.get_cost_and_usage.assert_called_once()

    def test_get_cost_and_usage_monthly(self):
        """Test getting monthly cost and usage data."""
        svc, mock_client = _make_service()
        mock_client.get_cost_and_usage.return_value = _ce_response(3)

        end_date = datetime.now().date()
        start_date = end_date.replace(day=1) - timedelta(days=90)

        result = svc.get_cost_and_usage(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            granularity="MONTHLY",
        )

        assert result is not None
        assert "ResultsByTime" in result

    def test_get_daily_costs(self):
        """Test the get_daily_costs shortcut method."""
        svc, mock_client = _make_service()
        mock_client.get_cost_and_usage.return_value = _ce_response(30)

        result = svc.get_daily_costs(days=30)

        assert result is not None
        assert "ResultsByTime" in result

    def test_get_monthly_costs(self):
        """Test the get_monthly_costs shortcut method."""
        svc, mock_client = _make_service()
        mock_client.get_cost_and_usage.return_value = _ce_response(3)

        result = svc.get_monthly_costs(months=3)

        assert result is not None
        assert "ResultsByTime" in result

    def test_get_service_costs(self):
        """Test getting cost breakdown by service."""
        svc, mock_client = _make_service()
        mock_client.get_cost_and_usage.return_value = _ce_response(30)

        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)

        result = svc.get_service_costs(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

        assert result is not None
        assert "ResultsByTime" in result

    def test_get_cost_forecast(self):
        """Test getting cost forecast."""
        svc, mock_client = _make_service()
        mock_client.get_cost_forecast.return_value = {
            "Total": {"Amount": "300.00", "Unit": "USD"},
            "ForecastResultsByTime": [],
        }

        start_date = datetime.now().date()
        end_date = start_date + timedelta(days=30)

        result = svc.get_cost_forecast(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

        assert result is not None
        assert "Total" in result or "ForecastResultsByTime" in result

    def test_get_current_month_forecast(self):
        """Test getting current month forecast."""
        svc, mock_client = _make_service()
        mock_client.get_cost_forecast.return_value = {
            "Total": {"Amount": "500.00", "Unit": "USD"},
            "ForecastResultsByTime": [],
        }

        result = svc.get_current_month_forecast()

        assert result is not None
        mock_client.get_cost_forecast.assert_called_once()

    def test_get_tags(self):
        """Test getting tag values."""
        svc, mock_client = _make_service()
        mock_client.get_tags.return_value = {
            "Tags": ["production", "staging"],
            "ResponseMetadata": {},
        }

        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)

        result = svc.get_tags(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            tag_key="Environment",
        )

        assert result is not None
        mock_client.get_tags.assert_called_once()

    def test_get_dimension_values(self):
        """Test getting dimension values."""
        svc, mock_client = _make_service()
        mock_client.get_dimension_values.return_value = {
            "DimensionValues": [
                {"Value": "Amazon EC2", "Attributes": {}},
                {"Value": "Amazon S3", "Attributes": {}},
            ],
            "ResponseMetadata": {},
        }

        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)

        result = svc.get_dimension_values(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            dimension="SERVICE",
        )

        assert result is not None
        mock_client.get_dimension_values.assert_called_once()

    def test_get_cost_and_usage_with_filters(self):
        """Test getting costs with filters applied."""
        svc, mock_client = _make_service()
        mock_client.get_cost_and_usage.return_value = _ce_response(30)

        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)

        filters = {"Tags": {"Key": "Environment", "Values": ["production"]}}

        result = svc.get_cost_and_usage(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            granularity="DAILY",
            filter_expr=filters,
        )

        assert result is not None
        mock_client.get_cost_and_usage.assert_called_once()

    @pytest.mark.slow
    def test_large_date_range(self):
        """Test handling of large date range (365 days)."""
        svc, mock_client = _make_service()
        mock_client.get_cost_and_usage.return_value = _ce_response(12)

        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=365)

        result = svc.get_cost_and_usage(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            granularity="MONTHLY",
        )

        assert result is not None
        assert "ResultsByTime" in result

    def test_client_error_propagates(self):
        """Test that ClientError from boto3 propagates appropriately."""
        svc, mock_client = _make_service()
        error_response = {
            "Error": {"Code": "ValidationException", "Message": "Invalid date range"}
        }
        mock_client.get_cost_and_usage.side_effect = ClientError(
            error_response, "GetCostAndUsage"
        )

        with pytest.raises(Exception):
            svc.get_cost_and_usage(
                start_date="2024-02-01",
                end_date="2024-01-01",
                granularity="DAILY",
            )

    def test_group_by_service(self):
        """Test getting costs grouped by service."""
        svc, mock_client = _make_service()
        resp = _ce_response(5)
        # Add groups to the response
        for r in resp["ResultsByTime"]:
            r["Groups"] = [
                {
                    "Keys": ["Amazon EC2"],
                    "Metrics": {"UnblendedCost": {"Amount": "5.00", "Unit": "USD"}},
                }
            ]
        mock_client.get_cost_and_usage.return_value = resp

        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=5)

        result = svc.get_cost_and_usage(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            granularity="DAILY",
            group_by=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )

        assert result is not None
        assert "ResultsByTime" in result
