from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from backend.app.forecast import BaselineConfig, DailyCash, DailyHistory, predict_baseline


START = date(2026, 9, 7)  # Monday


def make_history(inflows, outflows=None, *, complete=True):
    outflows = outflows if outflows is not None else [20] * len(inflows)
    days = tuple(DailyCash(date=START + timedelta(days=i), currency="USD",
                          inflow_cents=inflow, outflow_cents=outflow)
                 for i, (inflow, outflow) in enumerate(zip(inflows, outflows)))
    return DailyHistory(currency="USD", days=days, complete_coverage=complete,
                        coverage_start=START if complete else None,
                        coverage_end=days[-1].date if complete else None)


@pytest.mark.parametrize("method", ["recent_value", "moving_average", "seasonal_naive"])
@pytest.mark.parametrize("horizon", [1, 2, 30])
def test_constant_predictions_deterministic_currency_dates_and_integer_cents(method, horizon):
    history = make_history([1234] * 28, [567] * 28)
    before = history.model_dump_json()
    result = predict_baseline(history, method=method, horizon_days=horizon)
    assert result == predict_baseline(history, method=method, horizon_days=horizon)
    assert result.currency == "USD"
    assert result.method == method
    assert result.forecast_horizon_days == len(result.days) == horizon
    assert result.days[0].date == history.days[-1].date + timedelta(days=1)
    assert result.days[-1].date == history.days[-1].date + timedelta(days=horizon)
    assert all(day.predicted_inflow_cents == 1234 and day.predicted_outflow_cents == 567 for day in result.days)
    assert all(type(day.predicted_inflow_cents) is int and day.effective_method == method for day in result.days)
    assert history.model_dump_json() == before


def test_recent_value_uses_last_day_not_global_average():
    result = predict_baseline(make_history([100] * 13 + [500], [30] * 13 + [90]), method="recent_value")
    assert [day.predicted_inflow_cents for day in result.days] == [500, 500]
    assert [day.predicted_outflow_cents for day in result.days] == [90, 90]


def test_moving_average_window_and_half_up_rounding():
    config = BaselineConfig(moving_average_window=2)
    result = predict_baseline(make_history([999] * 12 + [0, 1], [500] * 12 + [10, 20]),
                              method="moving_average", config=config)
    assert [day.predicted_inflow_cents for day in result.days] == [1, 1]
    assert [day.predicted_outflow_cents for day in result.days] == [15, 15]


def test_large_integer_mean_has_no_float_precision_loss():
    amount = 10**40 + 1
    result = predict_baseline(make_history([amount] * 14), method="moving_average")
    assert result.days[0].predicted_inflow_cents == amount


@pytest.mark.parametrize("weekend_heavy", [True, False])
def test_seasonal_patterns_come_from_history(weekend_heavy):
    daily = [700 if ((START + timedelta(days=i)).weekday() >= 5) == weekend_heavy else 100 for i in range(40)]
    result = predict_baseline(make_history(daily), method="seasonal_naive", horizon_days=9)
    for day in result.days:
        expected = 700 if (day.date.weekday() >= 5) == weekend_heavy else 100
        assert day.predicted_inflow_cents == expected
        assert day.effective_method == "seasonal_naive"


def test_seasonal_uses_configured_recent_comparable_days_only():
    history = make_history([100] * 7 + [200] * 7 + [300] * 7)
    result = predict_baseline(history, method="seasonal_naive", config=BaselineConfig(weekday_samples=2))
    assert result.days[0].predicted_inflow_cents == 250
    assert result.days[1].predicted_inflow_cents == 250


def test_missing_dates_are_unknown_not_zero_or_compressed_window():
    full = make_history(list(range(100, 115)))
    missing = DailyHistory(currency="USD", days=full.days[:10] + full.days[11:])
    result = predict_baseline(missing, method="moving_average")
    assert result.days[0].predicted_inflow_cents == 114
    assert result.days[0].effective_method == "recent_value"
    assert any("unknown" in warning for warning in result.warnings)
    assert any("contiguous" in warning for warning in result.warnings)


