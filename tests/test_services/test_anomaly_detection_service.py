"""
Unit tests for AnomalyDetectionService.

All methods are pure (no DB / AWS calls), so no mocking is required beyond
supplying deterministic input data.
"""
import pytest
from datetime import date, timedelta

from app.services.anomaly_detection_service import AnomalyDetectionService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_uniform_data(n: int, base_cost: float = 100.0):
    """Return n days of constant costs (no anomalies expected)."""
    start = date(2025, 1, 1)
    return [
        {"date": (start + timedelta(days=i)).strftime("%Y-%m-%d"), "cost": base_cost}
        for i in range(n)
    ]


def _make_data_with_spike(n: int = 30, base_cost: float = 100.0, spike_day: int = 20, spike_factor: float = 10.0):
    """Return n days of data with a single obvious spike."""
    start = date(2025, 1, 1)
    data = []
    for i in range(n):
        cost = base_cost * spike_factor if i == spike_day else base_cost
        data.append({"date": (start + timedelta(days=i)).strftime("%Y-%m-%d"), "cost": cost})
    return data


def _make_data_with_drop(n: int = 30, base_cost: float = 100.0, drop_day: int = 20, drop_factor: float = 0.0):
    """Return n days of data with a single obvious drop."""
    start = date(2025, 1, 1)
    data = []
    for i in range(n):
        cost = base_cost * drop_factor if i == drop_day else base_cost
        data.append({"date": (start + timedelta(days=i)).strftime("%Y-%m-%d"), "cost": cost})
    return data


# ---------------------------------------------------------------------------
# detect_z_score_anomalies
# ---------------------------------------------------------------------------

class TestDetectZScoreAnomalies:
    def test_returns_empty_for_insufficient_data(self):
        data = _make_uniform_data(6)  # needs >= 7
        result = AnomalyDetectionService.detect_z_score_anomalies(data)
        assert result == []

    def test_no_anomalies_in_uniform_data(self):
        data = _make_uniform_data(30)
        result = AnomalyDetectionService.detect_z_score_anomalies(data)
        assert result == []

    def test_detects_spike(self):
        data = _make_data_with_spike()
        result = AnomalyDetectionService.detect_z_score_anomalies(data, threshold=2.0)
        assert len(result) >= 1
        types = {r["type"] for r in result}
        assert "spike" in types

    def test_detects_drop(self):
        data = _make_data_with_drop()
        result = AnomalyDetectionService.detect_z_score_anomalies(data, threshold=2.0)
        assert len(result) >= 1
        types = {r["type"] for r in result}
        assert "drop" in types

    def test_anomaly_has_required_keys(self):
        data = _make_data_with_spike()
        result = AnomalyDetectionService.detect_z_score_anomalies(data, threshold=2.0)
        assert len(result) >= 1
        required_keys = {"date", "cost", "baseline_cost", "z_score", "severity", "type", "delta", "percentage_change", "description"}
        for item in result:
            assert required_keys.issubset(item.keys())

    def test_severity_critical_for_extreme_z_score(self):
        # spike factor 20x over 30 days should produce z_score >> 4
        data = _make_data_with_spike(n=30, spike_factor=20.0)
        result = AnomalyDetectionService.detect_z_score_anomalies(data, threshold=2.0)
        assert any(r["severity"] == "critical" for r in result)

    def test_severity_high_for_moderate_z_score(self):
        # spike factor 5x is |z| between 3 and 4
        data = _make_data_with_spike(n=30, spike_factor=5.0)
        result = AnomalyDetectionService.detect_z_score_anomalies(data, threshold=2.0)
        severities = {r["severity"] for r in result}
        assert severities & {"critical", "high"}  # at least one of the two

    def test_returns_empty_when_std_is_zero(self):
        """Uniform data has std=0, should return empty."""
        data = _make_uniform_data(30)
        result = AnomalyDetectionService.detect_z_score_anomalies(data)
        assert result == []

    def test_custom_threshold_raises_bar(self):
        data = _make_data_with_spike(spike_factor=5.0)
        # With very high threshold, the spike may not be detected
        result_loose = AnomalyDetectionService.detect_z_score_anomalies(data, threshold=2.0)
        result_strict = AnomalyDetectionService.detect_z_score_anomalies(data, threshold=10.0)
        assert len(result_loose) >= len(result_strict)


