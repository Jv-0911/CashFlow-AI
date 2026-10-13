"""Train once and reuse selected estimators without fitting during inference."""

from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha256
from importlib.metadata import version
import json
import platform
from typing import TYPE_CHECKING

from pydantic import TypeAdapter

from .baselines import METHODS, _predict, forecast_context, validate_history
from .features import FEATURE_NAMES
from .persistence_schemas import DirectionModelMetadata, ModelMetadata, SafeIdentifier, UTCTimestamp
from .schemas import BaselineConfig, DailyHistory, ForecastResult, MLConfig, SelectedPredictionDay
from .selection import forecast_baselines

if TYPE_CHECKING:
    from .models import FittedCandidate


FEATURE_SCHEMA_VERSION = "daily-v1-" + sha256("\n".join(FEATURE_NAMES).encode()).hexdigest()[:16]


def dependency_versions() -> dict[str, str]:
    """Exact versions are required for this deliberately nonportable local format."""
    return {"python": platform.python_version(), **{
        name: version(name) for name in ("numpy", "scikit-learn", "joblib", "pydantic")
    }}


def history_fingerprint(history: DailyHistory) -> str:
    history = validate_history(history)
    value = json.dumps(history.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class TrainedForecastModel:
    metadata: ModelMetadata
    history: DailyHistory
    training_forecast: ForecastResult
    fitted_candidates: dict[str, "FittedCandidate"]


def _direction_metadata(direction, forecast, fitted, config):
    method = getattr(forecast, f"selected_{direction}_model")
    score = next((item for item in forecast.comparison if item.method == method), None)
    selected_features, hyperparameters = (), {}
    if method in fitted:
        candidate = fitted[method]
        report = next(item for item in candidate.feature_reports if item.direction == direction)
        selected_features = report.selected_features
        params = candidate.series[direction].pipeline.named_steps["model"].get_params(deep=False)
        hyperparameters = {key: value for key, value in params.items()
                           if value is None or type(value) in (str, int, float, bool)}
        hyperparameters["feature_group"] = candidate.series[direction].group
    elif method == "moving_average":
        hyperparameters = {"window_days": config.moving_average_window}
    elif method == "seasonal_naive":
        hyperparameters = {"weekday_samples": config.weekday_samples}
    return DirectionModelMetadata(
        direction=direction, method=method, selected_features=selected_features,
        hyperparameters=hyperparameters,
        validation_metrics=getattr(score, direction) if score else None,
        eligible=bool(score and score.eligible),
        eligibility_reason=score.reason if score else "No historical model available.",
    )


def train_forecast_model(
    history: DailyHistory, *, business_id: str, model_version: str,
    trained_at: datetime, horizon_days: int = 2, config: BaselineConfig | None = None,
    ml_config: MLConfig | None = None,
) -> TrainedForecastModel:
    """Chronologically select models and retain the selected sklearn pipelines.

    Empty/short histories remain explicitly limited baseline artifacts. This operation
    does not attest actual-payment verification; the caller must validate provenance.
    """
    business_id = TypeAdapter(SafeIdentifier).validate_python(business_id)
    model_version = TypeAdapter(SafeIdentifier).validate_python(model_version)
    trained_at = TypeAdapter(UTCTimestamp).validate_python(trained_at)
    history = validate_history(history)
    if history.days and trained_at.date() < history.days[-1].date:
        raise ValueError("training timestamp precedes historical observations")
    config = BaselineConfig.model_validate((config or BaselineConfig()).model_dump())
    ml_config = MLConfig.model_validate(ml_config.model_dump()) if ml_config is not None else None
    forecast = forecast_baselines(history, horizon_days=horizon_days, config=config, ml_config=ml_config)
    fitted = {}
    for method in dict.fromkeys((forecast.selected_inflow_model, forecast.selected_outflow_model)):
        if method is not None and method not in METHODS:
            from .models import fit_ml_candidate
            fitted[method] = fit_ml_candidate(history, method=method, config=ml_config)
    metadata = ModelMetadata(
        business_id=business_id, model_id="model-" + sha256(f"{business_id}:{model_version}".encode()).hexdigest()[:20],
        model_version=model_version, currency=history.currency, trained_at=trained_at,
        horizon_days=forecast.forecast_horizon_days,
        training_start=history.days[0].date if history.days else None,
        training_end=history.days[-1].date if history.days else None,
        training_observations=len(history.days), history_fingerprint=history_fingerprint(history),
        complete_coverage=history.complete_coverage, feature_schema_version=FEATURE_SCHEMA_VERSION,
        inflow=_direction_metadata("inflow", forecast, fitted, config),
        outflow=_direction_metadata("outflow", forecast, fitted, config),
        baseline_config=config, ml_config=ml_config, dependency_versions=dependency_versions(),
        reliability=forecast.reliability, evaluated_horizons=forecast.evaluated_horizons,
        candidate_eligibility=forecast.model_eligibility, warnings=forecast.warnings,
    )
    return TrainedForecastModel(metadata, history, forecast, fitted)


def validate_trained_model(bundle: TrainedForecastModel) -> TrainedForecastModel:
    """Check runtime consistency after trusted deserialization or before persistence."""
    if not isinstance(bundle, TrainedForecastModel):
        raise ValueError("artifact is not a trained forecasting model")
    metadata = ModelMetadata.model_validate(bundle.metadata.model_dump())
    expected_model_id = "model-" + sha256(f"{metadata.business_id}:{metadata.model_version}".encode()).hexdigest()[:20]
    if metadata.model_id != expected_model_id:
        raise ValueError("model identifier does not match its business and version")
    if metadata.feature_schema_version != FEATURE_SCHEMA_VERSION or metadata.dependency_versions != dependency_versions():
        raise ValueError("trained model is incompatible with this runtime")
    history = validate_history(bundle.history)
    forecast = ForecastResult.model_validate(bundle.training_forecast.model_dump())
    if metadata.currency != history.currency or forecast.currency != history.currency:
        raise ValueError("model currency does not match its training history")
    if metadata.history_fingerprint != history_fingerprint(history):
        raise ValueError("training history fingerprint does not match metadata")
    if metadata.training_observations != len(history.days):
        raise ValueError("training observation count does not match metadata")
    if metadata.training_start != (history.days[0].date if history.days else None) or metadata.training_end != (history.days[-1].date if history.days else None):
        raise ValueError("training dates do not match metadata")
    if forecast.as_of != metadata.training_end or forecast.forecast_horizon_days != metadata.horizon_days:
        raise ValueError("training forecast dates do not match metadata")
    if forecast.selected_inflow_model != metadata.inflow.method or forecast.selected_outflow_model != metadata.outflow.method:
        raise ValueError("selected forecasting methods do not match metadata")
    if forecast.backtest.config != metadata.baseline_config or forecast.backtest.ml_config not in (None, metadata.ml_config):
        raise ValueError("training configuration does not match metadata")
    required = {method for method in (metadata.inflow.method, metadata.outflow.method) if method is not None and method not in METHODS}
    if set(bundle.fitted_candidates) != required:
        raise ValueError("selected ML methods do not match stored pipelines")
    for method, candidate in bundle.fitted_candidates.items():
        if candidate.method != method or set(candidate.series) != {"inflow", "outflow"}:
            raise ValueError("stored ML pipeline directions are inconsistent")
        for direction in ("inflow", "outflow"):
            direction_metadata = getattr(metadata, direction)
            if direction_metadata.method == method:
                report = next((item for item in candidate.feature_reports if item.direction == direction), None)
                if report is None or report.selected_features != direction_metadata.selected_features:
                    raise ValueError("selected feature metadata does not match stored ML reports")
    return bundle


def forecast_trained_model(
    bundle: TrainedForecastModel, *, history: DailyHistory | None = None,
    horizon_days: int | None = None, as_of: date | None = None,
) -> ForecastResult:
    """Infer from frozen ML pipelines or a fixed selected historical baseline.

    Optional observations must extend the immutable original history. Updated
    history never inherits the original backtest's evidence or uncertainty claim.
    """
    validate_trained_model(bundle)
    metadata = bundle.metadata
    history = validate_history(history) if history is not None else bundle.history
    if history.currency != metadata.currency:
        raise ValueError("new history currency does not match the trained model")
    old = bundle.history.days
    if len(history.days) < len(old) or history.days[:len(old)] != old:
        raise ValueError("new history must append to the immutable trained history")
    if old and history.days[0].date != old[0].date:
        raise ValueError("new history must retain the original feature time origin")
    if bundle.history.complete_coverage and not history.complete_coverage:
        raise ValueError("complete trained history cannot be replaced by unconfirmed coverage")
    horizon_days = metadata.horizon_days if horizon_days is None else horizon_days
    history, horizon_days, cutoff, context_warnings = forecast_context(history, horizon_days, as_of)
    if horizon_days > metadata.horizon_days:
        raise ValueError("requested horizon exceeds the trained model's configured horizon")
    unchanged = history_fingerprint(history) == metadata.history_fingerprint
    warnings = list(bundle.training_forecast.warnings + context_warnings)
    if not unchanged:
        warnings.append("Frozen model inference uses appended observations; stored validation metrics describe training-time selection, not fresh evaluation. Uncertainty and horizon evidence must be reevaluated.")
    predicted = {}
    for method in dict.fromkeys((metadata.inflow.method, metadata.outflow.method)):
        if method is None:
            continue
        if method in METHODS:
            result = _predict(history, horizon_days, cutoff, method, metadata.baseline_config, ())
            if any(day.effective_method != method for day in result.days):
                raise ValueError("stored baseline requires algorithm fallback; use an explicit standalone baseline operation instead of mislabelling the stored model")
            predicted[method] = result.days
            warnings.extend(result.warnings)
        else:
            if not history.days or cutoff != history.days[-1].date:
                raise ValueError("frozen ML inference requires an observation through as_of; stale gaps must be filled with verified observations or an explicit baseline operation")
            if any(max(day.inflow_cents, day.outflow_cents) > 2**53 - 1 for day in history.days):
                raise ValueError("new monetary values exceed the exact float64 range for the frozen ML model")
            from .models import recursive_predictions
            predicted[method] = recursive_predictions(bundle.fitted_candidates[method], history, horizon_days)
    fresh_evidence = unchanged and (not history.days or cutoff == history.days[-1].date)
    rows = []
    if metadata.inflow.method is not None and metadata.outflow.method is not None:
        for inflow, outflow in zip(predicted[metadata.inflow.method], predicted[metadata.outflow.method]):
            rows.append(SelectedPredictionDay(
                date=inflow.date, horizon=inflow.horizon,
                predicted_inflow_cents=inflow.predicted_inflow_cents,
                predicted_outflow_cents=outflow.predicted_outflow_cents,
                inflow_method=inflow.effective_method, outflow_method=outflow.effective_method,
                has_minimum_evidence=fresh_evidence and inflow.horizon in metadata.evaluated_horizons,
            ))
    result = bundle.training_forecast.model_dump()
    result.update(as_of=cutoff, forecast_horizon_days=horizon_days, days=tuple(rows),
                  evaluated_horizons=tuple(value for value in metadata.evaluated_horizons if value <= horizon_days) if fresh_evidence else (),
                  reliability=bundle.training_forecast.reliability if fresh_evidence else "insufficient_evidence",
                  warnings=tuple(dict.fromkeys(warnings)))
    return ForecastResult.model_validate(result)
