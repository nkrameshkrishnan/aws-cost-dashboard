"""
Tests for cost processor service.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from moto import mock_ce

from app.services.cost_processor import CostProcessor, aggregate_multi_profile_costs


class TestCostProcessor:
    """Test cost processor service."""

    @mock_ce
    def test_get_daily_costs(self, aws_credentials):
        """Test getting daily cost breakdown."""
        with patch('app.services.cost_processor.CostExplorerService') as mock_ce_service:
            # Mock the Cost Explorer service response
            mock_service = Mock()
            mock_service.get_cost_and_usage.return_value = {
                "ResultsByTime": [
                    {
                        "TimePeriod": {
                            "Start": "2024-01-01",
                            "End": "2024-01-02"
                        },
                        "Total": {
                            "UnblendedCost": {
                                "Amount": "100.50",
                                "Unit": "USD"
                            }
                        }
                    },
                    {
                        "TimePeriod": {
                            "Start": "2024-01-02",
                            "End": "2024-01-03"
                        },
                        "Total": {
                            "UnblendedCost": {
                                "Amount": "150.75",
                                "Unit": "USD"
                            }
                        }
                    }
                ]
            }
            mock_ce_service.return_value = mock_service

            # Mock cache manager
            with patch('app.services.cost_processor.cache_manager') as mock_cache:
                mock_cache.get_or_fetch.side_effect = lambda key, func, ttl: func()

                processor = CostProcessor(profile_name="default")
                result = processor.get_daily_costs("2024-01-01", "2024-01-03")

                # Assertions
                assert len(result) == 2
                assert result[0]["date"] == "2024-01-01"
                assert result[0]["cost"] == 100.50
                assert result[1]["date"] == "2024-01-02"
                assert result[1]["cost"] == 150.75

    @mock_ce
    def test_get_cost_summary(self, aws_credentials):
        """Test getting cost summary."""
        with patch('app.services.cost_processor.CostExplorerService') as mock_ce_service:
            mock_service = Mock()
            mock_service.get_cost_and_usage.return_value = {
                "ResultsByTime": [
                    {
                        "TimePeriod": {
                            "Start": "2024-01-01",
                            "End": "2024-01-31"
                        },
                        "Total": {
                            "UnblendedCost": {
                                "Amount": "1500.00",
                                "Unit": "USD"
                            }
                        }
                    }
                ]
            }
            mock_ce_service.return_value = mock_service

            with patch('app.services.cost_processor.cache_manager') as mock_cache:
                mock_cache.get_or_fetch.side_effect = lambda key, func, ttl: func()

                processor = CostProcessor(profile_name="default")
                result = processor.get_cost_summary("2024-01-01", "2024-01-31")

                assert result["total_cost"] == 1500.00
                assert result["currency"] == "USD"
                assert result["profile_name"] == "default"

    @mock_ce
    def test_get_service_breakdown(self, aws_credentials):
        """Test getting service breakdown."""
        with patch('app.services.cost_processor.CostExplorerService') as mock_ce_service:
            mock_service = Mock()
            mock_service.get_service_costs.return_value = {
                "ResultsByTime": [
                    {
                        "Groups": [
                            {
                                "Keys": ["Amazon EC2"],
                                "Metrics": {
                                    "UnblendedCost": {
                                        "Amount": "200.00",
                                        "Unit": "USD"
                                    }
                                }
                            },
                            {
                                "Keys": ["Amazon RDS"],
                                "Metrics": {
                                    "UnblendedCost": {
                                        "Amount": "150.00",
                                        "Unit": "USD"
                                    }
                                }
                            }
                        ]
                    }
                ]
            }
            mock_ce_service.return_value = mock_service

            with patch('app.services.cost_processor.cache_manager') as mock_cache:
                mock_cache.get_or_fetch.side_effect = lambda key, func, ttl: func()

                processor = CostProcessor(profile_name="default")
                result = processor.get_service_breakdown("2024-01-01", "2024-01-31", top_n=10)

                assert len(result) == 2
                assert result[0]["service"] == "Amazon EC2"
                assert result[0]["cost"] == 200.00
                assert result[1]["service"] == "Amazon RDS"
                assert result[1]["cost"] == 150.00

    @mock_ce
    def test_calculate_mom_change(self, aws_credentials):
        """Test month-over-month change calculation."""
        with patch('app.services.cost_processor.CostExplorerService') as mock_ce_service:
            mock_service = Mock()

            # Mock responses for current and previous month
            def mock_get_cost_and_usage(start_date, end_date, granularity):
                if "2024-02" in start_date:
                    # Current month
                    return {
                        "ResultsByTime": [{
                            "Total": {"UnblendedCost": {"Amount": "1200.00", "Unit": "USD"}}
                        }]
                    }
                else:
                    # Previous month
                    return {
                        "ResultsByTime": [{
                            "Total": {"UnblendedCost": {"Amount": "1000.00", "Unit": "USD"}}
                        }]
                    }

            mock_service.get_cost_and_usage.side_effect = mock_get_cost_and_usage
            mock_ce_service.return_value = mock_service

            with patch('app.services.cost_processor.cache_manager') as mock_cache:
                mock_cache.get_or_fetch.side_effect = lambda key, func, ttl: func()

                processor = CostProcessor(profile_name="default")
                result = processor.calculate_mom_change("2024-02-01", "2024-02-29")

                assert result["current_month"]["cost"] == 1200.00
                assert result["previous_month"]["cost"] == 1000.00
                assert result["change_amount"] == 200.00
                assert result["change_percent"] == 20.00

    @pytest.mark.unit
    def test_aggregate_multi_profile_costs(self, aws_credentials):
        """Test aggregating costs across multiple profiles."""
        with patch('app.services.cost_processor.CostProcessor') as mock_processor_class:
            # Mock two profiles
            mock_processor1 = Mock()
            mock_processor1.get_cost_summary.return_value = {
                "total_cost": 1000.00,
                "currency": "USD"
            }

            mock_processor2 = Mock()
            mock_processor2.get_cost_summary.return_value = {
                "total_cost": 1500.00,
                "currency": "USD"
            }

            mock_processor_class.side_effect = [mock_processor1, mock_processor2]

            result = aggregate_multi_profile_costs(
                ["profile1", "profile2"],
                "2024-01-01",
                "2024-01-31"
            )

            assert result["total_cost"] == 2500.00
            assert len(result["profile_breakdown"]) == 2
            assert result["profile_breakdown"][0]["cost"] == 1000.00
            assert result["profile_breakdown"][1]["cost"] == 1500.00

    @pytest.mark.unit
    def test_ttl_for_historical_data(self):
        """Test that historical data gets longer TTL."""
        from app.services.cost_processor import CostProcessor

        # Historical date range (past)
        ttl = CostProcessor._get_ttl_for_date_range("2023-01-01", "2023-01-31")

        # Should use historical TTL (longer cache)
        from app.config import settings
        assert ttl == settings.CACHE_TTL_HISTORICAL

    @pytest.mark.unit
    def test_ttl_for_current_data(self):
        """Test that current month data gets shorter TTL."""
        from app.services.cost_processor import CostProcessor
        from datetime import datetime

        # Current month
        now = datetime.now()
        current_month_start = now.replace(day=1).strftime("%Y-%m-%d")
        current_month_end = now.strftime("%Y-%m-%d")

        ttl = CostProcessor._get_ttl_for_date_range(current_month_start, current_month_end)

        # Should use current month TTL (shorter cache)
        from app.config import settings
        assert ttl == settings.CACHE_TTL_CURRENT_MONTH