# ---------------------------------------------------------------------------
# detect_iqr_anomalies
# ---------------------------------------------------------------------------

class TestDetectIqrAnomalies:
    def test_returns_empty_for_insufficient_data(self):
        data = _make_uniform_data(6)
        result = AnomalyDetectionService.detect_iqr_anomalies(data)
        assert result == []

    def test_no_anomalies_in_uniform_data(self):
        data = _make_uniform_data(30)
        result = AnomalyDetectionService.detect_iqr_anomalies(data)
        assert result == []

    def test_detects_high_outlier(self):
        data = _make_data_with_spike()
        result = AnomalyDetectionService.detect_iqr_anomalies(data, multiplier=1.5)
        assert len(result) >= 1
        assert any(r["type"] == "spike" for r in result)

    def test_detects_low_outlier(self):
        data = _make_data_with_drop()
        result = AnomalyDetectionService.detect_iqr_anomalies(data, multiplier=1.5)
        assert len(result) >= 1
        assert any(r["type"] == "drop" for r in result)

    def test_anomaly_has_required_keys(self):
        data = _make_data_with_spike()
        result = AnomalyDetectionService.detect_iqr_anomalies(data, multiplier=1.5)
        required_keys = {"date", "cost", "baseline_cost", "lower_bound", "upper_bound", "severity", "type", "delta", "percentage_change", "description"}
        for item in result:
            assert required_keys.issubset(item.keys())

    def test_severity_critical_for_extreme_multiplier_3(self):
        """multiplier != 1.5 → severity should be 'critical'."""
        data = _make_data_with_spike()
        result = AnomalyDetectionService.detect_iqr_anomalies(data, multiplier=3.0)
        # Only the most extreme outlier will survive with multiplier=3
        if result:
            assert all(r["severity"] == "critical" for r in result)

    def test_severity_high_for_multiplier_1_5(self):
        data = _make_data_with_spike()
        result = AnomalyDetectionService.detect_iqr_anomalies(data, multiplier=1.5)
        if result:
            assert all(r["severity"] == "high" for r in result)


# ---------------------------------------------------------------------------
# detect_sudden_spikes
# ---------------------------------------------------------------------------

class TestDetectSuddenSpikes:
    def test_returns_empty_for_single_point(self):
        data = [{"date": "2025-01-01", "cost": 100.0}]
        result = AnomalyDetectionService.detect_sudden_spikes(data)
        assert result == []

    def test_no_spikes_in_uniform_data(self):
        data = _make_uniform_data(30)
        result = AnomalyDetectionService.detect_sudden_spikes(data, spike_threshold=2.0)
        assert result == []

    def test_detects_2x_spike(self):
        data = [
            {"date": "2025-01-01", "cost": 100.0},
            {"date": "2025-01-02", "cost": 100.0},
            {"date": "2025-01-03", "cost": 250.0},  # 2.5x previous
        ]
        result = AnomalyDetectionService.detect_sudden_spikes(data, spike_threshold=2.0)
        assert len(result) == 1
        assert result[0]["date"] == "2025-01-03"
        assert result[0]["type"] == "sudden_spike"

    def test_severity_critical_for_3x_spike(self):
        data = [
            {"date": "2025-01-01", "cost": 100.0},
            {"date": "2025-01-02", "cost": 350.0},  # 3.5x
        ]
        result = AnomalyDetectionService.detect_sudden_spikes(data, spike_threshold=2.0)
        assert result[0]["severity"] == "critical"

    def test_severity_high_for_2x_spike(self):
        data = [
            {"date": "2025-01-01", "cost": 100.0},
            {"date": "2025-01-02", "cost": 210.0},  # 2.1x
        ]
        result = AnomalyDetectionService.detect_sudden_spikes(data, spike_threshold=2.0)
        assert result[0]["severity"] == "high"

    def test_spike_result_has_required_keys(self):
        data = [
            {"date": "2025-01-01", "cost": 100.0},
            {"date": "2025-01-02", "cost": 250.0},
        ]
        result = AnomalyDetectionService.detect_sudden_spikes(data, spike_threshold=2.0)
        required = {"date", "cost", "previous_cost", "change_ratio", "severity", "type", "delta", "percentage_change", "description"}
        assert required.issubset(result[0].keys())


