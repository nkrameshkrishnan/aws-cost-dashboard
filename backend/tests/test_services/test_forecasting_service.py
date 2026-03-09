"""
Unit tests for CostForecastingService.

All methods are pure (no DB / AWS calls), so no mocking is required.
"""
import pytest
from datetime import date, timedelta

from app.services.forecasting_service import CostForecastingService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_data(n: int, base: float = 100.0, slope: float = 0.0):
    """Return n days of linearly-trending cost data."""
    start = date(2025, 1, 1)
    return [
        {
            "date": (start + timedelta(days=i)).strftime("%Y-%m-%d"),
            "cost": base + slope * i,
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# forecast_linear
# ---------------------------------------------------------------------------

class TestForecastLinear:
    def test_returns_error_for_insufficient_data(self):
        data = _make_data(6)  # needs >= 7
        result = CostForecastingService.forecast_linear(data, days_ahead=7)
        assert "error" in result
        assert result["predictions"] == []

    def test_returns_correct_number_of_predictions(self):
        data = _make_data(30)
        result = CostForecastingService.forecast_linear(data, days_ahead=14)
        assert len(result["predictions"]) == 14

    def test_predictions_are_future_dates(self):
        data = _make_data(30)
        result = CostForecastingService.forecast_linear(data, days_ahead=5)
        last_hist = date(2025, 1, 30)
        for pred in result["predictions"]:
            pred_date = date.fromisoformat(pred["date"])
            assert pred_date > last_hist

    def test_prediction_keys_present(self):
        data = _make_data(30)
        result = CostForecastingService.forecast_linear(data, days_ahead=5)
        required = {"date", "predicted_cost", "lower_bound", "upper_bound", "confidence"}
        for pred in result["predictions"]:
            assert required.issubset(pred.keys())

    def test_predicted_cost_non_negative(self):
        data = _make_data(30)
        result = CostForecastingService.forecast_linear(data, days_ahead=30)
        for pred in result["predictions"]:
            assert pred["predicted_cost"] >= 0

    def test_trend_increasing_for_positive_slope(self):
        data = _make_data(30, slope=10.0)
        result = CostForecastingService.forecast_linear(data, days_ahead=5)
        assert result["trend"] == "increasing"

    def test_trend_decreasing_for_negative_slope(self):
        data = _make_data(30, base=1000.0, slope=-5.0)
        result = CostForecastingService.forecast_linear(data, days_ahead=5)
        assert result["trend"] == "decreasing"

    def test_r_squared_between_0_and_1(self):
        data = _make_data(30)
        result = CostForecastingService.forecast_linear(data, days_ahead=5)
        assert 0.0 <= result["r_squared"] <= 1.0

    def test_method_name_is_linear_regression(self):
        data = _make_data(30)
        result = CostForecastingService.forecast_linear(data, days_ahead=5)
        assert result["method"] == "linear_regression"

    def test_upper_bound_gte_lower_bound(self):
        data = _make_data(30)
        result = CostForecastingService.forecast_linear(data, days_ahead=5)
        for pred in result["predictions"]:
            assert pred["upper_bound"] >= pred["lower_bound"]


# ---------------------------------------------------------------------------
# forecast_moving_average
# ---------------------------------------------------------------------------

class TestForecastMovingAverage:
    def test_returns_error_for_insufficient_data(self):
        data = _make_data(6)
        result = CostForecastingService.forecast_moving_average(data, days_ahead=5, window=7)
        assert "error" in result
        assert result["predictions"] == []

    def test_returns_correct_number_of_predictions(self):
        data = _make_data(30)
        result = CostForecastingService.forecast_moving_average(data, days_ahead=10, window=7)
        assert len(result["predictions"]) == 10

    def test_all_predictions_equal_recent_average(self):
        """MA forecast should predict the same value for all future days."""
        data = _make_data(30)
        result = CostForecastingService.forecast_moving_average(data, days_ahead=5, window=7)
        avg = result["average_daily_cost"]
        for pred in result["predictions"]:
            assert abs(pred["predicted_cost"] - avg) < 1e-6

    def test_prediction_keys_present(self):
        data = _make_data(30)
        result = CostForecastingService.forecast_moving_average(data, days_ahead=5)
        required = {"date", "predicted_cost", "lower_bound", "upper_bound", "confidence"}
        for pred in result["predictions"]:
            assert required.issubset(pred.keys())

    def test_method_name(self):
        data = _make_data(30)
        result = CostForecastingService.forecast_moving_average(data, days_ahead=3)
        assert result["method"] == "moving_average"

    def test_trend_is_stable(self):
        data = _make_data(30)
        result = CostForecastingService.forecast_moving_average(data, days_ahead=3)
        assert result["trend"] == "stable"

    def test_lower_bound_non_negative(self):
        data = _make_data(30, base=10.0)  # low base — std may push lower below 0
        result = CostForecastingService.forecast_moving_average(data, days_ahead=5)
        for pred in result["predictions"]:
            assert pred["lower_bound"] >= 0


# ---------------------------------------------------------------------------
# forecast_exponential_smoothing
# ---------------------------------------------------------------------------

class TestForecastExponentialSmoothing:
    def test_returns_error_for_insufficient_data(self):
        data = _make_data(2)  # needs >= 3
        result = CostForecastingService.forecast_exponential_smoothing(data, days_ahead=5)
        assert "error" in result
        assert result["predictions"] == []

    def test_returns_correct_number_of_predictions(self):
        data = _make_data(30)
        result = CostForecastingService.forecast_exponential_smoothing(data, days_ahead=10)
        assert len(result["predictions"]) == 10

    def test_prediction_keys_present(self):
        data = _make_data(30)
        result = CostForecastingService.forecast_exponential_smoothing(data, days_ahead=5)
        required = {"date", "predicted_cost", "lower_bound", "upper_bound", "confidence"}
        for pred in result["predictions"]:
            assert required.issubset(pred.keys())

    def test_method_name(self):
        data = _make_data(30)
        result = CostForecastingService.forecast_exponential_smoothing(data, days_ahead=3)
        assert result["method"] == "exponential_smoothing"

    def test_alpha_stored_in_result(self):
        data = _make_data(30)
        result = CostForecastingService.forecast_exponential_smoothing(data, days_ahead=3, alpha=0.5)
        assert result["alpha"] == 0.5

    def test_trend_increasing_for_rising_data(self):
        data = _make_data(30, slope=10.0)
        result = CostForecastingService.forecast_exponential_smoothing(data, days_ahead=5, alpha=0.5)
        assert result["trend"] == "increasing"

    def test_trend_decreasing_for_falling_data(self):
        data = _make_data(30, base=1000.0, slope=-10.0)
        result = CostForecastingService.forecast_exponential_smoothing(data, days_ahead=5, alpha=0.5)
        assert result["trend"] == "decreasing"

    def test_trend_stable_for_flat_data(self):
        data = _make_data(30)
        result = CostForecastingService.forecast_exponential_smoothing(data, days_ahead=5, alpha=0.3)
        assert result["trend"] == "stable"

    def test_predicted_cost_non_negative(self):
        data = _make_data(30)
        result = CostForecastingService.forecast_exponential_smoothing(data, days_ahead=5)
        for pred in result["predictions"]:
            assert pred["predicted_cost"] >= 0


# ---------------------------------------------------------------------------
# forecast_ensemble
# ---------------------------------------------------------------------------

class TestForecastEnsemble:
    def test_returns_error_for_insufficient_data(self):
        data = _make_data(6)
        result = CostForecastingService.forecast_ensemble(data, days_ahead=5)
        assert "error" in result

    def test_returns_correct_number_of_predictions(self):
        data = _make_data(30)
        result = CostForecastingService.forecast_ensemble(data, days_ahead=10)
        assert len(result["predictions"]) == 10

    def test_method_name(self):
        data = _make_data(30)
        result = CostForecastingService.forecast_ensemble(data, days_ahead=5)
        assert result["method"] == "ensemble"

    def test_models_used_lists_three_methods(self):
        data = _make_data(30)
        result = CostForecastingService.forecast_ensemble(data, days_ahead=5)
        assert set(result["models_used"]) == {"linear_regression", "moving_average", "exponential_smoothing"}

    def test_ensemble_is_average_of_individual_models(self):
        data = _make_data(30)
        result = CostForecastingService.forecast_ensemble(data, days_ahead=5)
        linear = CostForecastingService.forecast_linear(data, days_ahead=5)
        ma = CostForecastingService.forecast_moving_average(data, days_ahead=5)
        es = CostForecastingService.forecast_exponential_smoothing(data, days_ahead=5)
        for i, pred in enumerate(result["predictions"]):
            expected_avg = (
                linear["predictions"][i]["predicted_cost"]
                + ma["predictions"][i]["predicted_cost"]
                + es["predictions"][i]["predicted_cost"]
            ) / 3
            assert abs(pred["predicted_cost"] - expected_avg) < 1e-6

    def test_individual_predictions_key_present(self):
        data = _make_data(30)
        result = CostForecastingService.forecast_ensemble(data, days_ahead=5)
        for pred in result["predictions"]:
            assert "individual_predictions" in pred
            ind = pred["individual_predictions"]
            assert "linear" in ind
            assert "moving_average" in ind
            assert "exponential_smoothing" in ind

    def test_upper_bound_is_max_of_models(self):
        data = _make_data(30)
        result = CostForecastingService.forecast_ensemble(data, days_ahead=5)
        linear = CostForecastingService.forecast_linear(data, days_ahead=5)
        ma = CostForecastingService.forecast_moving_average(data, days_ahead=5)
        es = CostForecastingService.forecast_exponential_smoothing(data, days_ahead=5)
        for i, pred in enumerate(result["predictions"]):
            expected_upper = max(
                linear["predictions"][i]["upper_bound"],
                ma["predictions"][i]["upper_bound"],
                es["predictions"][i]["upper_bound"],
            )
            assert abs(pred["upper_bound"] - expected_upper) < 1e-6


# ---------------------------------------------------------------------------
# calculate_forecast_accuracy
# ---------------------------------------------------------------------------

class TestCalculateForecastAccuracy:
    def _make_pairs(self, n: int = 10, error: float = 0.0):
        """Return matching actual/predicted lists, with optional constant error."""
        start = date(2025, 1, 1)
        actual = [
            {"date": (start + timedelta(days=i)).strftime("%Y-%m-%d"), "cost": 100.0}
            for i in range(n)
        ]
        predicted = [
            {"date": (start + timedelta(days=i)).strftime("%Y-%m-%d"), "predicted_cost": 100.0 + error}
            for i in range(n)
        ]
        return actual, predicted

    def test_perfect_accuracy(self):
        actual, predicted = self._make_pairs(error=0.0)
        result = CostForecastingService.calculate_forecast_accuracy(actual, predicted)
        assert result["mae"] == pytest.approx(0.0, abs=1e-6)
        assert result["rmse"] == pytest.approx(0.0, abs=1e-6)

    def test_mae_matches_constant_error(self):
        actual, predicted = self._make_pairs(error=10.0)
        result = CostForecastingService.calculate_forecast_accuracy(actual, predicted)
        assert result["mae"] == pytest.approx(10.0, rel=1e-4)

    def test_rmse_matches_constant_error(self):
        actual, predicted = self._make_pairs(error=10.0)
        result = CostForecastingService.calculate_forecast_accuracy(actual, predicted)
        assert result["rmse"] == pytest.approx(10.0, rel=1e-4)

    def test_returns_error_for_no_overlapping_dates(self):
        actual = [{"date": "2025-01-01", "cost": 100.0}]
        predicted = [{"date": "2025-02-01", "predicted_cost": 100.0}]
        result = CostForecastingService.calculate_forecast_accuracy(actual, predicted)
        assert "error" in result

    def test_result_has_required_keys(self):
        actual, predicted = self._make_pairs()
        result = CostForecastingService.calculate_forecast_accuracy(actual, predicted)
        required = {"mae", "mape", "rmse", "r_squared", "samples"}
        assert required.issubset(result.keys())

    def test_sample_count_matches_overlap(self):
        actual, predicted = self._make_pairs(n=10)
        result = CostForecastingService.calculate_forecast_accuracy(actual, predicted)
        assert result["samples"] == 10


# ---------------------------------------------------------------------------
# detect_seasonality
# ---------------------------------------------------------------------------

class TestDetectSeasonality:
    def test_returns_weekly_pattern_keys(self):
        data = _make_data(60)
        result = CostForecastingService.detect_seasonality(data)
        required = {
            "has_weekly_seasonality", "weekly_coefficient_of_variation",
            "weekly_pattern", "highest_cost_day", "lowest_cost_day",
            "monthly_pattern"
        }
        assert required.issubset(result.keys())

    def test_weekly_pattern_has_seven_days(self):
        data = _make_data(60)
        result = CostForecastingService.detect_seasonality(data)
        days = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}
        assert set(result["weekly_pattern"].keys()) == days

    def test_no_seasonality_for_uniform_data(self):
        data = _make_data(60)
        result = CostForecastingService.detect_seasonality(data)
        # Uniform data has zero coefficient of variation → no seasonality
        assert not result["has_weekly_seasonality"]

    def test_highest_cost_day_is_valid_day_name(self):
        data = _make_data(60)
        result = CostForecastingService.detect_seasonality(data)
        valid_days = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}
        assert result["highest_cost_day"] in valid_days
