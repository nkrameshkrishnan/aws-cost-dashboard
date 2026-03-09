"""
Unit tests for RightSizingService.
"""
import pytest
from unittest.mock import MagicMock, patch

from app.services.rightsizing_service import RightSizingService
from app.schemas.rightsizing import (
    RightSizingRecommendation,
    RightSizingRecommendationsResponse,
    RightSizingSummary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_recommendation(**kwargs):
    defaults = dict(
        resource_arn="arn:aws:ec2:us-east-1:123:instance/i-abc",
        resource_name="i-abc",
        resource_type="ec2_instance",
        current_config="t3.large",
        recommended_config="t3.medium",
        finding="Overprovisioned",
        estimated_monthly_savings=25.0,
    )
    defaults.update(kwargs)
    return RightSizingRecommendation(**defaults)


def _make_service(mock_optimizer_recs=None, raise_exc=None):
    """Return a RightSizingService with mocked AWSSessionManager and ComputeOptimizer."""
    mock_session_manager = MagicMock()
    mock_session = MagicMock()
    mock_session_manager.get_session.return_value = mock_session

    if mock_optimizer_recs is None:
        mock_optimizer_recs = {
            "ec2_instances": [],
            "ebs_volumes": [],
            "lambda_functions": [],
            "auto_scaling_groups": [],
        }

    with patch("app.services.rightsizing_service.ComputeOptimizerClient") as MockOptimizer:
        mock_optimizer = MagicMock()
        if raise_exc:
            mock_optimizer.get_all_recommendations.side_effect = raise_exc
        else:
            mock_optimizer.get_all_recommendations.return_value = mock_optimizer_recs
        MockOptimizer.return_value = mock_optimizer

        svc = RightSizingService(session_manager=mock_session_manager)
        return svc, MockOptimizer, mock_optimizer


# ---------------------------------------------------------------------------
# get_recommendations
# ---------------------------------------------------------------------------

class TestGetRecommendations:
    def test_empty_recommendations(self):
        svc, _, _ = _make_service()
        resp = svc.get_recommendations("prod")
        assert resp.total_recommendations == 0
        assert resp.total_monthly_savings == 0.0
        assert resp.recommendations == []

    def test_with_ec2_recommendations(self):
        recs = {
            "ec2_instances": [
                {
                    "resource_arn": "arn:aws:ec2:us-east-1:123:instance/i-1",
                    "resource_name": "i-1",
                    "resource_type": "ec2_instance",
                    "current_config": "t3.large",
                    "recommended_config": "t3.medium",
                    "finding": "Overprovisioned",
                    "estimated_monthly_savings": 20.0,
                }
            ],
            "ebs_volumes": [],
            "lambda_functions": [],
            "auto_scaling_groups": [],
        }
        svc, _, _ = _make_service(mock_optimizer_recs=recs)
        resp = svc.get_recommendations("prod")
        assert resp.total_recommendations == 1
        assert resp.total_monthly_savings == 20.0
        assert "ec2_instance" in resp.recommendations_by_type

    def test_filters_by_resource_type(self):
        recs = {
            "ec2_instances": [
                {
                    "resource_arn": "arn:aws:ec2:us-east-1:123:instance/i-1",
                    "resource_name": "i-1",
                    "resource_type": "ec2_instance",
                    "current_config": "t3.large",
                    "recommended_config": "t3.medium",
                    "finding": "Overprovisioned",
                    "estimated_monthly_savings": 20.0,
                }
            ],
            "ebs_volumes": [
                {
                    "resource_arn": "arn:aws:ec2:us-east-1:123:volume/vol-1",
                    "resource_name": "vol-1",
                    "resource_type": "ebs_volume",
                    "current_config": "gp2 100GB",
                    "recommended_config": "gp3 100GB",
                    "finding": "Overprovisioned",
                    "estimated_monthly_savings": 5.0,
                }
            ],
            "lambda_functions": [],
            "auto_scaling_groups": [],
        }
        svc, _, _ = _make_service(mock_optimizer_recs=recs)
        resp = svc.get_recommendations("prod", resource_types=["ec2_instance"])
        assert resp.total_recommendations == 1
        assert resp.recommendations[0].resource_type == "ec2_instance"

    def test_error_returns_empty_response(self):
        svc, _, _ = _make_service(raise_exc=Exception("AWS error"))
        resp = svc.get_recommendations("prod")
        assert resp.total_recommendations == 0
        assert resp.profile_name == "prod"


# ---------------------------------------------------------------------------
# get_summary
# ---------------------------------------------------------------------------

class TestGetSummary:
    def test_empty_summary(self):
        svc, _, _ = _make_service()
        summary = svc.get_summary("prod")
        assert isinstance(summary, RightSizingSummary)
        assert summary.total_ec2_recommendations == 0

    def test_summary_counts(self):
        recs = {
            "ec2_instances": [
                {
                    "resource_arn": "arn:aws:ec2:us-east-1:123:instance/i-1",
                    "resource_name": "i-1",
                    "resource_type": "ec2_instance",
                    "current_config": "t3.large",
                    "recommended_config": "t3.medium",
                    "finding": "Overprovisioned",
                    "estimated_monthly_savings": 30.0,
                }
            ],
            "ebs_volumes": [],
            "lambda_functions": [],
            "auto_scaling_groups": [],
        }
        svc, _, _ = _make_service(mock_optimizer_recs=recs)
        summary = svc.get_summary("prod")
        assert summary.total_ec2_recommendations == 1
        assert summary.total_potential_savings == 30.0
        assert summary.overprovisioned_resources == 1


# ---------------------------------------------------------------------------
# get_top_savings_opportunities
# ---------------------------------------------------------------------------

class TestGetTopSavingsOpportunities:
    def test_returns_top_by_savings(self):
        recs = {
            "ec2_instances": [
                {
                    "resource_arn": f"arn:aws:ec2:us-east-1:123:instance/i-{i}",
                    "resource_name": f"i-{i}",
                    "resource_type": "ec2_instance",
                    "current_config": "t3.large",
                    "recommended_config": "t3.medium",
                    "finding": "Overprovisioned",
                    "estimated_monthly_savings": float(i * 10),
                }
                for i in range(1, 6)  # 5 recs with $10, $20, $30, $40, $50 savings
            ],
            "ebs_volumes": [],
            "lambda_functions": [],
            "auto_scaling_groups": [],
        }
        svc, _, _ = _make_service(mock_optimizer_recs=recs)
        top = svc.get_top_savings_opportunities("prod", limit=3)
        assert len(top) == 3
        # Should be sorted descending
        assert top[0].estimated_monthly_savings >= top[1].estimated_monthly_savings

    def test_empty_list_on_error(self):
        svc, _, _ = _make_service(raise_exc=Exception("fail"))
        top = svc.get_top_savings_opportunities("prod")
        assert top == []
