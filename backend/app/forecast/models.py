"""Small CPU-only estimators; nested feature-group choice precedes each outer forecast."""

from dataclasses import dataclass
from datetime import date, timedelta
from math import floor, isfinite
from time import perf_counter

import numpy as np
from pydantic import TypeAdapter
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from .baselines import forecast_context, validate_history
from .features import CALENDAR_FEATURES, FEATURE_NAMES, HISTORY_FEATURES, OPTIONAL_FIELDS, TrainingFeatureFilter, build_training_data, feature_row
from .schemas import CandidateEligibility, DailyCash, DailyHistory, FeatureReport, MLConfig, MLMethod, MLPrediction, PredictionDay


ML_METHODS = ("ridge", "random_forest", "hist_gradient_boosting")


def model_eligibility(history: DailyHistory, method: MLMethod, config: MLConfig) -> CandidateEligibility:
    method = TypeAdapter(MLMethod).validate_python(method)
    history = validate_history(history)
    config = MLConfig.model_validate(config.model_dump())
    minimum = config.ridge_minimum_days if method == "ridge" else config.tree_minimum_days
    reason = "Eligible historical coverage and usable training count."
    if not history.complete_coverage:
        reason = "ML requires confirmed complete coverage; sparse or incomplete history uses baselines."
    elif len(history.days) < minimum:
        reason = f"Requires at least {minimum} known daily observations."
    elif len(history.days) - 1 - config.inner_validation_days < config.minimum_training_samples:
        reason = "Too few training samples for the nested chronological feature comparison."
    elif any(max(day.inflow_cents, day.outflow_cents) > 2**53 - 1 for day in history.days):
        reason = "Amounts exceed the exact integer range of float64; use integer baselines."
    return CandidateEligibility(method=method, eligible=reason.startswith("Eligible"), reason=reason)


@dataclass
class FittedSeries:
    pipeline: Pipeline
    indices: tuple[int, ...]
    group: str


@dataclass
class FittedCandidate:
    method: MLMethod
    series: dict[str, FittedSeries]
    feature_reports: tuple[FeatureReport, ...]
    fit_seconds: float


def _fit_series(X, y, method, group, config, direction):
    # Separate activity histories keep mixed-model recursive inference coherent.
    names = CALENDAR_FEATURES if group == "calendar" else CALENDAR_FEATURES + tuple(name for name in HISTORY_FEATURES if name.startswith(direction + "_"))
    indices = tuple(FEATURE_NAMES.index(name) for name in names)
    if method == "ridge":
        estimator = Ridge(alpha=0.1)
    elif method == "random_forest":
        estimator = RandomForestRegressor(n_estimators=24, max_depth=5, min_samples_leaf=3,
                                           n_jobs=1, random_state=config.random_seed)
    elif method == "hist_gradient_boosting":
        # No random internal holdout: all validation is chronological outside the estimator.
        estimator = HistGradientBoostingRegressor(max_iter=50, max_depth=3, max_leaf_nodes=15,
                                                 min_samples_leaf=8, learning_rate=0.08,
                                                 l2_regularization=0.1, early_stopping=False,
                                                 random_state=config.random_seed)
    else:
        raise ValueError("unsupported ML method")
    steps = [("features", TrainingFeatureFilter(names, config.maximum_missing_fraction)),
             ("imputer", SimpleImputer(strategy="median"))]
    if method == "ridge":
        steps.append(("scaler", StandardScaler()))
    steps.append(("model", estimator))
    pipeline = Pipeline(steps)
    with threadpool_limits(limits=1):
        pipeline.fit(X[:, indices], y)
    return FittedSeries(pipeline, indices, group)


def prediction_cents(value: float) -> int:
    """Clip negative gross predictions; reject nonfinite/unsafe values, round half up."""
    if not isfinite(value) or abs(value) > 2**53 - 1:
        raise ValueError("ML prediction is not finite or exceeds the safe float64 monetary range")
    clipped = max(0.0, value)
    whole = floor(clipped)
    return whole + int(clipped - whole >= 0.5)


def recursive_predictions(
    fitted: FittedCandidate, history: DailyHistory, horizon_days: int,
) -> tuple[PredictionDay, ...]:
    observed = {day.date: day for day in history.days}
    cutoff = history.days[-1].date
    results = []
    for horizon in range(1, horizon_days + 1):
        target = cutoff + timedelta(days=horizon)
        row = feature_row(target, observed, history.days[0].date)
        values = np.asarray([[row[name] for name in FEATURE_NAMES]])
        predicted = {}
        for direction, series in fitted.series.items():
            with threadpool_limits(limits=1):
                raw = float(series.pipeline.predict(values[:, series.indices])[0])
            predicted[direction] = prediction_cents(raw)
        results.append(PredictionDay(date=target, horizon=horizon, effective_method=fitted.method,
                                     predicted_inflow_cents=predicted["inflow"], predicted_outflow_cents=predicted["outflow"]))
        # This local record is a generated value, never an actual from the forecast window.
        observed[target] = DailyCash(date=target, currency=history.currency,
                                    inflow_cents=predicted["inflow"], outflow_cents=predicted["outflow"])
    return tuple(results)


