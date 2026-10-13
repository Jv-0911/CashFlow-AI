from datetime import date, timedelta

import numpy as np
import pytest

from backend.app.forecast import DailyCash, DailyHistory
from backend.app.forecast.features import FEATURE_NAMES, TrainingFeatureFilter, build_training_data, feature_row


START = date(2026, 9, 7)


def history(count=20):
    days = tuple(DailyCash(date=START + timedelta(days=i), currency="USD", inflow_cents=100*i,
                          outflow_cents=10*i) for i in range(count))
    return DailyHistory(currency="USD", days=days, complete_coverage=True, coverage_start=START, coverage_end=days[-1].date)


def test_calendar_lags_rolling_trend_and_weekday_features():
    data = history()
    target = START + timedelta(days=14)
    row = feature_row(target, {day.date: day for day in data.days[:14]}, START)
    assert row["day_of_week"] == 0 and row["month"] == 9 and row["quarter"] == 3
    assert row["weekend"] == 0 and row["time_index"] == 14
    assert row["inflow_lag_1"] == 1300 and row["inflow_lag_7"] == 700
    assert row["inflow_mean_3"] == 1200 and row["inflow_mean_7"] == 1000
    assert row["inflow_mean_14"] == 650
    assert row["inflow_std_7"] == 200 and row["inflow_trend_7"] == 100
    assert row["inflow_same_weekday"] == 350
    assert row["outflow_lag_1"] == 130


def test_missing_dates_do_not_turn_into_zero_features():
    data = history()
    observed = {day.date: day for i, day in enumerate(data.days[:14]) if i != 13}
    row = feature_row(START + timedelta(days=14), observed, START)
    assert np.isnan(row["inflow_lag_1"])
    assert np.isnan(row["inflow_mean_3"]) and np.isnan(row["inflow_mean_7"])
    assert row["inflow_lag_7"] == 700


def test_features_refuse_future_or_target_day_values():
    data = history()
    with pytest.raises(ValueError, match="strictly before"):
        feature_row(data.days[10].date, {day.date: day for day in data.days}, START)


def test_training_row_features_exclude_target_values_and_insufficient_lags():
    data = history()
    X, y, dates = build_training_data(data)
    assert dates[0] == START + timedelta(days=1)
    assert X[0, FEATURE_NAMES.index("inflow_lag_1")] == 0
    assert np.isnan(X[0, FEATURE_NAMES.index("inflow_lag_7")])
    assert y["inflow"][0] == 100
    changed = data.model_copy(update={"days": data.days[:-1] + (data.days[-1].model_copy(update={"inflow_cents": 999999}),)})
    changed_X, changed_y, _ = build_training_data(changed)
    assert np.array_equal(X, changed_X, equal_nan=True)
    assert y["inflow"][-1] != changed_y["inflow"][-1]


def test_training_filter_constant_duplicate_missing_and_future_invariance():
    names = ("constant", "signal", "duplicate", "unknown")
    X = np.array([[1, 1, 1, np.nan], [1, 2, 2, np.nan], [1, 3, 3, np.nan]])
    selector = TrainingFeatureFilter(names=names).fit(X)
    assert selector.selected_features_ == ("signal",)
    assert "constant" in selector.excluded_features_["constant"]
    assert "duplicate" in selector.excluded_features_["duplicate"]
    assert "missingness" in selector.excluded_features_["unknown"]
    assert selector.transform([[200, 1000, -1000, 500]]).tolist() == [[1000]]
    assert selector.selected_features_ == ("signal",)


@pytest.mark.parametrize("values", [[[float("inf")]], [[1, 2]], [[1], [1]]])
def test_unusable_or_invalid_feature_matrices_are_rejected(values):
    with pytest.raises(ValueError):
        TrainingFeatureFilter(names=("x",)).fit(values)


def test_observed_amounts_outside_float64_exact_range_are_rejected_for_ml():
    data = history(2)
    data = data.model_copy(update={"days": (data.days[0], data.days[1].model_copy(update={"inflow_cents": 2**53}))})
    with pytest.raises(ValueError, match="exact integer range"):
        build_training_data(data)
