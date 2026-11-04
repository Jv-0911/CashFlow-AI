from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from backend.app.forecast.schemas import BaselineConfig, DailyCash, DailyHistory, MLConfig
from backend.app.forecast.trained import (
    FEATURE_SCHEMA_VERSION, forecast_trained_model, history_fingerprint, train_forecast_model,
)


TRAINED_AT = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)


def history(count=42, trend=False, business_offset=0):
    start = date(2026, 1, 1)
    days = tuple(DailyCash(date=start + timedelta(days=index), currency="USD",
                          inflow_cents=1000 + (50 * index if trend else 0) + business_offset,
                          outflow_cents=200, evidence_ids=(f"day_{index}",)) for index in range(count))
    return DailyHistory(currency="USD", days=days, complete_coverage=True,
                        coverage_start=start, coverage_end=days[-1].date)


def train(count=42, trend=False, version="v1", business_id="business_a", ml=False):
    return train_forecast_model(history(count, trend), business_id=business_id,
                                model_version=version, trained_at=TRAINED_AT,
                                ml_config=MLConfig() if ml else None)


def test_metadata_preserves_selection_and_history_without_mutating_input():
    data = history()
    original = data.model_dump()
    bundle = train_forecast_model(data, business_id="business_a", model_version="v1", trained_at=TRAINED_AT)
    assert data.model_dump() == original
    assert bundle.metadata.history_fingerprint == history_fingerprint(data)
    assert bundle.metadata.feature_schema_version == FEATURE_SCHEMA_VERSION
    assert bundle.metadata.training_observations == 42
    assert bundle.metadata.training_start == data.days[0].date
    assert bundle.metadata.training_end == data.days[-1].date
    assert bundle.metadata.inflow.method == "recent_value"
    assert bundle.metadata.inflow.validation_metrics.mae_cents == 0
    assert bundle.metadata.inflow.eligible
    assert bundle.metadata.dependency_versions["scikit-learn"]
    assert forecast_trained_model(bundle).days == bundle.training_forecast.days


def test_mixed_direction_model_inference_reuses_fitted_pipeline(monkeypatch):
    bundle = train(84, trend=True, ml=True)
    assert bundle.metadata.inflow.method == "ridge"
    assert bundle.metadata.outflow.method == "recent_value"
    assert set(bundle.fitted_candidates) == {"ridge"}
    assert bundle.metadata.inflow.selected_features
    assert bundle.metadata.inflow.hyperparameters["alpha"] == 0.1
    import backend.app.forecast.models as models
    monkeypatch.setattr(models, "fit_ml_candidate", lambda *args, **kwargs: pytest.fail("inference attempted fitting"))
    result = forecast_trained_model(bundle)
    assert result.days == bundle.training_forecast.days
    assert result.days[0].predicted_outflow_cents == 200


def test_append_only_observations_update_features_but_not_validation_evidence():
    bundle = train(42)
    result = forecast_trained_model(bundle, history=history(45))
    assert result.as_of == history(45).days[-1].date
    assert result.backtest == bundle.training_forecast.backtest
    assert not result.evaluated_horizons
    assert all(not day.has_minimum_evidence for day in result.days)
    assert result.reliability == "insufficient_evidence"
    assert any("not fresh evaluation" in warning for warning in result.warnings)
    assert bundle.history == history(42)


def test_frozen_ml_uses_appended_features_without_retraining(monkeypatch):
    bundle = train(84, trend=True, ml=True)
    import backend.app.forecast.models as models
    monkeypatch.setattr(models, "fit_ml_candidate", lambda *args, **kwargs: pytest.fail("inference attempted fitting"))
    result = forecast_trained_model(bundle, history=history(86, trend=True))
    assert result.days[0].predicted_inflow_cents > bundle.training_forecast.days[0].predicted_inflow_cents
    assert not result.days[0].has_minimum_evidence


@pytest.mark.parametrize("case", ["changed_prefix", "shorter", "currency", "coverage"])
def test_updated_history_cannot_replace_training_observations(case):
    bundle = train()
    candidate = history(45)
    if case == "changed_prefix":
        days = list(candidate.days)
        days[0] = days[0].model_copy(update={"inflow_cents": 999})
        candidate = candidate.model_copy(update={"days": tuple(days)})
    elif case == "shorter":
        candidate = history(41)
    elif case == "currency":
        candidate = candidate.model_copy(update={"currency": "EUR", "days": tuple(day.model_copy(update={"currency": "EUR"}) for day in candidate.days)})
    elif case == "coverage":
        candidate = DailyHistory(currency="USD", days=candidate.days)
    with pytest.raises(ValueError):
        forecast_trained_model(bundle, history=candidate)