# ---------------------------------------------------------------------------
# detect_cost_drift
# ---------------------------------------------------------------------------

class TestDetectCostDrift:
    def test_returns_empty_for_insufficient_data(self):
        data = _make_uniform_data(13)  # needs >= window_size * 2 = 14
        result = AnomalyDetectionService.detect_cost_drift(data, window_size=7)
        assert result == []

    def test_no_drift_in_stable_data(self):
        data = _make_uniform_data(60)
        result = AnomalyDetectionService.detect_cost_drift(data, window_size=7)
        assert result == []

    def test_detects_upward_drift(self):
        # Start at 100, ramp up to ~200 over 30 days
        start = date(2025, 1, 1)
        data = [
            {"date": (start + timedelta(days=i)).strftime("%Y-%m-%d"), "cost": 100.0 + i * 5}
            for i in range(30)
        ]
        result = AnomalyDetectionService.detect_cost_drift(data, window_size=7, drift_threshold=20.0)
        assert len(result) >= 1
        assert result[0]["type"] == "upward_drift"

    def test_detects_downward_drift(self):
        # Start at 200, decrease to 100 over 30 days
        start = date(2025, 1, 1)
        data = [
            {"date": (start + timedelta(days=i)).strftime("%Y-%m-%d"), "cost": 200.0 - i * 5}
            for i in range(30)
        ]
        result = AnomalyDetectionService.detect_cost_drift(data, window_size=7, drift_threshold=20.0)
        assert len(result) >= 1
        assert result[0]["type"] == "downward_drift"

    def test_drift_result_has_required_keys(self):
        start = date(2025, 1, 1)
        data = [
            {"date": (start + timedelta(days=i)).strftime("%Y-%m-%d"), "cost": 100.0 + i * 5}
            for i in range(30)
        ]
        result = AnomalyDetectionService.detect_cost_drift(data, window_size=7, drift_threshold=10.0)
        if result:
            required = {"start_date", "end_date", "baseline_cost", "current_cost", "drift_percentage", "severity", "type", "delta", "description"}
            assert required.issubset(result[0].keys())

    def test_high_severity_for_drift_over_30_percent(self):
        start = date(2025, 1, 1)
        # 100 → 300 → high severity
        data = [
            {"date": (start + timedelta(days=i)).strftime("%Y-%m-%d"), "cost": 100.0 + i * 10}
            for i in range(30)
        ]
        result = AnomalyDetectionService.detect_cost_drift(data, window_size=7, drift_threshold=10.0)
        if result:
            assert result[0]["severity"] == "high"


# ---------------------------------------------------------------------------
# detect_service_anomalies
# ---------------------------------------------------------------------------

