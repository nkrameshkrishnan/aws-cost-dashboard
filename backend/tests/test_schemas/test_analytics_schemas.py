"""Tests for analytics, automation, and rightsizing schemas."""
import pytest
from pydantic import ValidationError

from app.schemas.analytics import (
    CostDataPoint, ForecastRequest, AnomalyDetectionRequest,
    ForecastPoint, AnomalyPoint, ForecastResponse, AnomalyResponse,
)
from app.schemas.automation import (
    ScheduleBudgetAlertsRequest, ScheduleAuditRequest,
    JobResponse, JobListResponse, JobStatusResponse,
)
from app.schemas.rightsizing import (
    RightSizingRecommendation, RightSizingRecommendationsResponse, RightSizingSummary,
)


# ---------------------------------------------------------------------------
# Analytics schemas
# ---------------------------------------------------------------------------

class TestCostDataPoint:
    def test_valid(self):
        dp = CostDataPoint(date="2024-01-01", cost=10.5)
        assert dp.date == "2024-01-01"
        assert dp.cost == 10.5

    def test_cost_cannot_be_negative(self):
        with pytest.raises(ValidationError):
            CostDataPoint(date="2024-01-01", cost=-1.0)

    def test_zero_cost_allowed(self):
        dp = CostDataPoint(date="2024-01-01", cost=0.0)
        assert dp.cost == 0.0


class TestForecastRequest:
    def _data_points(self, n=3):
        return [CostDataPoint(date=f"2024-01-{i:02d}", cost=float(i * 10)) for i in range(1, n + 1)]

    def test_valid_defaults(self):
        req = ForecastRequest(historical_data=self._data_points(5))
        assert req.days_ahead == 30
        assert req.method == "ensemble"

    def test_requires_at_least_2_points(self):
        with pytest.raises(ValidationError):
            ForecastRequest(historical_data=self._data_points(1))

    def test_days_ahead_bounds(self):
        with pytest.raises(ValidationError):
            ForecastRequest(historical_data=self._data_points(3), days_ahead=0)
        with pytest.raises(ValidationError):
            ForecastRequest(historical_data=self._data_points(3), days_ahead=366)

    def test_all_methods(self):
        for method in ("linear", "moving_average", "exponential_smoothing", "ensemble"):
            req = ForecastRequest(historical_data=self._data_points(3), method=method)
            assert req.method == method

    def test_invalid_method(self):
        with pytest.raises(ValidationError):
            ForecastRequest(historical_data=self._data_points(3), method="magic")


class TestAnomalyDetectionRequest:
    def _data_points(self, n=5):
        return [CostDataPoint(date=f"2024-01-{i:02d}", cost=float(i * 10)) for i in range(1, n + 1)]

    def test_valid_defaults(self):
        req = AnomalyDetectionRequest(historical_data=self._data_points(5))
        assert req.method == "all"
        assert req.threshold == 3.0

    def test_requires_at_least_3_points(self):
        with pytest.raises(ValidationError):
            AnomalyDetectionRequest(historical_data=self._data_points(2))

    def test_threshold_must_be_positive(self):
        with pytest.raises(ValidationError):
            AnomalyDetectionRequest(historical_data=self._data_points(5), threshold=0.0)

    def test_all_methods(self):
        for method in ("z_score", "iqr", "spike", "drift", "all"):
            req = AnomalyDetectionRequest(historical_data=self._data_points(5), method=method)
            assert req.method == method


class TestForecastPoint:
    def test_valid(self):
        fp = ForecastPoint(
            date="2024-02-01",
            predicted_cost=100.0,
            lower_bound=80.0,
            upper_bound=120.0,
        )
        assert fp.predicted_cost == 100.0


class TestAnomalyPoint:
    def test_valid(self):
        ap = AnomalyPoint(
            date="2024-01-15",
            cost=500.0,
            anomaly_type="spike",
            severity="high",
            description="Unusual cost spike detected",
        )
        assert ap.severity == "high"


