from datetime import date, timedelta

import numpy as np
import pytest
from pydantic import ValidationError

from backend.app.forecast import DailyCash, DailyHistory, MLConfig
from backend.app.forecast.features import FEATURE_NAMES, build_training_data
from backend.app.forecast.models import (
    FittedCandidate, FittedSeries, fit_ml_candidate, model_eligibility, prediction_cents,
    predict_ml_candidate, recursive_predictions,
)


START = date(2026, 1, 5)


def make_history(count=110, kind="trend"):
    days = tuple(DailyCash(date=START + timedelta(days=i), currency="USD",
                          inflow_cents=1000 + 50*i if kind == "trend" else 1000,
                          outflow_cents=200) for i in range(count))
    return DailyHistory(currency="USD", days=days, complete_coverage=True, coverage_start=START, coverage_end=days[-1].date)


@pytest.mark.parametrize("method", ["ridge", "random_forest", "hist_gradient_boosting"])
def test_models_fit_predict_and_are_deterministic(method):
    data = make_history()
    a = predict_ml_candidate(data, method=method)
    b = predict_ml_candidate(data, method=method)
    assert a.days == b.days
    assert a.currency == "USD" and a.method == method
    assert len(a.days) == 2
    assert all(day.predicted_inflow_cents >= 0 and day.predicted_outflow_cents >= 0 for day in a.days)
    assert a.fit_seconds > 0 and a.inference_seconds > 0
    assert len(a.feature_reports) == 2
    for report in a.feature_reports:
        assert report.training_start == START and report.training_end == data.days[-1].date
        assert report.usable_observations == 109
        assert report.selected_features
        assert report.inner_validation_mae_cents.keys() == {"calendar", "calendar_and_history"}
        assert "not provided" in report.excluded_features["orders"]
        assert "business_type" in report.excluded_features


def test_preprocessing_fits_training_values_only():
    history = make_history(70)
    fitted = fit_ml_candidate(history, method="ridge")
    series = fitted.series["inflow"]
    X, _, _ = build_training_data(history)
    filtered = series.pipeline.named_steps["features"].transform(X[:, series.indices])
    imputed = series.pipeline.named_steps["imputer"].transform(filtered)
    scaler = series.pipeline.named_steps["scaler"]
    assert np.allclose(scaler.mean_, imputed.mean(axis=0))
    before = scaler.mean_.copy()
    series.pipeline.predict(X[-1:, series.indices] * 1000)
    assert np.array_equal(before, scaler.mean_)


@pytest.mark.parametrize("count,method", [(55, "ridge"), (89, "random_forest"), (89, "hist_gradient_boosting")])
def test_insufficient_days_skip_models(count, method):
    data = make_history(count)
    eligibility = model_eligibility(data, method, MLConfig())
    assert not eligibility.eligible
    with pytest.raises(ValueError, match="Requires at least"):
        fit_ml_candidate(data, method=method)


def test_incomplete_or_sparse_data_is_not_ml_eligible():
    full = make_history()
    sparse = DailyHistory(currency="USD", days=full.days[::2])
    assert not model_eligibility(sparse, "ridge", MLConfig()).eligible


def test_configurable_thresholds_still_require_usable_training_rows():
    config = MLConfig(ridge_minimum_days=28, minimum_training_samples=28, inner_validation_days=7)
    assert not model_eligibility(make_history(30), "ridge", config).eligible
    assert model_eligibility(make_history(40), "ridge", config).eligible
    with pytest.raises(ValidationError):
        MLConfig(maximum_origins=100)


@pytest.mark.parametrize("value,expected", [(-1, 0), (0, 0), (1.49, 1), (1.5, 2)])
def test_monetary_clipping_and_rounding(value, expected):
    assert prediction_cents(value) == expected


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 2**54])
def test_invalid_prediction_values_fail_safely(value):
    with pytest.raises(ValueError):
        prediction_cents(value)


def test_recursive_day_two_uses_generated_day_one():
    class AddOne:
        def predict(self, X):
            return X[:, 0] + 1

    data = make_history(56, "constant")
    series = FittedSeries(AddOne(), (FEATURE_NAMES.index("inflow_lag_1"),), "calendar_and_history")
    pair = FittedCandidate("ridge", {"inflow": series, "outflow": series}, (), 0.0)
    predicted = recursive_predictions(pair, data, 2)
    assert [day.predicted_inflow_cents for day in predicted] == [1001, 1002]


def test_thirty_day_inference_uses_one_model_per_direction():
    result = predict_ml_candidate(make_history(70), method="ridge", horizon_days=30)
    assert len(result.days) == 30 and len(result.feature_reports) == 2
    assert result.days[-1].date == make_history(70).days[-1].date + timedelta(days=30)
