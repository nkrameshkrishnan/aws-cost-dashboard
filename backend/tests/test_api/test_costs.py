"""
Tests for cost API endpoints.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch
from app.services.cost_processor_db import DatabaseCostProcessor
from app.services.cost_processor import aggregate_multi_profile_costs


class TestCostEndpoints:
    """Test cost-related API endpoints."""

    def test_get_cost_summary(self, client):
        """Test getting cost summary."""
        with patch.object(DatabaseCostProcessor, 'get_cost_summary', return_value={
            "total_cost": 1000.00,
            "profile_name": "default",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "currency": "USD",
            "period_count": 31
        }):
            response = client.get(
                "/api/v1/costs/summary?profile_name=default&start_date=2024-01-01&end_date=2024-01-31"
            )

            assert response.status_code == 200
            data = response.json()
            assert "total_cost" in data

    def test_get_cost_summary_with_date_range(self, client):
        """Test getting cost summary with custom date range."""
        start_date = "2024-01-01"
        end_date = "2024-01-31"

        with patch.object(DatabaseCostProcessor, 'get_cost_summary', return_value={
            "total_cost": 500.00,
            "profile_name": "default",
            "start_date": start_date,
            "end_date": end_date,
            "currency": "USD",
            "period_count": 31
        }):
            response = client.get(
                f"/api/v1/costs/summary?profile_name=default&start_date={start_date}&end_date={end_date}"
            )

            assert response.status_code == 200

    def test_get_daily_costs(self, client):
        """Test getting daily cost breakdown."""
        # get_daily_costs returns List[Dict], not a wrapped response
        with patch.object(DatabaseCostProcessor, 'get_daily_costs', return_value=[
            {"date": "2024-01-01", "cost": 100.00},
            {"date": "2024-01-02", "cost": 150.00}
        ]):
            response = client.get(
                "/api/v1/costs/daily?profile_name=default&start_date=2024-01-01&end_date=2024-01-31"
            )

            assert response.status_code == 200
            data = response.json()
            assert "daily_costs" in data

    def test_get_costs_by_service(self, client):
        """Test getting cost breakdown by service."""
        # get_service_breakdown returns List[Dict], not a wrapped response
        with patch.object(DatabaseCostProcessor, 'get_service_breakdown', return_value=[
            {"service": "Amazon EC2", "cost": 200.00},
            {"service": "Amazon RDS", "cost": 100.00}
        ]):
            response = client.get(
                "/api/v1/costs/by-service?profile_name=default&start_date=2024-01-01&end_date=2024-01-31"
            )

            assert response.status_code == 200
            data = response.json()
            assert "services" in data

    def test_get_cost_forecast(self, client):
        """Test getting cost forecast."""
        # get_forecast returns Dict without profile_name (endpoint adds it)
        with patch.object(DatabaseCostProcessor, 'get_forecast', return_value={
            "forecasted_cost": 3000.00,
            "forecast_period_start": "2024-02-01",
            "forecast_period_end": "2024-02-29",
            "currency": "USD"
        }):
            response = client.get("/api/v1/costs/forecast?profile_name=default")

            assert response.status_code == 200
            data = response.json()
            assert "forecasted_cost" in data or "forecast" in data

    def test_get_cost_trend(self, client):
        """Test getting cost trends."""
        # get_cost_trend returns List[Dict], not a wrapped response
        with patch.object(DatabaseCostProcessor, 'get_cost_trend', return_value=[
            {"month": "2024-01", "cost": 1000.00},
            {"month": "2024-02", "cost": 1200.00}
        ]):
            response = client.get("/api/v1/costs/trend?profile_name=default")

            assert response.status_code == 200

    def test_get_mom_comparison(self, client):
        """Test getting month-over-month comparison."""
        with patch.object(DatabaseCostProcessor, 'calculate_mom_change', return_value={
            "current_month": {"cost": 1200.00, "month": "2024-02"},
            "previous_month": {"cost": 1000.00, "month": "2024-01"},
            "change_amount": 200.00,
            "change_percent": 20.0
        }):
            response = client.get(
                "/api/v1/costs/mom-comparison?profile_name=default"
                "&current_month_start=2024-02-01&current_month_end=2024-02-29"
            )

            assert response.status_code == 200

    def test_invalid_date_format(self, client):
        """Test handling of invalid date format."""
        response = client.get(
            "/api/v1/costs/summary?profile_name=default&start_date=invalid&end_date=invalid"
        )

        # Endpoint catches ValueError and returns 404
        assert response.status_code == 404

    def test_future_date_range(self, client):
        """Test handling of future date range."""
        future_date = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")

        with patch.object(DatabaseCostProcessor, 'get_cost_summary', return_value={
            "total_cost": 0.00,
            "profile_name": "default",
            "start_date": future_date,
            "end_date": future_date,
            "currency": "USD",
            "period_count": 1
        }):
            response = client.get(
                f"/api/v1/costs/summary?profile_name=default&start_date={future_date}&end_date={future_date}"
            )

            # Should handle gracefully
            assert response.status_code in [200, 400, 422]

    def test_missing_required_parameters(self, client):
        """Test handling of missing required profile_name parameter."""
        response = client.get("/api/v1/costs/summary")

        # Should return 422 for missing required parameter
        assert response.status_code == 422

    def test_get_dashboard_data(self, client):
        """Test getting optimized dashboard data."""
        with patch.object(DatabaseCostProcessor, 'get_cost_summary', return_value={
            "total_cost": 1000.00,
            "profile_name": "default",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "currency": "USD",
            "period_count": 31
        }), \
        patch.object(DatabaseCostProcessor, 'calculate_mom_change', return_value={
            "current_month": {"cost": 1200.00, "month": "2024-02"},
            "previous_month": {"cost": 1000.00, "month": "2024-01"},
            "change_amount": 200.00,
            "change_percent": 20.0
        }), \
        patch.object(DatabaseCostProcessor, 'get_forecast', return_value={
            "forecasted_cost": 500.00,
            "forecast_period_start": "2024-02-01",
            "forecast_period_end": "2024-02-29",
            "currency": "USD"
        }):
            response = client.get("/api/v1/costs/dashboard?profile_name=default")

            assert response.status_code == 200

    def test_cost_endpoints_require_profile_name(self, client):
        """Test that endpoints require profile_name parameter."""
        endpoints = [
            "/summary?start_date=2024-01-01&end_date=2024-01-31",
            "/daily?start_date=2024-01-01&end_date=2024-01-31",
            "/by-service?start_date=2024-01-01&end_date=2024-01-31"
        ]

        for endpoint in endpoints:
            response = client.get(f"/api/v1/costs{endpoint}")
            # Should return 422 for missing required parameter
            assert response.status_code == 422, f"Endpoint {endpoint} should require profile_name"

    def test_nonexistent_endpoints_return_404(self, client):
        """Test that non-existent endpoints return 404."""
        nonexistent_endpoints = [
            "/api/v1/costs/by-region",
            "/api/v1/costs/by-account",
            "/api/v1/costs/monthly",
            "/api/v1/costs/comparison",
            "/api/v1/costs/trends",
            "/api/v1/costs/optimization"
        ]

        for endpoint in nonexistent_endpoints:
            response = client.get(f"{endpoint}?profile_name=default")
            assert response.status_code == 404, f"Endpoint {endpoint} should return 404"

    def test_large_date_range_performance(self, client):
        """Test performance with large date range."""
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")

        # get_daily_costs returns List[Dict], not a wrapped response
        with patch.object(DatabaseCostProcessor, 'get_daily_costs', return_value=[
            {"date": "2024-01-01", "cost": 100.0} for _ in range(365)
        ]):
            response = client.get(
                f"/api/v1/costs/daily?profile_name=default&start_date={start_date}&end_date={end_date}"
            )

            assert response.status_code == 200

    def test_multi_profile_costs(self, client):
        """Test getting costs for multiple profiles."""
        with patch('app.api.v1.endpoints.costs.aggregate_multi_profile_costs', return_value={
            "profiles": ["prod", "dev"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "total_cost": 5000.00,
            "profile_breakdown": [
                {"profile_name": "prod", "cost": 3000.00},
                {"profile_name": "dev", "cost": 2000.00}
            ]
        }):
            response = client.get(
                "/api/v1/costs/multi-profile?profile_names=prod,dev&start_date=2024-01-01&end_date=2024-01-31"
            )

            assert response.status_code == 200