def test_selected_ml_refuses_stale_gap():
    bundle = train(84, trend=True, ml=True)
    with pytest.raises(ValueError, match="stale gaps"):
        forecast_trained_model(bundle, as_of=bundle.history.days[-1].date + timedelta(days=2))


def test_baseline_stale_gap_preserves_dates_without_claiming_evidence():
    bundle = train()
    cutoff = bundle.history.days[-1].date + timedelta(days=3)
    result = forecast_trained_model(bundle, as_of=cutoff)
    assert result.days[0].date == cutoff + timedelta(days=1)
    assert not result.evaluated_horizons
    assert all(not day.has_minimum_evidence for day in result.days)


def test_stored_baseline_never_silently_changes_algorithm():
    data = history(60)
    days = tuple(day.model_copy(update={"inflow_cents": 1000 if index % 2 == 0 else 0})
                 for index, day in enumerate(data.days))
    data = data.model_copy(update={"days": days})
    bundle = train_forecast_model(data, business_id="business_a", model_version="v1", trained_at=TRAINED_AT,
                                  config=BaselineConfig(moving_average_window=2))
    assert bundle.metadata.inflow.method == "moving_average"
    with pytest.raises(ValueError, match="algorithm fallback"):
        forecast_trained_model(bundle, as_of=data.days[-1].date + timedelta(days=1))


def test_requested_horizon_cannot_exceed_trained_configuration():
    bundle = train()
    assert len(forecast_trained_model(bundle, horizon_days=1).days) == 1
    with pytest.raises(ValueError, match="configured horizon"):
        forecast_trained_model(bundle, horizon_days=3)
    with pytest.raises(ValidationError):
        forecast_trained_model(bundle, horizon_days=True)


@pytest.mark.parametrize("business_id,model_version", [("../other", "v1"), ("a/b", "v1"), ("a", ".."), ("a", "v1.json"), ("a", "a" * 65), ("é", "v1")])
def test_training_identifiers_reject_paths_and_unsupported_characters(business_id, model_version):
    with pytest.raises(ValidationError):
        train_forecast_model(history(), business_id=business_id, model_version=model_version, trained_at=TRAINED_AT)


@pytest.mark.parametrize("timestamp", [datetime(2026, 10, 12), datetime(2026, 10, 12, tzinfo=timezone(timedelta(hours=1)))])
def test_training_requires_utc_timestamp(timestamp):
    with pytest.raises(ValidationError, match="UTC"):
        train_forecast_model(history(), business_id="a", model_version="v1", trained_at=timestamp)


def test_training_timestamp_cannot_precede_history():
    with pytest.raises(ValueError, match="precedes"):
        train_forecast_model(history(), business_id="a", model_version="v1",
                             trained_at=datetime(2025, 1, 1, tzinfo=timezone.utc))


def test_empty_history_artifact_remains_explicitly_insufficient():
    bundle = train_forecast_model(DailyHistory(currency="USD", days=()), business_id="new_business", model_version="v1", trained_at=TRAINED_AT)
    result = forecast_trained_model(bundle, as_of=date(2026, 10, 12))
    assert not result.days
    assert result.status == "insufficient_data"
    assert bundle.metadata.training_start is None
    assert bundle.metadata.inflow.method is None


def test_config_and_integer_cents_are_preserved():
    data = history(42)
    days = tuple(day.model_copy(update={"inflow_cents": 10**40 + 1}) for day in data.days)
    data = data.model_copy(update={"days": days})
    bundle = train_forecast_model(data, business_id="a", model_version="v1", trained_at=TRAINED_AT,
                                  config=BaselineConfig(moving_average_window=3), ml_config=MLConfig())
    assert not bundle.fitted_candidates
    assert forecast_trained_model(bundle).days[0].predicted_inflow_cents == 10**40 + 1
    assert bundle.metadata.baseline_config.moving_average_window == 3
