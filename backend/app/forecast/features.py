"""Calendar features known ahead; activity features use strictly earlier observations."""

from datetime import date, timedelta
from math import cos, pi, sin

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin

from .baselines import validate_history
from .schemas import DailyCash, DailyHistory


CALENDAR_FEATURES = (
    "time_index", "day_of_week", "weekend", "month", "quarter", "week_of_year", "day_of_month",
    "weekday_sin", "weekday_cos", *(f"weekday_{i}" for i in range(7)),
)
HISTORY_FEATURES = tuple(
    f"{direction}_{suffix}" for direction in ("inflow", "outflow")
    for suffix in ("lag_1", "lag_7", "mean_3", "mean_7", "mean_14", "std_7", "trend_7", "same_weekday")
)
FEATURE_NAMES = CALENDAR_FEATURES + HISTORY_FEATURES
OPTIONAL_FIELDS = ("business_type", "store_id", "bookings", "occupancy", "orders", "customer_count", "promotions", "holiday_indicator")


def feature_row(target: date, observed: dict[date, DailyCash], reference_start: date) -> dict[str, float]:
    """Never accepts target-day outcomes, including during recursive future inference."""
    if any(day >= target for day in observed):
        raise ValueError("features require observations strictly before the target date")
    weekday = target.weekday()
    row = {
        "time_index": float((target - reference_start).days), "day_of_week": float(weekday),
        "weekend": float(weekday >= 5), "month": float(target.month),
        "quarter": float((target.month - 1) // 3 + 1), "week_of_year": float(target.isocalendar().week),
        "day_of_month": float(target.day), "weekday_sin": sin(2 * pi * weekday / 7),
        "weekday_cos": cos(2 * pi * weekday / 7),
        **{f"weekday_{i}": float(weekday == i) for i in range(7)},
    }
    def prior(offset):
        return observed.get(target - timedelta(days=offset)) if target.toordinal() > offset else None
    for direction in ("inflow", "outflow"):
        amount = lambda day: float(getattr(day, f"{direction}_cents"))
        for lag in (1, 7):
            day = prior(lag)
            row[f"{direction}_lag_{lag}"] = amount(day) if day is not None else np.nan
        for window in (3, 7, 14):
            days = [prior(i) for i in range(1, window + 1)]
            row[f"{direction}_mean_{window}"] = float(np.mean([amount(day) for day in days])) if all(day is not None for day in days) else np.nan
            if window == 7:
                row[f"{direction}_std_7"] = float(np.std([amount(day) for day in days])) if all(day is not None for day in days) else np.nan
                row[f"{direction}_trend_7"] = (amount(days[0]) - amount(days[-1])) / 6 if all(day is not None for day in days) else np.nan
        comparable = [day for day in observed.values() if day.date.weekday() == weekday][-3:]
        row[f"{direction}_same_weekday"] = float(np.mean([amount(day) for day in comparable])) if len(comparable) >= 2 else np.nan
    return row


def build_training_data(history: DailyHistory) -> tuple[np.ndarray, dict[str, np.ndarray], tuple[date, ...]]:
    history = validate_history(history)
    observed: dict[date, DailyCash] = {}
    rows, inflows, outflows, dates = [], [], [], []
    for day in history.days:
        if max(day.inflow_cents, day.outflow_cents) > 2**53 - 1:
            raise ValueError("ML requires amounts within the exact integer range of float64; use integer baselines")
        if observed:
            features = feature_row(day.date, observed, history.days[0].date)
            rows.append([features[name] for name in FEATURE_NAMES])
            inflows.append(day.inflow_cents)
            outflows.append(day.outflow_cents)
            dates.append(day.date)
        observed[day.date] = day
    return (np.asarray(rows, dtype=float).reshape(-1, len(FEATURE_NAMES)),
            {"inflow": np.asarray(inflows, dtype=float), "outflow": np.asarray(outflows, dtype=float)}, tuple(dates))


class TrainingFeatureFilter(TransformerMixin, BaseEstimator):
    """Fit missingness, constants, and duplicate-column filtering on training rows only."""

    def __init__(self, names=FEATURE_NAMES, maximum_missing_fraction=0.4):
        self.names = names
        self.maximum_missing_fraction = maximum_missing_fraction

    def _validate(self, values):
        values = np.asarray(values, dtype=float)
        if values.ndim != 2 or values.shape[1] != len(self.names) or np.isinf(values).any():
            raise ValueError("feature matrix must have the configured width and no infinite values")
        return values

    def fit(self, X, y=None):
        values = self._validate(X)
        if not len(values):
            raise ValueError("cannot fit preprocessing without training rows")
        selected, excluded = [], {}
        for index, name in enumerate(self.names):
            column = values[:, index]
            if np.isnan(column).mean() > self.maximum_missing_fraction:
                excluded[name] = "excessive training missingness"
            elif len(np.unique(column[~np.isnan(column)])) <= 1:
                excluded[name] = "constant or unusable in training"
            elif any(np.array_equal(column, values[:, previous], equal_nan=True) for previous in selected):
                excluded[name] = "duplicate engineered training column"
            else:
                selected.append(index)
        if not selected:
            raise ValueError("no usable features after training-only filtering")
        self.selected_indices_ = np.asarray(selected)
        self.selected_features_ = tuple(self.names[index] for index in selected)
        self.excluded_features_ = excluded
        return self

    def transform(self, X):
        if not hasattr(self, "selected_indices_"):
            raise ValueError("feature filter is not fitted")
        return self._validate(X)[:, self.selected_indices_]