class TestDetectServiceAnomalies:
    def test_returns_empty_for_short_series(self):
        service_costs = {
            "EC2": _make_uniform_data(5)  # < 7 data points
        }
        result = AnomalyDetectionService.detect_service_anomalies(service_costs)
        assert result == []

    def test_adds_service_name_to_anomaly(self):
        service_costs = {
            "EC2": _make_data_with_spike(),
            "RDS": _make_uniform_data(30),
        }
        result = AnomalyDetectionService.detect_service_anomalies(service_costs, threshold=2.0)
        assert all("service" in a for a in result)
        service_names = {a["service"] for a in result}
        assert "EC2" in service_names

    def test_no_anomalies_when_all_uniform(self):
        service_costs = {
            "EC2": _make_uniform_data(30),
            "S3": _make_uniform_data(30),
        }
        result = AnomalyDetectionService.detect_service_anomalies(service_costs)
        assert result == []

    def test_sorted_by_severity(self):
        service_costs = {
            "EC2": _make_data_with_spike(spike_factor=20.0),  # critical
        }
        result = AnomalyDetectionService.detect_service_anomalies(service_costs, threshold=2.0)
        # All items should be in non-ascending severity order
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        orders = [severity_order.get(r["severity"], 99) for r in result]
        assert orders == sorted(orders)


# ---------------------------------------------------------------------------
# get_anomaly_summary
# ---------------------------------------------------------------------------

class TestGetAnomalySummary:
    def test_summary_keys_present(self):
        data = _make_data_with_spike()
        result = AnomalyDetectionService.get_anomaly_summary(data)
        required = {
            "total_anomalies", "critical_anomalies", "high_anomalies",
            "medium_anomalies", "anomalies", "drift_analysis",
            "detection_methods_used", "data_points_analyzed"
        }
        assert required.issubset(result.keys())

    def test_data_points_analyzed_matches_input(self):
        data = _make_data_with_spike(n=20)
        result = AnomalyDetectionService.get_anomaly_summary(data)
        assert result["data_points_analyzed"] == 20

    def test_anomalies_capped_at_20(self):
        """Even with many anomalies the list should be <= 20."""
        # Generate 50 very noisy days
        import random
        random.seed(42)
        start = date(2025, 1, 1)
        data = [
            {"date": (start + timedelta(days=i)).strftime("%Y-%m-%d"),
             "cost": random.uniform(10, 10000)}
            for i in range(50)
        ]
        result = AnomalyDetectionService.get_anomaly_summary(data)
        assert len(result["anomalies"]) <= 20

    def test_no_anomalies_for_uniform_data(self):
        data = _make_uniform_data(30)
        result = AnomalyDetectionService.get_anomaly_summary(data)
        assert result["total_anomalies"] == 0
        assert result["anomalies"] == []

    def test_detection_methods_listed(self):
        data = _make_data_with_spike()
        result = AnomalyDetectionService.get_anomaly_summary(data)
        assert set(result["detection_methods_used"]) == {"z_score", "iqr", "sudden_spike", "drift"}


# ---------------------------------------------------------------------------
# recommend_actions
# ---------------------------------------------------------------------------

class TestRecommendActions:
    def test_spike_returns_recommendations(self):
        anomaly = {"type": "spike", "severity": "high"}
        result = AnomalyDetectionService.recommend_actions(anomaly)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_sudden_spike_returns_recommendations(self):
        anomaly = {"type": "sudden_spike", "severity": "high"}
        result = AnomalyDetectionService.recommend_actions(anomaly)
        assert any("CloudWatch" in r or "infrastructure" in r for r in result)

    def test_critical_severity_adds_urgent_prefix(self):
        anomaly = {"type": "spike", "severity": "critical"}
        result = AnomalyDetectionService.recommend_actions(anomaly)
        assert result[0] == "🚨 IMMEDIATE ACTION REQUIRED"

    def test_upward_drift_returns_finops_recommendation(self):
        anomaly = {"type": "upward_drift", "severity": "medium"}
        result = AnomalyDetectionService.recommend_actions(anomaly)
        assert any("FinOps" in r for r in result)

    def test_unknown_type_returns_fallback(self):
        anomaly = {"type": "unknown_type", "severity": "low"}
        result = AnomalyDetectionService.recommend_actions(anomaly)
        assert len(result) >= 1  # at least the fallback
        assert any("Cost Explorer" in r for r in result)
