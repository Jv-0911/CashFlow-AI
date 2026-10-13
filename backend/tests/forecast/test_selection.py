from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from backend.app.forecast import (
    BaselineConfig, DailyCash, DailyHistory, ForecastResult, aggregate_daily,
    calculate_balances, forecast_baselines, ingest_csv,
)


START = date(2026, 9, 7)


def make_history(count=56, *, seasonal=False, alternating_expense=False, trend=False):
    days = tuple(DailyCash(
        date=START + timedelta(days=i), currency="USD",
        inflow_cents=(5000 if (START + timedelta(days=i)).weekday() >= 5 else 1000) if seasonal else (100 + i * 10 if trend else 1000),
        outflow_cents=(200 if i % 2 else 0) if alternating_expense else 200,
    ) for i in range(count))
    return DailyHistory(currency="USD", days=days, complete_coverage=True,
                        coverage_start=START, coverage_end=days[-1].date)


def test_separate_models_selected_for_inflow_and_outflow():
    config = BaselineConfig(moving_average_window=2)
    result = forecast_baselines(make_history(seasonal=True, alternating_expense=True), config=config)
    assert result.selected_inflow_model == "seasonal_naive"
    assert result.selected_outflow_model == "moving_average"
    assert result.selection_basis == "chronological_backtest"
    assert result.evaluated_horizons == (1, 2)
    assert result.reliability == "limited_backtest_evidence"
    assert all(day.predicted_inflow_cents == 1000 and day.predicted_outflow_cents == 100 for day in result.days)
    assert result.inflow_evaluation[0].inflow.mae_cents == 0
    assert result.outflow_evaluation[0].outflow.mae_cents == 100
    assert len(result.selection_reasons) == 2


def test_simplest_model_wins_constant_series_ties():
    history = make_history()
    result = forecast_baselines(history)
    assert result.selected_inflow_model == result.selected_outflow_model == "recent_value"
    assert all(score.eligible for score in result.comparison)
    assert all(score.inflow.mae_cents == score.outflow.mae_cents == 0 for score in result.comparison)
    assert history == make_history()
    assert result == forecast_baselines(history)
    assert ForecastResult.model_validate_json(result.model_dump_json()) == result


def test_recent_value_wins_a_rising_trend_on_held_out_error():
    result = forecast_baselines(make_history(trend=True))
    assert result.selected_inflow_model == "recent_value"
    assert [score.inflow.mae_cents for score in result.inflow_evaluation] == [10, 20]
    assert [score.inflow.bias_cents for score in result.inflow_evaluation] == [-10, -20]


@pytest.mark.parametrize("count", [1, 7, 14, 15])
def test_short_history_returns_labeled_recent_value_fallback(count):
    result = forecast_baselines(make_history(count))
    assert result.forecast_horizon_days == len(result.days) == 2
    assert result.selected_inflow_model == "recent_value"
    assert result.selection_basis == "recent_value_fallback"
    assert result.reliability == "insufficient_evidence"
    assert result.evaluated_horizons == ()
    assert not any(day.has_minimum_evidence for day in result.days)
    assert any("unvalidated" in warning for warning in result.warnings)


@pytest.mark.parametrize("horizon", [1, 2, 30])
def test_requested_horizon_preserved_and_long_range_evidence_is_explicit(horizon):
    history = make_history(20)
    result = forecast_baselines(history, horizon_days=horizon)
    assert len(result.days) == result.forecast_horizon_days == horizon
    assert result.days[-1].date == history.days[-1].date + timedelta(days=horizon)
    if horizon == 30:
        assert result.reliability == "insufficient_evidence"
        assert not result.days[-1].has_minimum_evidence
        assert result.inflow_evaluation[-1].inflow.mae_cents is None
        assert any("accuracy is unestablished" in warning for warning in result.warnings)
    else:
        assert result.reliability == "limited_backtest_evidence"


def test_thirty_days_evaluated_when_enough_history_exists():
    result = forecast_baselines(make_history(70), horizon_days=30)
    assert result.evaluated_horizons == tuple(range(1, 31))
    assert all(day.has_minimum_evidence for day in result.days)
    assert result.reliability == "limited_backtest_evidence"
    assert result.uncertainty == "not_estimated"


