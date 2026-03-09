"""
Unit tests for BudgetNotificationService.

Uses unittest.mock to isolate from DB queries and Teams HTTP calls.
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch, call

from app.services.budget_notification_service import BudgetNotificationService
from app.schemas.budget import BudgetAlertLevel, BudgetPeriod, BudgetStatus


# ---------------------------------------------------------------------------
# Helpers / factories
# ---------------------------------------------------------------------------

def _make_webhook(
    webhook_type: str = "teams",
    is_active: bool = True,
    send_budget_alerts: bool = True,
    budget_threshold_percentage: int = 80,
    name: str = "Test Webhook",
    webhook_url: str = "https://example.com/webhook",
):
    wh = MagicMock()
    wh.webhook_type = webhook_type
    wh.is_active = is_active
    wh.send_budget_alerts = send_budget_alerts
    wh.budget_threshold_percentage = budget_threshold_percentage
    wh.name = name
    wh.webhook_url = webhook_url
    wh.last_sent_at = None
    return wh


def _make_budget_status(
    percentage_used: float = 90.0,
    budget_name: str = "Test Budget",
    budget_amount: float = 1000.0,
    current_spend: float = 900.0,
    projected_spend: float = None,
    alert_level: BudgetAlertLevel = BudgetAlertLevel.WARNING,
) -> BudgetStatus:
    return BudgetStatus(
        budget_id=1,
        budget_name=budget_name,
        budget_amount=budget_amount,
        period=BudgetPeriod.MONTHLY,
        start_date=datetime(2025, 1, 1),
        end_date=None,
        current_spend=current_spend,
        percentage_used=percentage_used,
        remaining=budget_amount - current_spend,
        days_remaining=10,
        alert_level=alert_level,
        threshold_warning=80.0,
        threshold_critical=100.0,
        projected_spend=projected_spend,
    )


def _make_budget_orm(budget_id: int = 1, aws_account_id: int = 1, name: str = "Test Budget", amount: float = 1000.0):
    b = MagicMock()
    b.id = budget_id
    b.aws_account_id = aws_account_id
    b.name = name
    b.amount = amount
    return b


def _make_account(name: str = "prod-account"):
    a = MagicMock()
    a.name = name
    return a


# ---------------------------------------------------------------------------
# check_and_send_budget_alerts
# ---------------------------------------------------------------------------

class TestCheckAndSendBudgetAlerts:
    def test_returns_zeros_when_no_active_webhooks(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []

        result = BudgetNotificationService.check_and_send_budget_alerts(db)

        assert result["webhooks_checked"] == 0
        assert result["budgets_checked"] == 0
        assert result["notifications_sent"] == 0
        assert result["errors"] == []

    @patch("app.services.budget_notification_service.BudgetService")
    @patch("app.services.budget_notification_service.TeamsNotificationService")
    def test_sends_alert_when_threshold_exceeded(self, MockTeams, MockBudgetSvc):
        db = MagicMock()
        webhook = _make_webhook(budget_threshold_percentage=80)
        db.query.return_value.filter.return_value.all.return_value = [webhook]

        budget_orm = _make_budget_orm()
        MockBudgetSvc.list_budgets.return_value = [budget_orm]
        MockBudgetSvc.get_budget_status.return_value = _make_budget_status(percentage_used=90.0)

        account = _make_account()
        db.query.return_value.filter.return_value.first.return_value = account

        MockTeams.create_budget_alert_card.return_value = {"card": "data"}
        MockTeams.send_adaptive_card.return_value = True

        result = BudgetNotificationService.check_and_send_budget_alerts(db)

        assert result["notifications_sent"] == 1
        assert result["errors"] == []

    @patch("app.services.budget_notification_service.BudgetService")
    def test_skips_alert_when_usage_below_threshold(self, MockBudgetSvc):
        db = MagicMock()
        webhook = _make_webhook(budget_threshold_percentage=95)
        db.query.return_value.filter.return_value.all.return_value = [webhook]

        budget_orm = _make_budget_orm()
        MockBudgetSvc.list_budgets.return_value = [budget_orm]
        # 85% usage < 95% threshold → no alert
        MockBudgetSvc.get_budget_status.return_value = _make_budget_status(percentage_used=85.0)

        account = _make_account()
        db.query.return_value.filter.return_value.first.return_value = account

        result = BudgetNotificationService.check_and_send_budget_alerts(db)

        assert result["notifications_sent"] == 0
        assert result["errors"] == []

    @patch("app.services.budget_notification_service.BudgetService")
    @patch("app.services.budget_notification_service.TeamsNotificationService")
    def test_records_error_when_teams_send_fails(self, MockTeams, MockBudgetSvc):
        db = MagicMock()
        webhook = _make_webhook(budget_threshold_percentage=80)
        db.query.return_value.filter.return_value.all.return_value = [webhook]

        budget_orm = _make_budget_orm()
        MockBudgetSvc.list_budgets.return_value = [budget_orm]
        MockBudgetSvc.get_budget_status.return_value = _make_budget_status(percentage_used=90.0)

        account = _make_account()
        db.query.return_value.filter.return_value.first.return_value = account

        MockTeams.create_budget_alert_card.return_value = {"card": "data"}
        MockTeams.send_adaptive_card.return_value = False  # simulated failure

        result = BudgetNotificationService.check_and_send_budget_alerts(db)

        assert result["notifications_sent"] == 0
        assert len(result["errors"]) == 1

    @patch("app.services.budget_notification_service.BudgetService")
    def test_continues_after_exception_on_one_budget(self, MockBudgetSvc):
        db = MagicMock()
        webhook = _make_webhook(budget_threshold_percentage=80)
        db.query.return_value.filter.return_value.all.return_value = [webhook]

        bad_budget = _make_budget_orm(budget_id=99)
        good_budget = _make_budget_orm(budget_id=1)
        MockBudgetSvc.list_budgets.return_value = [bad_budget, good_budget]

        def get_status_side_effect(db, bid):
            if bid == 99:
                raise RuntimeError("simulated DB error")
            return _make_budget_status(percentage_used=70.0)  # below 80% threshold — no send

        MockBudgetSvc.get_budget_status.side_effect = get_status_side_effect

        result = BudgetNotificationService.check_and_send_budget_alerts(db)

        assert len(result["errors"]) == 1
        assert "99" in result["errors"][0]

    @patch("app.services.budget_notification_service.BudgetService")
    def test_skips_budget_with_none_status(self, MockBudgetSvc):
        db = MagicMock()
        webhook = _make_webhook()
        db.query.return_value.filter.return_value.all.return_value = [webhook]

        budget_orm = _make_budget_orm()
        MockBudgetSvc.list_budgets.return_value = [budget_orm]
        MockBudgetSvc.get_budget_status.return_value = None  # budget not found

        result = BudgetNotificationService.check_and_send_budget_alerts(db)

        assert result["notifications_sent"] == 0
        assert result["errors"] == []

    @patch("app.services.budget_notification_service.BudgetService")
    @patch("app.services.budget_notification_service.TeamsNotificationService")
    def test_unknown_account_defaults_to_unknown_string(self, MockTeams, MockBudgetSvc):
        db = MagicMock()
        webhook = _make_webhook(budget_threshold_percentage=80)
        db.query.return_value.filter.return_value.all.return_value = [webhook]

        budget_orm = _make_budget_orm()
        MockBudgetSvc.list_budgets.return_value = [budget_orm]
        MockBudgetSvc.get_budget_status.return_value = _make_budget_status(percentage_used=90.0)
        db.query.return_value.filter.return_value.first.return_value = None  # no account found

        MockTeams.create_budget_alert_card.return_value = {}
        MockTeams.send_adaptive_card.return_value = True

        # Should not raise; account_name should default to "Unknown"
        result = BudgetNotificationService.check_and_send_budget_alerts(db)
        # Verify that the card was created with account_name="Unknown"
        _, kwargs = MockTeams.create_budget_alert_card.call_args
        assert kwargs.get("account_name") == "Unknown"

    @patch("app.services.budget_notification_service.BudgetService")
    def test_budgets_checked_count_matches_budget_list(self, MockBudgetSvc):
        db = MagicMock()
        webhook = _make_webhook(budget_threshold_percentage=80)
        db.query.return_value.filter.return_value.all.return_value = [webhook]

        budgets = [_make_budget_orm(budget_id=i) for i in range(3)]
        MockBudgetSvc.list_budgets.return_value = budgets
        # All below threshold
        MockBudgetSvc.get_budget_status.return_value = _make_budget_status(percentage_used=50.0)

        result = BudgetNotificationService.check_and_send_budget_alerts(db)
        assert result["budgets_checked"] == 3


# ---------------------------------------------------------------------------
# _send_budget_alert (private, tested via check_and_send or directly)
# ---------------------------------------------------------------------------

class TestSendBudgetAlert:
    @patch("app.services.budget_notification_service.TeamsNotificationService")
    def test_sends_teams_adaptive_card_for_teams_webhook(self, MockTeams):
        webhook = _make_webhook(webhook_type="teams")
        MockTeams.create_budget_alert_card.return_value = {"card": "data"}
        MockTeams.send_adaptive_card.return_value = True

        result = BudgetNotificationService._send_budget_alert(
            webhook=webhook,
            budget_name="MyBudget",
            current_spend=800.0,
            budget_amount=1000.0,
            percentage=80.0,
            forecast_spend=900.0,
            account_name="prod",
            alert_level=BudgetAlertLevel.WARNING,
        )
        assert result is True
        MockTeams.send_adaptive_card.assert_called_once()

    @patch("app.services.budget_notification_service.TeamsNotificationService")
    def test_sends_power_automate_format_for_pa_webhook(self, MockTeams):
        webhook = _make_webhook(webhook_type="power_automate")
        MockTeams.convert_to_power_automate_format.return_value = {"pa": "data"}
        MockTeams.send_to_power_automate.return_value = True

        result = BudgetNotificationService._send_budget_alert(
            webhook=webhook,
            budget_name="MyBudget",
            current_spend=800.0,
            budget_amount=1000.0,
            percentage=80.0,
            forecast_spend=900.0,
            account_name="prod",
            alert_level=BudgetAlertLevel.CRITICAL,
        )
        assert result is True
        MockTeams.send_to_power_automate.assert_called_once()

    @patch("app.services.budget_notification_service.TeamsNotificationService")
    def test_returns_false_on_exception(self, MockTeams):
        webhook = _make_webhook(webhook_type="teams")
        MockTeams.create_budget_alert_card.side_effect = Exception("Network error")

        result = BudgetNotificationService._send_budget_alert(
            webhook=webhook,
            budget_name="MyBudget",
            current_spend=800.0,
            budget_amount=1000.0,
            percentage=80.0,
            forecast_spend=900.0,
            account_name="prod",
            alert_level=BudgetAlertLevel.WARNING,
        )
        assert result is False


# ---------------------------------------------------------------------------
# send_immediate_budget_alert
# ---------------------------------------------------------------------------

class TestSendImmediateBudgetAlert:
    @patch("app.services.budget_notification_service.BudgetService")
    def test_returns_error_when_status_not_found(self, MockBudgetSvc):
        db = MagicMock()
        MockBudgetSvc.get_budget_status.return_value = None

        result = BudgetNotificationService.send_immediate_budget_alert(db, budget_id=99)

        assert result["success"] is False
        assert "99" in result["error"]

    @patch("app.services.budget_notification_service.BudgetService")
    def test_returns_error_when_budget_orm_not_found(self, MockBudgetSvc):
        db = MagicMock()
        MockBudgetSvc.get_budget_status.return_value = _make_budget_status()
        MockBudgetSvc.get_budget.return_value = None  # budget ORM missing

        result = BudgetNotificationService.send_immediate_budget_alert(db, budget_id=99)

        assert result["success"] is False

    @patch("app.services.budget_notification_service.BudgetService")
    def test_returns_error_when_no_webhooks_configured(self, MockBudgetSvc):
        db = MagicMock()
        MockBudgetSvc.get_budget_status.return_value = _make_budget_status()
        MockBudgetSvc.get_budget.return_value = _make_budget_orm()
        db.query.return_value.filter.return_value.first.return_value = _make_account()
        db.query.return_value.filter.return_value.all.return_value = []

        result = BudgetNotificationService.send_immediate_budget_alert(db, budget_id=1)

        assert result["success"] is False
        assert "No active webhooks" in result["error"]

    @patch("app.services.budget_notification_service.BudgetService")
    @patch("app.services.budget_notification_service.TeamsNotificationService")
    def test_sends_to_all_webhooks(self, MockTeams, MockBudgetSvc):
        db = MagicMock()
        MockBudgetSvc.get_budget_status.return_value = _make_budget_status()
        MockBudgetSvc.get_budget.return_value = _make_budget_orm()

        webhooks = [_make_webhook(name=f"wh{i}") for i in range(3)]
        account = _make_account()

        # First call to filter().first() returns account, subsequent calls return webhooks
        db.query.return_value.filter.return_value.first.return_value = account
        db.query.return_value.filter.return_value.all.return_value = webhooks

        MockTeams.create_budget_alert_card.return_value = {}
        MockTeams.send_adaptive_card.return_value = True

        result = BudgetNotificationService.send_immediate_budget_alert(db, budget_id=1)

        assert result["success"] is True
        assert result["notifications_sent"] == 3

    @patch("app.services.budget_notification_service.BudgetService")
    @patch("app.services.budget_notification_service.TeamsNotificationService")
    def test_success_false_when_all_sends_fail(self, MockTeams, MockBudgetSvc):
        db = MagicMock()
        MockBudgetSvc.get_budget_status.return_value = _make_budget_status()
        MockBudgetSvc.get_budget.return_value = _make_budget_orm()

        webhook = _make_webhook()
        db.query.return_value.filter.return_value.first.return_value = _make_account()
        db.query.return_value.filter.return_value.all.return_value = [webhook]

        MockTeams.create_budget_alert_card.return_value = {}
        MockTeams.send_adaptive_card.return_value = False

        result = BudgetNotificationService.send_immediate_budget_alert(db, budget_id=1)

        assert result["success"] is False
        assert result["notifications_sent"] == 0
        assert len(result["errors"]) == 1
