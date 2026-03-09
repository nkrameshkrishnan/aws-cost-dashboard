"""Tests for remaining schemas: unit_cost, teams, cost, export, aws_account."""
import pytest
from datetime import datetime
from pydantic import ValidationError

from app.schemas.unit_cost import (
    BusinessMetricCreate, BusinessMetricResponse,
    UnitCostResponse, UnitCostTrendResponse,
)
from app.schemas.teams import (
    TeamsWebhookBase, TeamsWebhookCreate, TeamsWebhookUpdate, TeamsWebhookResponse,
)
from app.schemas.aws_account import (
    AWSAccountCreate, AWSAccountUpdate, AWSAccountResponse,
)


# ---------------------------------------------------------------------------
# unit_cost schemas
# ---------------------------------------------------------------------------

class TestBusinessMetricCreate:
    def test_minimal(self):
        bm = BusinessMetricCreate(profile_name="prod", metric_date="2024-01-01")
        assert bm.active_users is None

    def test_full(self):
        bm = BusinessMetricCreate(
            profile_name="prod",
            metric_date="2024-01-01",
            active_users=500,
            total_transactions=10000,
            api_calls=50000,
            data_processed_gb=100.5,
            custom_metric_1=99.9,
            custom_metric_1_name="requests",
        )
        assert bm.active_users == 500

    def test_negative_active_users_rejected(self):
        with pytest.raises(ValidationError):
            BusinessMetricCreate(profile_name="prod", metric_date="2024-01-01", active_users=-1)

    def test_negative_transactions_rejected(self):
        with pytest.raises(ValidationError):
            BusinessMetricCreate(profile_name="prod", metric_date="2024-01-01", total_transactions=-5)


class TestBusinessMetricResponse:
    def test_valid(self):
        now = datetime.now()
        bm = BusinessMetricResponse(
            id=1,
            profile_name="prod",
            metric_date="2024-01-01",
            active_users=100,
            total_transactions=None,
            api_calls=None,
            data_processed_gb=None,
            custom_metric_1=None,
            custom_metric_1_name=None,
            created_at=now,
            updated_at=now,
        )
        assert bm.id == 1


class TestUnitCostResponse:
    def test_minimal(self):
        resp = UnitCostResponse(
            profile_name="prod",
            start_date="2024-01-01",
            end_date="2024-01-31",
            total_cost=1000.0,
        )
        assert resp.cost_per_user is None
        assert resp.trend is None

    def test_full(self):
        resp = UnitCostResponse(
            profile_name="prod",
            start_date="2024-01-01",
            end_date="2024-01-31",
            total_cost=5000.0,
            cost_per_user=0.10,
            cost_per_transaction=0.05,
            total_users=50000,
            trend="improving",
            mom_change_percent=-5.0,
        )
        assert resp.trend == "improving"


class TestUnitCostTrendResponse:
    def test_valid(self):
        resp = UnitCostTrendResponse(
            profile_name="prod",
            metric_type="cost_per_user",
            trend_data=[
                {"date": "2024-01-01", "unit_cost": 0.10, "total_cost": 1000.0, "metric_value": 10000},
            ],
        )
        assert len(resp.trend_data) == 1


# ---------------------------------------------------------------------------
# teams schemas
# ---------------------------------------------------------------------------

class TestTeamsWebhookSchemas:
    def test_create_minimal(self):
        wh = TeamsWebhookCreate(
            name="My Webhook",
            webhook_url="https://example.com/webhook",
        )
        assert wh.is_active is True

    def test_update_partial(self):
        upd = TeamsWebhookUpdate(name="Updated Name")
        assert upd.name == "Updated Name"

    def test_response_schema(self):
        now = datetime.now()
        resp = TeamsWebhookResponse(
            id=1,
            name="My Webhook",
            webhook_url="https://example.com/webhook",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        assert resp.id == 1


# ---------------------------------------------------------------------------
# aws_account schemas
# ---------------------------------------------------------------------------

class TestAWSAccountSchemas:
    def test_create_requires_credentials(self):
        acc = AWSAccountCreate(
            name="prod",
            access_key_id="AKIAIOSFODNN7EXAMPLE",
            secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYzEXAMPLEKEY",
            region="us-east-1",
        )
        assert acc.region == "us-east-1"

    def test_create_missing_key_raises(self):
        with pytest.raises(ValidationError):
            AWSAccountCreate(
                name="prod",
                # missing access_key_id and secret_access_key
                region="us-east-1",
            )

    def test_update_partial(self):
        upd = AWSAccountUpdate(name="staging")
        assert upd.name == "staging"

    def test_response_schema(self):
        now = datetime.now()
        resp = AWSAccountResponse(
            id=1,
            name="prod",
            account_id="123456789012",
            region="us-east-1",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        assert resp.id == 1