def test_confirmed_zero_is_included_in_average():
    history = make_history([100] * 12 + [0, 0], [40] * 14)
    result = predict_baseline(history, method="moving_average", config=BaselineConfig(moving_average_window=2))
    assert result.days[0].predicted_inflow_cents == 0
    assert result.days[0].predicted_outflow_cents == 40
    assert result.days[0].effective_method == "moving_average"


def test_seasonal_fallback_is_explicit_and_labels_effective_method():
    result = predict_baseline(make_history([100] * 7), method="seasonal_naive")
    assert result.method == "seasonal_naive"
    assert all(day.effective_method == "moving_average" for day in result.days)
    assert any("matching weekdays" in warning for warning in result.warnings)


def test_short_average_falls_back_without_fabricating_history():
    result = predict_baseline(make_history([100, 900]), method="moving_average")
    assert result.days[0].effective_method == "recent_value"
    assert result.days[0].predicted_inflow_cents == 900
    assert any("unvalidated" in warning for warning in result.warnings)


def test_no_history_returns_insufficient_data_not_zero_prediction():
    history = DailyHistory(currency="USD", days=())
    result = predict_baseline(history, method="recent_value", horizon_days=30, as_of=START)
    assert result.status == "insufficient_data"
    assert result.days == ()
    assert result.as_of == START
    assert result.forecast_horizon_days == 30


def test_explicit_as_of_preserves_dates_and_warns_about_staleness():
    history = make_history([100] * 14)
    cutoff = history.days[-1].date + timedelta(days=3)
    result = predict_baseline(history, method="moving_average", as_of=cutoff)
    assert result.days[0].date == cutoff + timedelta(days=1)
    assert result.days[0].effective_method == "recent_value"
    assert any("stale" in warning for warning in result.warnings)


def test_future_observations_cannot_be_passed_as_training_data():
    history = make_history([100] * 14)
    with pytest.raises(ValueError, match="after as_of"):
        predict_baseline(history, method="moving_average", as_of=history.days[6].date)


@pytest.mark.parametrize("horizon", [0, 31, -1, True, 1.5, "2"])
def test_invalid_horizons(horizon):
    with pytest.raises(ValidationError):
        predict_baseline(make_history([100] * 14), method="recent_value", horizon_days=horizon)


@pytest.mark.parametrize("field,value", [("moving_average_window", 0), ("weekday_samples", True),
                                        ("minimum_history_days", -1), ("maximum_origins", 0),
                                        ("mae_tie_relative", float("nan"))])
def test_invalid_configuration(field, value):
    with pytest.raises(ValidationError):
        BaselineConfig(**{field: value})


def test_invalid_method_and_date_overflow():
    with pytest.raises(ValidationError):
        predict_baseline(make_history([100] * 14), method="invented")
    history = DailyHistory(currency="USD", days=(DailyCash(date=date.max, currency="USD"),))
    with pytest.raises(ValueError, match="beyond"):
        predict_baseline(history, method="recent_value")


@pytest.mark.parametrize("kind", ["duplicates", "unsorted", "mixed_currency", "incomplete_claim"])
def test_incompatible_history_is_rejected(kind):
    history = make_history([100] * 14)
    if kind == "duplicates":
        history = DailyHistory(currency="USD", days=history.days + (history.days[-1],))
    elif kind == "unsorted":
        history = DailyHistory(currency="USD", days=tuple(reversed(history.days)))
    elif kind == "mixed_currency":
        history = DailyHistory(currency="USD", days=(DailyCash(date=START, currency="EUR"),))
    else:
        history = history.model_copy(update={"days": history.days[:5] + history.days[6:]})
    with pytest.raises(ValueError):
        predict_baseline(history, method="recent_value")
