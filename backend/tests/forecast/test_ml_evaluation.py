from datetime import date, timedelta

import pytest

from backend.app.forecast import DailyCash, DailyHistory, ForecastResult, MLConfig, forecast_baselines


START = date(2026, 1, 5)


def make_history(count=84, kind="trend"):
    days = tuple(DailyCash(date=START + timedelta(days=i), currency="USD",
        inflow_cents=(1000+50*i if kind == "trend" else 5000 if (START+timedelta(days=i)).weekday() >= 5 else 1000) if kind != "constant" else 1000,
        outflow_cents=200) for i in range(count))
    return DailyHistory(currency="USD", days=days, complete_coverage=True, coverage_start=START, coverage_end=days[-1].date)


def test_ml_wins_a_clear_trend_and_outflow_keeps_simpler_baseline():
    result = forecast_baselines(make_history(), ml_config=MLConfig())
    assert result.selected_inflow_model == "ridge"
    assert result.selected_outflow_model == "recent_value"
    assert result.inflow_evaluation[0].inflow.mae_cents < 50
    assert result.inflow_evaluation[1].inflow.mae_cents < 100
    assert any("Paired held-out MAE gain" in reason for reason in result.selection_reasons)
    assert len(result.feature_reports) == 1 and result.feature_reports[0].direction == "inflow"
    assert result.backtest.ml_config == MLConfig()
    assert ForecastResult.model_validate_json(result.model_dump_json()) == result
    assert len({origin.weekday() for origin in result.backtest.origins}) > 1


def test_no_useful_signal_baseline_wins_exact_ties():
    result = forecast_baselines(make_history(kind="constant"), ml_config=MLConfig())
    assert result.selected_inflow_model == result.selected_outflow_model == "recent_value"
    assert result.feature_reports == ()
    ridge = next(score for score in result.comparison if score.method == "ridge")
    assert "does not exceed" in ridge.selection_evidence["inflow"]


def test_weekday_pattern_keeps_perfect_seasonal_baseline():
    result = forecast_baselines(make_history(kind="weekday"), ml_config=MLConfig())
    assert result.selected_inflow_model == "seasonal_naive"
    assert result.inflow_evaluation[0].inflow.mae_cents == 0


def test_all_models_compared_on_identical_origins_and_windows():
    result = forecast_baselines(make_history(112), ml_config=MLConfig(maximum_origins=3))
    assert {method.method for method in result.backtest.methods} == {
        "recent_value", "moving_average", "seasonal_naive", "ridge", "random_forest", "hist_gradient_boosting"}
    keys = [[(point.origin, point.date, point.horizon) for point in method.points] for method in result.backtest.methods]
    assert all(key == keys[0] for key in keys)
    assert len(result.backtest.origins) == 3
    for evaluation in result.backtest.methods:
        for report in evaluation.fold_feature_reports:
            assert report.training_end in result.backtest.origins
            assert report.training_start == START
        assert all(point.origin < point.date for point in evaluation.points)


def test_future_mutation_cannot_change_earlier_origin_ml_predictions_or_features():
    data = make_history()
    mutation_date = data.days[73].date
    changed = data.model_copy(update={"days": tuple(day.model_copy(update={"inflow_cents": 20000})
                if day.date >= mutation_date else day for day in data.days)})
    a = forecast_baselines(data, ml_config=MLConfig(maximum_origins=3))
    b = forecast_baselines(changed, ml_config=MLConfig(maximum_origins=3))
    for first, second in zip(a.backtest.methods, b.backtest.methods):
        first_points = [(point.origin, point.date, point.predicted_inflow_cents, point.predicted_outflow_cents)
                        for point in first.points if point.origin < mutation_date]
        second_points = [(point.origin, point.date, point.predicted_inflow_cents, point.predicted_outflow_cents)
                         for point in second.points if point.origin < mutation_date]
        assert first_points == second_points
        assert [report for report in first.fold_feature_reports if report.training_end < mutation_date] == [
            report for report in second.fold_feature_reports if report.training_end < mutation_date]


@pytest.mark.parametrize("count", [0, 13, 40, 56, 60])
def test_small_history_skips_ml_and_preserves_phase_two_results(count):
    data = make_history(count) if count else DailyHistory(currency="USD", days=())
    before = forecast_baselines(data)
    after = forecast_baselines(data, ml_config=MLConfig())
    assert after.days == before.days
    assert after.selected_inflow_model == before.selected_inflow_model
    assert not any(item.eligible for item in after.model_eligibility)


def test_long_horizon_without_comparison_windows_preserves_dates_and_warns():
    data = make_history(84)
    result = forecast_baselines(data, horizon_days=30, ml_config=MLConfig())
    assert len(result.days) == 30
    assert result.days[-1].date == data.days[-1].date + timedelta(days=30)
    assert not any(item.eligible for item in result.model_eligibility)
    assert any("Too few complete chronological windows" in warning for warning in result.warnings)


def test_stale_as_of_skips_ml_and_retains_requested_dates():
    data = make_history()
    cutoff = data.days[-1].date + timedelta(days=2)
    result = forecast_baselines(data, as_of=cutoff, ml_config=MLConfig())
    assert not any(item.eligible for item in result.model_eligibility)
    assert result.days[0].date == cutoff + timedelta(days=1)
    assert result.reliability == "insufficient_evidence"


def test_missing_metrics_are_not_selected_as_if_they_were_zero_error():
    from backend.app.forecast import BaselineConfig, calculate_metrics
    from backend.app.forecast.schemas import BaselineScore
    from backend.app.forecast.selection import _select

    empty = calculate_metrics([], [])
    known = calculate_metrics([100], [101])
    missing = BaselineScore(method="ridge", eligible=True, reason="Missing synthetic evidence", inflow=empty, outflow=empty)
    baseline = BaselineScore(method="recent_value", eligible=True, reason="Synthetic held-out evidence", inflow=known, outflow=known)
    chosen, _ = _select([missing, baseline], "inflow", BaselineConfig())
    assert chosen == "recent_value"
    with pytest.raises(ValueError, match="complete held-out metrics"):
        _select([missing], "inflow", BaselineConfig())


def test_unconfirmed_coverage_preserves_baseline_and_declines_ml():
    full = make_history()
    data = DailyHistory(currency="USD", days=full.days[::2])
    result = forecast_baselines(data, ml_config=MLConfig())
    assert all(not item.eligible for item in result.model_eligibility)
    assert result.days == forecast_baselines(data).days


def test_comparison_window_requirement_exceeding_budget_skips_ml():
    from backend.app.forecast import BaselineConfig

    result = forecast_baselines(make_history(), config=BaselineConfig(minimum_evaluation_windows=10),
                                ml_config=MLConfig(maximum_origins=3))
    assert all(not item.eligible for item in result.model_eligibility)
