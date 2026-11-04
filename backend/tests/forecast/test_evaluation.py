from datetime import date, timedelta
from math import sqrt

import pytest
from pydantic import ValidationError

from backend.app.forecast import BaselineConfig, DailyCash, DailyHistory, calculate_metrics, rolling_origin_backtest


START = date(2026, 9, 7)


def history_for(values):
    days = tuple(DailyCash(date=START + timedelta(days=i), currency="USD", inflow_cents=value, outflow_cents=10)
                 for i, value in enumerate(values))
    return DailyHistory(currency="USD", days=days, complete_coverage=True,
                        coverage_start=START, coverage_end=days[-1].date)


def test_metrics_match_hand_calculation():
    metrics = calculate_metrics([100, 200, 0], [90, 220, 30])
    assert metrics.evaluated_observations == 3
    assert metrics.mae_cents == 20
    assert metrics.bias_cents == pytest.approx(40 / 3)
    assert metrics.wape == pytest.approx(0.2)
    assert metrics.absolute_error_std_cents == pytest.approx(sqrt(200 / 3))
    assert metrics.wape_unavailable_reason is None


def test_bias_sign():
    assert calculate_metrics([100], [120]).bias_cents == 20
    assert calculate_metrics([100], [80]).bias_cents == -20


@pytest.mark.parametrize("actual", [[0, 0], [1, 2], [99]])
def test_zero_and_near_zero_wape_is_unavailable(actual):
    metrics = calculate_metrics(actual, [100] * len(actual))
    assert metrics.wape is None
    assert metrics.wape_unavailable_reason == "zero_or_near_zero_actuals"
    assert metrics.mae_cents is not None


def test_custom_wape_threshold_and_empty_metrics():
    assert calculate_metrics([1], [2], wape_minimum_actual_cents=1).wape == 1
    empty = calculate_metrics([], [])
    assert empty.mae_cents is None and empty.bias_cents is None and empty.wape is None
    assert empty.evaluated_observations == 0
    assert empty.wape_unavailable_reason == "no_observations"


@pytest.mark.parametrize("actual,predicted", [([1], []), ([-1], [0]), ([True], [0]), ([1], [1.1])])
def test_invalid_metric_inputs(actual, predicted):
    with pytest.raises((ValueError, ValidationError)):
        calculate_metrics(actual, predicted)


def test_rolling_origins_separate_horizons_and_both_directions():
    history = history_for([100 * (i + 1) for i in range(10)])
    config = BaselineConfig(minimum_history_days=7, moving_average_window=1, weekday_samples=1,
                            minimum_evaluation_windows=2)
    result = rolling_origin_backtest(history, config=config)
    assert result.origins == (START + timedelta(days=6), START + timedelta(days=7), START + timedelta(days=8))
    recent = result.methods[0]
    assert recent.horizons[0].inflow.mae_cents == 100
    assert recent.horizons[1].inflow.mae_cents == 200
    assert recent.horizons[0].inflow.bias_cents == -100
    assert recent.horizons[0].outflow.mae_cents == recent.horizons[1].outflow.mae_cents == 0
    assert [score.inflow.evaluated_observations for score in recent.horizons] == [3, 2]
    assert result.status == "evaluated"
    for point in recent.points:
        assert point.origin < point.date
        assert point.date == point.origin + timedelta(days=point.horizon)
        train_last = next(day for day in history.days if day.date == point.origin)
        assert point.predicted_inflow_cents == train_last.inflow_cents


def test_methods_use_identical_origins_and_targets():
    result = rolling_origin_backtest(history_for([i * 10 for i in range(35)]), horizon_days=5)
    keys = [[(point.origin, point.date, point.horizon) for point in method.points] for method in result.methods]
    assert keys[0] == keys[1] == keys[2]


def test_future_values_do_not_change_past_origin_predictions():
    history = history_for([100] * 30)
    changed = history.model_copy(update={"days": tuple(
        day.model_copy(update={"inflow_cents": 999999, "outflow_cents": 500000}) if i >= 22 else day
        for i, day in enumerate(history.days)
    )})
    original = rolling_origin_backtest(history)
    modified = rolling_origin_backtest(changed)
    mutation_date = history.days[22].date
    for first, second in zip(original.methods, modified.methods):
        a = [(point.origin, point.date, point.predicted_inflow_cents, point.predicted_outflow_cents)
             for point in first.points if point.origin < mutation_date]
        b = [(point.origin, point.date, point.predicted_inflow_cents, point.predicted_outflow_cents)
             for point in second.points if point.origin < mutation_date]
        assert a == b


def test_sparse_targets_are_skipped_never_scored_as_zero():
    days = tuple(DailyCash(date=START + timedelta(days=2 * i), currency="USD", inflow_cents=100)
                 for i in range(25))
    result = rolling_origin_backtest(DailyHistory(currency="USD", days=days))
    assert result.methods[0].horizons[0].inflow.evaluated_observations == 0
    assert result.methods[0].horizons[0].inflow.mae_cents is None
    assert result.methods[0].horizons[1].inflow.evaluated_observations > 0
    assert not result.methods[0].horizons[0].has_minimum_evidence
    assert result.skipped_unknown_targets > 0
    assert any("not zero-filled" in warning for warning in result.warnings)


@pytest.mark.parametrize("count", [1, 7, 14, 15])
def test_insufficient_windows_do_not_fabricate_metrics_or_validation(count):
    result = rolling_origin_backtest(history_for([100] * count))
    assert result.status == "insufficient_data"
    assert all(not score.has_minimum_evidence for method in result.methods for score in method.horizons)
    if count <= 14:
        assert result.origins == ()
        assert result.methods[0].horizons[0].inflow.mae_cents is None


def test_origin_limit_and_step_are_configurable():
    result = rolling_origin_backtest(history_for([100] * 60), config=BaselineConfig(maximum_origins=4, origin_step=3))
    assert len(result.origins) == 4
    assert all((b - a).days == 3 for a, b in zip(result.origins, result.origins[1:]))
    assert any("most recent 4" in warning for warning in result.warnings)
