"""
Unit tests for KPIService.

The two pure synchronous methods (calculate_kpi_status, calculate_trend) are
tested directly. The async KPI calculators are tested with mocked DB and
external service dependencies.
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.kpi_service import KPIService
from app.models.kpi import (
    KPIStatus,
    KPIThreshold,
    KPIValue,
    KPICategory,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_threshold(excellent: float, good: float, warning: float, poor: float = 0.0) -> KPIThreshold:
    return KPIThreshold(excellent=excellent, good=good, warning=warning, poor=poor)


def _make_service(db=None):
    db = db or MagicMock()
    return KPIService(db)


# ---------------------------------------------------------------------------
# calculate_kpi_status — higher_is_better=True
# ---------------------------------------------------------------------------

class TestCalculateKpiStatusHigherIsBetter:
    def setup_method(self):
        self.svc = _make_service()
        self.thresholds = _make_threshold(excellent=90.0, good=75.0, warning=60.0)

    def test_excellent(self):
        status = self.svc.calculate_kpi_status(95.0, self.thresholds, higher_is_better=True)
        assert status == KPIStatus.EXCELLENT

    def test_good_at_boundary(self):
        status = self.svc.calculate_kpi_status(90.0, self.thresholds, higher_is_better=True)
        assert status == KPIStatus.EXCELLENT  # >= excellent

    def test_good(self):
        status = self.svc.calculate_kpi_status(80.0, self.thresholds, higher_is_better=True)
        assert status == KPIStatus.GOOD

    def test_warning(self):
        status = self.svc.calculate_kpi_status(65.0, self.thresholds, higher_is_better=True)
        assert status == KPIStatus.WARNING

    def test_poor(self):
        status = self.svc.calculate_kpi_status(50.0, self.thresholds, higher_is_better=True)
        assert status == KPIStatus.POOR


# ---------------------------------------------------------------------------
# calculate_kpi_status — higher_is_better=False (e.g. cost growth rate)
# ---------------------------------------------------------------------------

class TestCalculateKpiStatusLowerIsBetter:
    def setup_method(self):
        self.svc = _make_service()
        # Lower growth is better: excellent <= -5, good <= 5, warning <= 15
        self.thresholds = _make_threshold(excellent=-5.0, good=5.0, warning=15.0)

    def test_excellent_for_cost_reduction(self):
        status = self.svc.calculate_kpi_status(-10.0, self.thresholds, higher_is_better=False)
        assert status == KPIStatus.EXCELLENT

    def test_good_for_stable_growth(self):
        status = self.svc.calculate_kpi_status(3.0, self.thresholds, higher_is_better=False)
        assert status == KPIStatus.GOOD

    def test_warning_for_moderate_growth(self):
        status = self.svc.calculate_kpi_status(10.0, self.thresholds, higher_is_better=False)
        assert status == KPIStatus.WARNING

    def test_poor_for_high_growth(self):
        status = self.svc.calculate_kpi_status(20.0, self.thresholds, higher_is_better=False)
        assert status == KPIStatus.POOR


# ---------------------------------------------------------------------------
# calculate_trend
# ---------------------------------------------------------------------------

class TestCalculateTrend:
    def setup_method(self):
        self.svc = _make_service()

    def test_stable_when_previous_is_none(self):
        assert self.svc.calculate_trend(100.0, None) == "stable"

    def test_stable_when_previous_is_zero(self):
        assert self.svc.calculate_trend(100.0, 0.0) == "stable"

    def test_stable_for_sub_2_percent_change(self):
        # 1% increase → stable
        assert self.svc.calculate_trend(101.0, 100.0) == "stable"

    def test_up_for_positive_change(self):
        assert self.svc.calculate_trend(120.0, 100.0) == "up"

    def test_down_for_negative_change(self):
        assert self.svc.calculate_trend(80.0, 100.0) == "down"

    def test_boundary_exactly_2_percent(self):
        # exactly 2% → "up" (abs >= 2%)
        result = self.svc.calculate_trend(102.0, 100.0)
        assert result == "up"


# ---------------------------------------------------------------------------
# calculate_cost_growth_rate (async)
# ---------------------------------------------------------------------------

class TestCalculateCostGrowthRate:
    @pytest.mark.asyncio
    @patch("app.services.kpi_service.DatabaseCostProcessor")
    async def test_positive_growth_rate(self, MockDBC):
        db = MagicMock()
        svc = KPIService(db)

        # Current month: $1200, previous month: $1000 → 20% growth
        MockDBC.get_cost_summary.side_effect = [
            {"total_cost": 1200.0},  # current month
            {"total_cost": 1000.0},  # previous month
        ]

        result = await svc.calculate_cost_growth_rate("prod")

        assert isinstance(result, KPIValue)
        assert abs(result.value - 20.0) < 0.1

    @pytest.mark.asyncio
    @patch("app.services.kpi_service.DatabaseCostProcessor")
    async def test_zero_growth_rate_when_no_previous_month_data(self, MockDBC):
        db = MagicMock()
        svc = KPIService(db)

        MockDBC.get_cost_summary.side_effect = [
            {"total_cost": 1000.0},
            {"total_cost": 0.0},  # previous = 0 → growth = 0
        ]

        result = await svc.calculate_cost_growth_rate("prod")

        assert result.value == 0.0

    @pytest.mark.asyncio
    @patch("app.services.kpi_service.DatabaseCostProcessor")
    async def test_returns_unknown_on_exception(self, MockDBC):
        db = MagicMock()
        svc = KPIService(db)
        MockDBC.get_cost_summary.side_effect = Exception("DB error")

        result = await svc.calculate_cost_growth_rate("prod")
        assert result.status == KPIStatus.UNKNOWN


# ---------------------------------------------------------------------------
# calculate_daily_spend_rate (async)
# ---------------------------------------------------------------------------

class TestCalculateDailySpendRate:
    @pytest.mark.asyncio
    @patch("app.services.kpi_service.DatabaseCostProcessor")
    async def test_returns_average_daily_spend(self, MockDBC):
        db = MagicMock()
        svc = KPIService(db)
        MockDBC.get_cost_summary.return_value = {"total_cost": 300.0}

        result = await svc.calculate_daily_spend_rate("prod")

        assert isinstance(result, KPIValue)
        # daily_avg = 300 / today.day — just check it's > 0
        assert result.value > 0

    @pytest.mark.asyncio
    @patch("app.services.kpi_service.DatabaseCostProcessor")
    async def test_returns_unknown_on_exception(self, MockDBC):
        db = MagicMock()
        svc = KPIService(db)
        MockDBC.get_cost_summary.side_effect = Exception("DB timeout")

        result = await svc.calculate_daily_spend_rate("prod")
        assert result.status == KPIStatus.UNKNOWN


# ---------------------------------------------------------------------------
# calculate_budget_utilization (async)
# ---------------------------------------------------------------------------

class TestCalculateBudgetUtilization:
    @pytest.mark.asyncio
    @patch("app.services.kpi_service.AWSBudgetsService")
    @patch("app.services.kpi_service.DatabaseCostProcessor")
    async def test_returns_zero_when_no_budgets(self, MockDBC, MockAWS):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        svc = KPIService(db)

        result = await svc.calculate_budget_utilization("prod")

        assert result.value == 0.0
        assert result.status == KPIStatus.UNKNOWN

    @pytest.mark.asyncio
    @patch("app.services.kpi_service.AWSBudgetsService")
    @patch("app.services.kpi_service.DatabaseCostProcessor")
    async def test_utilization_uses_linear_projection_on_aws_error(self, MockDBC, MockAWS):
        db = MagicMock()

        budget = MagicMock()
        budget.name = "Q1 Budget"
        budget.amount = 1000.0
        db.query.return_value.filter.return_value.all.return_value = [budget]

        MockDBC.get_cost_summary.return_value = {"total_cost": 500.0}
        MockAWS.get_budget_forecast.side_effect = Exception("AWS unavailable")

        svc = KPIService(db)
        result = await svc.calculate_budget_utilization("prod")

        assert isinstance(result, KPIValue)
        assert result.value >= 0.0  # Should fall back gracefully

    @pytest.mark.asyncio
    @patch("app.services.kpi_service.AWSBudgetsService")
    @patch("app.services.kpi_service.DatabaseCostProcessor")
    async def test_returns_unknown_on_exception(self, MockDBC, MockAWS):
        db = MagicMock()
        db.query.side_effect = Exception("DB down")
        svc = KPIService(db)

        result = await svc.calculate_budget_utilization("prod")
        assert result.status == KPIStatus.UNKNOWN


# ---------------------------------------------------------------------------
# calculate_savings_potential (async)
# ---------------------------------------------------------------------------

class TestCalculateSavingsPotential:
    @pytest.mark.asyncio
    @patch("app.services.kpi_service.job_storage")
    @patch("app.services.kpi_service.DatabaseCostProcessor")
    @patch("app.services.kpi_service.AWSBudgetsService")
    async def test_uses_audit_results_when_available(self, MockAWS, MockDBC, mock_job_storage):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        svc = KPIService(db)

        mock_job_storage.list_jobs.return_value = [
            {
                "status": "completed",
                "results": {"summary": {"total_potential_savings": 500.0}}
            }
        ]

        result = await svc.calculate_savings_potential("prod")

        assert isinstance(result, KPIValue)
        assert result.value == 500.0

    @pytest.mark.asyncio
    @patch("app.services.kpi_service.job_storage")
    @patch("app.services.kpi_service.AWSBudgetsService")
    @patch("app.services.kpi_service.DatabaseCostProcessor")
    async def test_falls_back_when_no_audit_results(self, MockDBC, MockAWS, mock_job_storage):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        svc = KPIService(db)

        mock_job_storage.list_jobs.return_value = []
        MockDBC.get_cost_summary.return_value = {"total_cost": 0.0}
        MockAWS.get_budget_forecast.side_effect = Exception("unavailable")

        result = await svc.calculate_savings_potential("prod")
        assert isinstance(result, KPIValue)

    @pytest.mark.asyncio
    @patch("app.services.kpi_service.job_storage")
    async def test_returns_excellent_on_exception(self, mock_job_storage):
        db = MagicMock()
        db.query.side_effect = Exception("DB down")
        svc = KPIService(db)
        mock_job_storage.list_jobs.side_effect = Exception("storage error")

        result = await svc.calculate_savings_potential("prod")
        assert result.status == KPIStatus.EXCELLENT  # fallback for savings


# ---------------------------------------------------------------------------
# calculate_resource_waste_ratio (async)
# ---------------------------------------------------------------------------

class TestCalculateResourceWasteRatio:
    @pytest.mark.asyncio
    @patch("app.services.kpi_service.AWSBudgetsService")
    @patch("app.services.kpi_service.DatabaseCostProcessor")
    async def test_zero_waste_for_on_budget_account(self, MockDBC, MockAWS):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        svc = KPIService(db)

        # No budgets → utilization = 0, growth = 0 → waste = 0
        result = await svc.calculate_resource_waste_ratio("prod")

        assert isinstance(result, KPIValue)
        # 0% utilization and 0% growth → waste_ratio = 0
        assert result.value == 0.0

    @pytest.mark.asyncio
    @patch("app.services.kpi_service.AWSBudgetsService")
    @patch("app.services.kpi_service.DatabaseCostProcessor")
    async def test_returns_excellent_on_exception(self, MockDBC, MockAWS):
        db = MagicMock()
        db.query.side_effect = Exception("DB down")
        svc = KPIService(db)

        result = await svc.calculate_resource_waste_ratio("prod")
        assert result.status == KPIStatus.EXCELLENT  # fallback


# ---------------------------------------------------------------------------
# calculate_all_kpis (async)
# ---------------------------------------------------------------------------

class TestCalculateAllKpis:
    @pytest.mark.asyncio
    @patch("app.services.kpi_service.AWSBudgetsService")
    @patch("app.services.kpi_service.DatabaseCostProcessor")
    @patch("app.services.kpi_service.job_storage")
    async def test_returns_all_six_kpis(self, mock_jobs, MockDBC, MockAWS):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        mock_jobs.list_jobs.return_value = []
        MockDBC.get_cost_summary.return_value = {"total_cost": 0.0}
        MockAWS.get_budget_forecast.side_effect = Exception("no aws")
        svc = KPIService(db)

        result = await svc.calculate_all_kpis("prod")

        expected_keys = {
            "cost_efficiency",
            "budget_utilization",
            "cost_growth_rate",
            "daily_spend_rate",
            "savings_potential",
            "resource_waste_ratio",
        }
        assert set(result.keys()) == expected_keys
        for key, val in result.items():
            assert isinstance(val, KPIValue), f"{key} should be KPIValue"


# ---------------------------------------------------------------------------
# get_kpi_metrics (async)
# ---------------------------------------------------------------------------

class TestGetKpiMetrics:
    @pytest.mark.asyncio
    @patch("app.services.kpi_service.AWSBudgetsService")
    @patch("app.services.kpi_service.DatabaseCostProcessor")
    async def test_raises_for_unknown_kpi_id(self, MockDBC, MockAWS):
        db = MagicMock()
        svc = KPIService(db)

        with pytest.raises(ValueError, match="Unknown KPI"):
            await svc.get_kpi_metrics("nonexistent_kpi", "prod")

    @pytest.mark.asyncio
    @patch("app.services.kpi_service.AWSBudgetsService")
    @patch("app.services.kpi_service.DatabaseCostProcessor")
    async def test_returns_kpi_metrics_object(self, MockDBC, MockAWS):
        from app.models.kpi import KPIMetrics
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        MockDBC.get_cost_summary.return_value = {"total_cost": 0.0}
        MockAWS.get_budget_forecast.side_effect = Exception("no aws")
        svc = KPIService(db)

        result = await svc.get_kpi_metrics("cost_growth_rate", "prod")

        assert isinstance(result, KPIMetrics)
        assert result.current is not None
