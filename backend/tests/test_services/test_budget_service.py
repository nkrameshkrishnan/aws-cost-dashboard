"""
Unit tests for BudgetService.

Uses a module-scoped in-memory SQLite DB so all tests share one engine.
The AWSAccount row is created once per module; budgets are created and
discarded per-test (each test uses a fresh session that rolls back uncommitted
work, but for simplicity we rely on unique budget names rather than rollback
since BudgetService.create_budget always commits).
"""
import pytest
import uuid
from datetime import datetime
from unittest.mock import patch
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.aws_account import AWSAccount
from app.models.budget import Budget
from app.database.base import Base
from app.schemas.budget import (
    BudgetCreate,
    BudgetUpdate,
    BudgetPeriod,
    BudgetAlertLevel,
)
from app.services.budget_service import BudgetService


# ---------------------------------------------------------------------------
# Module-level fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine():
    """Single in-memory SQLite engine shared across this module."""
    # Ensure all models are registered before create_all
    from app.models.teams_webhook import TeamsWebhook      # noqa: F401
    from app.models.business_metric import BusinessMetric  # noqa: F401
    from app.models.async_job import AsyncJob              # noqa: F401
    from app.models.kpi import KPIThreshold               # noqa: F401

    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture(scope="module")
def account_id(engine):
    """Create a single AWSAccount for the whole module; return its DB id."""
    Session = sessionmaker(bind=engine)
    session = Session()
    acc = AWSAccount(
        name="test-account-budgetsvc",
        encrypted_access_key_id="enc-key-id",
        encrypted_secret_access_key="enc-secret",
        account_id="123456789012",
    )
    session.add(acc)
    session.commit()
    aid = acc.id
    session.close()
    return aid