def test_sparse_history_is_explicit_and_fallback_candidates_not_selected():
    days = tuple(DailyCash(date=START + timedelta(days=2 * i), currency="USD", inflow_cents=100)
                 for i in range(25))
    result = forecast_baselines(DailyHistory(currency="USD", days=days))
    assert result.reliability == "insufficient_evidence"
    assert result.evaluated_horizons == (2,)
    moving = next(score for score in result.comparison if score.method == "moving_average")
    assert not moving.eligible
    assert "fallback required" in moving.reason
    assert all(day.predicted_inflow_cents == 100 for day in result.days)


def test_unconfirmed_contiguous_history_still_warns_about_incomplete_coverage():
    full = make_history()
    result = forecast_baselines(DailyHistory(currency="USD", days=full.days))
    assert result.reliability == "insufficient_evidence"
    assert any("may be incomplete" in warning for warning in result.warnings)


def test_no_history_returns_insufficient_data_without_manufactured_zeros():
    result = forecast_baselines(DailyHistory(currency="USD", days=()), as_of=START)
    assert result.status == "insufficient_data"
    assert result.days == ()
    assert result.selected_inflow_model is result.selected_outflow_model is None
    assert result.selection_basis == "no_history"
    assert result.comparison[0].inflow.mae_cents is None


def test_no_settled_transactions_with_confirmed_coverage_predicts_actual_zeros():
    source = "date,amount_cents,direction,currency,payment_status\n2026-09-07,500,inflow,USD,pending"
    data = ingest_csv(source)
    history = aggregate_daily(data, coverage_start=START, coverage_end=START + timedelta(days=29), complete_coverage=True)
    result = forecast_baselines(history)
    assert result.selected_inflow_model == result.selected_outflow_model == "recent_value"
    assert all(day.predicted_inflow_cents == day.predicted_outflow_cents == 0 for day in result.days)
    assert result.inflow_evaluation[0].inflow.wape is None
    assert result.inflow_evaluation[0].inflow.mae_cents == 0


def test_predictions_can_be_supplied_to_phase_one_balance_calculator():
    result = forecast_baselines(make_history())
    cash = [DailyCash(date=day.date, currency=result.currency, inflow_cents=day.predicted_inflow_cents,
                      outflow_cents=day.predicted_outflow_cents) for day in result.days]
    balance = calculate_balances(cash, start_date=result.days[0].date, horizon_days=2,
                                 opening_balance_cents=100, safety_reserve_cents=0, currency=result.currency)
    assert [day.closing_balance_cents for day in balance.days] == [900, 1700]


@pytest.mark.parametrize("horizon", [0, 31, True, "2", 2.5])
def test_invalid_comparison_horizons(horizon):
    with pytest.raises(ValidationError):
        forecast_baselines(make_history(), horizon_days=horizon)


def test_stale_as_of_preserves_request_and_reduces_reliability():
    history = make_history()
    cutoff = history.days[-1].date + timedelta(days=10)
    result = forecast_baselines(history, as_of=cutoff)
    assert result.days[0].date == cutoff + timedelta(days=1)
    assert result.reliability == "insufficient_evidence"
    assert not any(day.has_minimum_evidence for day in result.days)
    assert any("does not validate" in warning for warning in result.warnings)


@pytest.mark.parametrize("recent_predictions", [[120, 120, 120, 120], [100, 100, 60, 140]])
def test_equal_mae_uses_bias_then_stability_before_complexity(recent_predictions):
    from backend.app.forecast import calculate_metrics
    from backend.app.forecast.schemas import BaselineScore
    from backend.app.forecast.selection import _select

    actual = [100, 100, 100, 100]
    recent = calculate_metrics(actual, recent_predictions)
    moving = calculate_metrics(actual, [80, 120, 80, 120])
    assert recent.mae_cents == moving.mae_cents == 20
    scores = [BaselineScore(method="recent_value", eligible=True, reason="Synthetic held-out errors", inflow=recent, outflow=recent),
              BaselineScore(method="moving_average", eligible=True, reason="Synthetic held-out errors", inflow=moving, outflow=moving)]
    method, reason = _select(scores, "inflow", BaselineConfig())
    assert method == "moving_average"
    assert "bias and error dispersion" in reason