class TestForecastResponse:
    def test_valid(self):
        resp = ForecastResponse(
            account_name="prod",
            forecast_method="ensemble",
            forecast_period_days=30,
            predictions=[],
            total_forecasted_cost=1500.0,
            generated_at="2024-01-01T00:00:00Z",
        )
        assert resp.confidence_level == "95%"


class TestAnomalyResponse:
    def test_valid(self):
        resp = AnomalyResponse(anomalies=[], method="all", total_anomalies=0)
        assert resp.summary is None

    def test_with_summary(self):
        resp = AnomalyResponse(
            anomalies=[],
            method="z_score",
            total_anomalies=2,
            summary={"critical": 1, "high": 1},
        )
        assert resp.summary["critical"] == 1


# ---------------------------------------------------------------------------
# Automation schemas
# ---------------------------------------------------------------------------

class TestScheduleBudgetAlertsRequest:
    def test_defaults(self):
        req = ScheduleBudgetAlertsRequest()
        assert req.job_id == "budget-alerts-default"
        assert req.enabled is True

    def test_custom_values(self):
        req = ScheduleBudgetAlertsRequest(
            job_id="my-job",
            cron_expression="0 8 * * *",
            enabled=False,
        )
        assert req.job_id == "my-job"
        assert req.enabled is False


class TestScheduleAuditRequest:
    def test_required_fields(self):
        with pytest.raises(ValidationError):
            ScheduleAuditRequest()  # missing job_id and account_name

    def test_valid(self):
        req = ScheduleAuditRequest(job_id="audit-1", account_name="prod")
        assert req.cron_expression == "0 2 * * *"
        assert req.send_teams_notification is True
        assert req.audit_types is None

    def test_with_audit_types(self):
        req = ScheduleAuditRequest(
            job_id="audit-1",
            account_name="prod",
            audit_types=["ec2", "rds"],
        )
        assert req.audit_types == ["ec2", "rds"]


class TestJobResponse:
    def test_valid(self):
        jr = JobResponse(job_id="job-1", name="My Job", enabled=True)
        assert jr.next_run_time is None
        assert jr.enabled is True


class TestJobListResponse:
    def test_valid(self):
        jobs = [JobResponse(job_id="j1", name="Job 1", enabled=True)]
        resp = JobListResponse(jobs=jobs, total=1)
        assert resp.total == 1


class TestJobStatusResponse:
    def test_valid(self):
        resp = JobStatusResponse(job_id="j1", status="running", progress=50)
        assert resp.current_step is None
        assert resp.error is None

    def test_completed_status(self):
        resp = JobStatusResponse(
            job_id="j1",
            status="completed",
            progress=100,
            completed_at="2024-01-01T12:00:00Z",
            result={"count": 5},
        )
        assert resp.result["count"] == 5


# ---------------------------------------------------------------------------
# Rightsizing schemas
# ---------------------------------------------------------------------------

class TestRightSizingRecommendation:
    def _base(self, **kwargs):
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

    def test_valid(self):
        rec = self._base()
        assert rec.recommendation_source == "aws_compute_optimizer"
        assert rec.region is None

    def test_with_optional_fields(self):
        rec = self._base(
            region="us-east-1",
            cpu_utilization=15.5,
            memory_utilization=20.0,
            performance_risk=1.5,
            savings_percentage=30.0,
        )
        assert rec.cpu_utilization == 15.5


class TestRightSizingRecommendationsResponse:
    def test_empty(self):
        resp = RightSizingRecommendationsResponse(
            profile_name="prod",
            total_recommendations=0,
            total_monthly_savings=0.0,
            recommendations_by_type={},
            recommendations=[],
        )
        assert resp.total_recommendations == 0


class TestRightSizingSummary:
    def test_valid(self):
        s = RightSizingSummary(
            profile_name="prod",
            total_ec2_recommendations=3,
            total_ebs_recommendations=1,
            total_lambda_recommendations=0,
            total_asg_recommendations=0,
            total_potential_savings=150.0,
            overprovisioned_resources=3,
            underprovisioned_resources=1,
            optimized_resources=5,
        )
        assert s.total_potential_savings == 150.0