def fit_ml_candidate(history: DailyHistory, *, method: MLMethod, config: MLConfig | None = None) -> FittedCandidate:
    config = MLConfig.model_validate((config or MLConfig()).model_dump())
    history = validate_history(history)
    eligible = model_eligibility(history, method, config)
    if not eligible.eligible:
        raise ValueError(eligible.reason)
    started = perf_counter()
    holdout = history.days[-config.inner_validation_days:]
    inner = DailyHistory(currency=history.currency, days=history.days[:-config.inner_validation_days],
                         complete_coverage=True, coverage_start=history.coverage_start,
                         coverage_end=history.days[-config.inner_validation_days - 1].date)
    X_inner, y_inner, _ = build_training_data(inner)
    group_scores = {"inflow": {}, "outflow": {}}
    # Exactly two groups, no search over individual feature subsets.
    for group in ("calendar", "calendar_and_history"):
        pair = {direction: _fit_series(X_inner, y_inner[direction], method, group, config, direction)
                for direction in ("inflow", "outflow")}
        temporary = FittedCandidate(method, pair, (), 0.0)
        predictions = recursive_predictions(temporary, inner, len(holdout))
        for direction in pair:
            group_scores[direction][group] = sum(
                abs(getattr(prediction, f"predicted_{direction}_cents") - getattr(actual, f"{direction}_cents"))
                for prediction, actual in zip(predictions, holdout)
            ) / len(holdout)
    X, targets, _ = build_training_data(history)
    fitted, reports = {}, []
    for direction in ("inflow", "outflow"):
        scores = group_scores[direction]
        margin = max(config.minimum_improvement_cents, scores["calendar"] * config.minimum_improvement_relative)
        group = "calendar_and_history" if scores["calendar"] - scores["calendar_and_history"] > margin else "calendar"
        series = _fit_series(X, targets[direction], method, group, config, direction)
        fitted[direction] = series
        selector = series.pipeline.named_steps["features"]
        estimator = series.pipeline.named_steps["model"]
        excluded = dict(selector.excluded_features_)
        if group == "calendar":
            excluded.update({name: "history group did not establish sufficient inner chronological improvement" for name in HISTORY_FEATURES})
        else:
            excluded.update({name: "other cash direction excluded to keep separate recursive predictors consistent" for name in HISTORY_FEATURES if not name.startswith(direction + "_")})
        excluded.update({name: "not provided by DailyHistory with known-ahead availability" for name in OPTIONAL_FIELDS})
        importance = getattr(estimator, "coef_", getattr(estimator, "feature_importances_", None))
        importance = {} if importance is None else dict(zip(selector.selected_features_, map(float, np.ravel(importance))))
        reports.append(FeatureReport(
            method=method, direction=direction, training_start=history.days[0].date,
            training_end=history.days[-1].date, usable_observations=len(X), feature_group=group,
            selected_features=selector.selected_features_, excluded_features=excluded,
            availability={name: "calendar_known_ahead" if name in CALENDAR_FEATURES else "observed_or_recursively_generated_before_target" for name in selector.selected_features_},
            training_importance=importance, inner_validation_mae_cents=scores,
            warnings=("Coefficients and impurity importance are training diagnostics, not causal or out-of-sample feature proof.",
                      "Inner feature-group validation is separate from the outer model-comparison outcomes."),
        ))
    return FittedCandidate(method, fitted, tuple(reports), perf_counter() - started)


def predict_ml_candidate(
    history: DailyHistory, *, method: MLMethod, horizon_days: int = 2, config: MLConfig | None = None,
) -> MLPrediction:
    history, horizon_days, cutoff, _ = forecast_context(history, horizon_days, None)
    fitted = fit_ml_candidate(history, method=method, config=config)
    started = perf_counter()
    days = recursive_predictions(fitted, history, horizon_days)
    return MLPrediction(currency=history.currency, as_of=cutoff, forecast_horizon_days=horizon_days,
                        method=method, days=days, feature_reports=fitted.feature_reports,
                        fit_seconds=fitted.fit_seconds, inference_seconds=perf_counter() - started)