@pytest.fixture
def db(engine):
    """Function-scoped session; rolls back at end of each test."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unique_name(prefix: str = "Budget") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _create_budget_data(account_id: int, **kwargs) -> BudgetCreate:
    defaults = dict(
        name=_unique_name(),
        aws_account_id=account_id,
        amount=1000.0,
        period=BudgetPeriod.MONTHLY,
        start_date=datetime(2025, 1, 1),
        threshold_warning=80.0,
        threshold_critical=100.0,
    )
    defaults.update(kwargs)
    return BudgetCreate(**defaults)


def _make_budget(db, account_id: int, **kwargs) -> Budget:
    data = _create_budget_data(account_id, **kwargs)
    return BudgetService.create_budget(db, data)


# ---------------------------------------------------------------------------
# _calculate_alert_level  (pure function, no DB needed)
# ---------------------------------------------------------------------------

class TestCalculateAlertLevel:
    def test_normal_when_below_warning(self):
        result = BudgetService._calculate_alert_level(50.0, 80.0, 100.0)
        assert result == BudgetAlertLevel.NORMAL

    def test_warning_at_exact_threshold(self):
        result = BudgetService._calculate_alert_level(80.0, 80.0, 100.0)
        assert result == BudgetAlertLevel.WARNING

    def test_critical_at_exact_critical_threshold(self):
        # At exactly 100% the function returns EXCEEDED (>= 100 check comes first)
        result = BudgetService._calculate_alert_level(100.0, 80.0, 100.0)
        assert result == BudgetAlertLevel.EXCEEDED

    def test_critical_just_below_100(self):
        # 99% >= 90% critical threshold but < 100% → CRITICAL
        result = BudgetService._calculate_alert_level(99.0, 80.0, 90.0)
        assert result == BudgetAlertLevel.CRITICAL

    def test_exceeded_above_100(self):
        result = BudgetService._calculate_alert_level(105.0, 80.0, 100.0)
        assert result == BudgetAlertLevel.EXCEEDED

    def test_warning_between_warning_and_critical(self):
        result = BudgetService._calculate_alert_level(90.0, 80.0, 100.0)
        assert result == BudgetAlertLevel.WARNING

    def test_critical_between_critical_and_100(self):
        # 95% > 90% critical threshold but < 100%
        result = BudgetService._calculate_alert_level(95.0, 80.0, 90.0)
        assert result == BudgetAlertLevel.CRITICAL

    def test_zero_usage_is_normal(self):
        result = BudgetService._calculate_alert_level(0.0, 80.0, 100.0)
        assert result == BudgetAlertLevel.NORMAL


# ---------------------------------------------------------------------------
# create_budget
# ---------------------------------------------------------------------------

class TestCreateBudget:
    def test_creates_budget_with_valid_account(self, db, account_id):
        budget = _make_budget(db, account_id)
        assert budget.id is not None
        assert budget.amount == 1000.0
        assert budget.aws_account_id == account_id
        assert budget.is_active is True

    def test_raises_when_account_not_found(self, db):
        data = _create_budget_data(99999)
        with pytest.raises(ValueError, match="99999"):
            BudgetService.create_budget(db, data)

    def test_budget_thresholds_stored(self, db, account_id):
        data = _create_budget_data(account_id, threshold_warning=75.0, threshold_critical=95.0)
        budget = BudgetService.create_budget(db, data)
        assert budget.threshold_warning == 75.0
        assert budget.threshold_critical == 95.0

    def test_budget_period_stored_correctly(self, db, account_id):
        data = _create_budget_data(account_id, period=BudgetPeriod.QUARTERLY)
        budget = BudgetService.create_budget(db, data)
        assert budget.period == BudgetPeriod.QUARTERLY


# ---------------------------------------------------------------------------
# get_budget
# ---------------------------------------------------------------------------

class TestGetBudget:
    def test_returns_budget_by_id(self, db, account_id):
        created = _make_budget(db, account_id)
        found = BudgetService.get_budget(db, created.id)
        assert found is not None
        assert found.id == created.id

    def test_returns_none_for_missing_id(self, db):
        assert BudgetService.get_budget(db, 99999) is None


# ---------------------------------------------------------------------------
# list_budgets
# ---------------------------------------------------------------------------

class TestListBudgets:
    def test_lists_active_budgets_by_default(self, db, account_id):
        b1 = _make_budget(db, account_id)
        b2 = _make_budget(db, account_id)

        ids = [b.id for b in BudgetService.list_budgets(db)]
        assert b1.id in ids
        assert b2.id in ids

    def test_filters_by_account_id(self, db, account_id):
        _make_budget(db, account_id)
        budgets = BudgetService.list_budgets(db, aws_account_id=account_id)
        assert all(b.aws_account_id == account_id for b in budgets)

    def test_filters_by_nonexistent_account_returns_empty(self, db):
        assert BudgetService.list_budgets(db, aws_account_id=99999) == []

    def test_active_only_false_includes_inactive(self, db, account_id):
        data = _create_budget_data(account_id, is_active=False)
        budget = BudgetService.create_budget(db, data)

        all_budgets = BudgetService.list_budgets(db, active_only=False)
        inactive_ids = [b.id for b in all_budgets if not b.is_active]
        assert budget.id in inactive_ids


# ---------------------------------------------------------------------------
# update_budget
# ---------------------------------------------------------------------------

class TestUpdateBudget:
    def test_updates_amount(self, db, account_id):
        budget = _make_budget(db, account_id)
        updated = BudgetService.update_budget(db, budget.id, BudgetUpdate(amount=2000.0))
        assert updated is not None
        assert updated.amount == 2000.0

    def test_returns_none_for_missing_budget(self, db):
        assert BudgetService.update_budget(db, 99999, BudgetUpdate(amount=500.0)) is None

    def test_updates_threshold(self, db, account_id):
        budget = _make_budget(db, account_id)
        updated = BudgetService.update_budget(db, budget.id, BudgetUpdate(threshold_warning=75.0))
        assert updated.threshold_warning == 75.0

    def test_deactivates_budget(self, db, account_id):
        budget = _make_budget(db, account_id)
        updated = BudgetService.update_budget(db, budget.id, BudgetUpdate(is_active=False))
        assert updated.is_active is False

    def test_unset_fields_not_changed(self, db, account_id):
        budget = _make_budget(db, account_id)
        original_amount = budget.amount
        updated = BudgetService.update_budget(db, budget.id, BudgetUpdate(threshold_warning=70.0))
        assert updated.amount == original_amount


# ---------------------------------------------------------------------------
# delete_budget
# ---------------------------------------------------------------------------

class TestDeleteBudget:
    def test_deletes_existing_budget(self, db, account_id):
        budget = _make_budget(db, account_id)
        bid = budget.id
        success = BudgetService.delete_budget(db, bid)
        assert success is True
        assert BudgetService.get_budget(db, bid) is None

    def test_returns_false_for_missing_budget(self, db):
        assert BudgetService.delete_budget(db, 99999) is False


# ---------------------------------------------------------------------------
# get_budget_status
# ---------------------------------------------------------------------------

class TestGetBudgetStatus:
    def test_returns_none_for_missing_budget(self, db):
        assert BudgetService.get_budget_status(db, 99999) is None

    @patch("app.services.budget_service.DatabaseCostProcessor")
    @patch("app.services.budget_service.AWSBudgetsService")
    def test_normal_alert_below_threshold(self, MockAWSBudgets, MockCostProc, db, account_id):
        budget = _make_budget(db, account_id)
        MockCostProc.get_cost_summary.return_value = {"total_cost": 500.0}
        MockAWSBudgets.get_budget_forecast.return_value = {"forecasted_spend": 800.0}

        status = BudgetService.get_budget_status(db, budget.id)
        assert status is not None
        assert status.current_spend == 500.0
        assert status.percentage_used == 50.0
        assert status.alert_level == BudgetAlertLevel.NORMAL

    @patch("app.services.budget_service.DatabaseCostProcessor")
    @patch("app.services.budget_service.AWSBudgetsService")
    def test_warning_alert_at_threshold(self, MockAWSBudgets, MockCostProc, db, account_id):
        budget = _make_budget(db, account_id)
        MockCostProc.get_cost_summary.return_value = {"total_cost": 850.0}  # 85%
        MockAWSBudgets.get_budget_forecast.return_value = {"forecasted_spend": 950.0}

        status = BudgetService.get_budget_status(db, budget.id)
        assert status.alert_level == BudgetAlertLevel.WARNING

    @patch("app.services.budget_service.DatabaseCostProcessor")
    @patch("app.services.budget_service.AWSBudgetsService")
    def test_cost_error_defaults_to_zero(self, MockAWSBudgets, MockCostProc, db, account_id):
        budget = _make_budget(db, account_id)
        MockCostProc.get_cost_summary.side_effect = RuntimeError("DB error")
        MockAWSBudgets.get_budget_forecast.return_value = {"forecasted_spend": 0.0}

        status = BudgetService.get_budget_status(db, budget.id)
        assert status.current_spend == 0.0

    @patch("app.services.budget_service.DatabaseCostProcessor")
    @patch("app.services.budget_service.AWSBudgetsService")
    def test_forecast_exception_falls_back_to_linear(self, MockAWSBudgets, MockCostProc, db, account_id):
        budget = _make_budget(db, account_id)
        MockCostProc.get_cost_summary.return_value = {"total_cost": 300.0}
        MockAWSBudgets.get_budget_forecast.side_effect = RuntimeError("AWS error")

        status = BudgetService.get_budget_status(db, budget.id)
        assert status is not None  # Should not raise

    @patch("app.services.budget_service.DatabaseCostProcessor")
    @patch("app.services.budget_service.AWSBudgetsService")
    def test_quarterly_period(self, MockAWSBudgets, MockCostProc, db, account_id):
        data = _create_budget_data(account_id, period=BudgetPeriod.QUARTERLY)
        budget = BudgetService.create_budget(db, data)
        MockCostProc.get_cost_summary.return_value = {"total_cost": 200.0}
        MockAWSBudgets.get_budget_forecast.return_value = {"forecasted_spend": 600.0}

        status = BudgetService.get_budget_status(db, budget.id)
        assert status.budget_id == budget.id

    @patch("app.services.budget_service.DatabaseCostProcessor")
    @patch("app.services.budget_service.AWSBudgetsService")
    def test_yearly_period(self, MockAWSBudgets, MockCostProc, db, account_id):
        data = _create_budget_data(account_id, period=BudgetPeriod.YEARLY)
        budget = BudgetService.create_budget(db, data)
        MockCostProc.get_cost_summary.return_value = {"total_cost": 5000.0}
        MockAWSBudgets.get_budget_forecast.return_value = {"forecasted_spend": 10000.0}

        status = BudgetService.get_budget_status(db, budget.id)
        assert status is not None

    @patch("app.services.budget_service.DatabaseCostProcessor")
    @patch("app.services.budget_service.AWSBudgetsService")
    def test_remaining_is_capped_at_zero(self, MockAWSBudgets, MockCostProc, db, account_id):
        budget = _make_budget(db, account_id)
        MockCostProc.get_cost_summary.return_value = {"total_cost": 1200.0}  # over budget
        MockAWSBudgets.get_budget_forecast.return_value = {"forecasted_spend": 1200.0}

        status = BudgetService.get_budget_status(db, budget.id)
        assert status.remaining == 0.0  # max(0, ...)
        assert status.alert_level == BudgetAlertLevel.EXCEEDED
