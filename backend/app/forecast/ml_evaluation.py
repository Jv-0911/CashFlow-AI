"""Fair outer ML evaluation and cautious promotion through the Phase 2 interface."""

from datetime import date
from math import ceil, sqrt
from statistics import mean, stdev
from time import perf_counter

from .baselines import METHODS, _predict, forecast_context
from .evaluation import _direction_metrics
from .models import ML_METHODS, fit_ml_candidate, model_eligibility, recursive_predictions
from .schemas import (
    BacktestPoint, BacktestResult, BaselineConfig, BaselineScore, CandidateEligibility, DailyHistory,
    ForecastResult, HorizonEvaluation, MLConfig, MethodEvaluation, SelectedPredictionDay,
)
from .selection import _select, forecast_baselines


def _prefix(history, index):
    return DailyHistory(currency=history.currency, days=history.days[:index + 1], complete_coverage=True,
                        coverage_start=history.coverage_start, coverage_end=history.days[index].date)


def _comparison_origins(history, horizon, ml_config, minimum_windows):
    eligibility, admitted, requirements = [], [], {}
    step = max(ml_config.origin_step, horizon)
    for method in ML_METHODS:
        item = model_eligibility(history, method, ml_config)
        required = max(ml_config.ridge_minimum_days if method == "ridge" else ml_config.tree_minimum_days,
                       ml_config.minimum_training_samples + ml_config.inner_validation_days + 1)
        windows = list(range(required - 1, len(history.days) - horizon, step))
        if item.eligible and min(len(windows), ml_config.maximum_origins) < minimum_windows:
            item = CandidateEligibility(method=method, eligible=False,
                                        reason="Too few complete chronological windows for fair ML comparison at the requested horizon.")
        eligibility.append(item)
        if item.eligible:
            admitted.append(method)
            requirements[method] = required
    if not admitted:
        return (), tuple(eligibility), ()
    # Every admitted candidate and baseline trains at the same cutoffs.
    indices = tuple(range(max(requirements.values()) - 1, len(history.days) - horizon, step))[-ml_config.maximum_origins:]
    return indices, tuple(eligibility), tuple(admitted)


def _paired_advantage(candidate: MethodEvaluation, baseline: MethodEvaluation, direction: str, config: BaselineConfig, ml: MLConfig):
    candidate_metrics = _direction_metrics(candidate.points, direction, config)
    baseline_metrics = _direction_metrics(baseline.points, direction, config)
    if candidate_metrics.mae_cents is None or baseline_metrics.mae_cents is None:
        return False, "Missing held-out metrics; cannot promote ML."
    margin = max(ml.minimum_improvement_cents, ml.minimum_improvement_relative * baseline_metrics.mae_cents)
    origins = sorted({point.origin for point in baseline.points})
    improvements = []
    for origin in origins:
        losses = []
        for evaluation in (baseline, candidate):
            losses.append(mean(abs(getattr(point, f"predicted_{direction}_cents") - getattr(point, f"actual_{direction}_cents"))
                               for point in evaluation.points if point.origin == origin))
        improvements.append(losses[0] - losses[1])
    if len(improvements) < ml.minimum_comparison_windows:
        return False, "Too few paired origins; cannot promote ML."
    mean_gain = mean(improvements)
    # Conservative diagnostic guard, not a calibrated significance test.
    noise_guard = 2 * stdev(improvements) / sqrt(len(improvements))
    if mean_gain <= max(margin, noise_guard):
        return False, f"Paired MAE gain {mean_gain:.3f} cents does not exceed improvement/noise guard {max(margin, noise_guard):.3f}."
    if sum(gain > 0 for gain in improvements) < ceil(2 * len(improvements) / 3):
        return False, "ML does not improve at least two-thirds of paired origins."
    for ml_horizon, base_horizon in zip(candidate.horizons, baseline.horizons):
        metric, reference = getattr(ml_horizon, direction), getattr(base_horizon, direction)
        if metric.mae_cents > reference.mae_cents + margin:
            return False, f"ML worsens horizon +{ml_horizon.horizon} beyond tolerance."
    if abs(candidate_metrics.bias_cents) > abs(baseline_metrics.bias_cents) + margin:
        return False, "ML bias worsens beyond improvement tolerance."
    if candidate_metrics.absolute_error_std_cents > baseline_metrics.absolute_error_std_cents + margin:
        return False, "ML error dispersion worsens beyond improvement tolerance."
    return True, f"Paired held-out MAE gain={mean_gain:.3f} cents; guard={max(margin, noise_guard):.3f}; no material lead, bias, or stability regression."


def forecast_models(
    history: DailyHistory, *, horizon_days: int = 2, config: BaselineConfig | None = None,
    ml_config: MLConfig | None = None, as_of: date | None = None,
) -> ForecastResult:
    config = BaselineConfig.model_validate((config or BaselineConfig()).model_dump())
    ml = MLConfig.model_validate((ml_config or MLConfig()).model_dump())
    history, horizon_days, cutoff, history_warnings = forecast_context(history, horizon_days, as_of)
    minimum_windows = max(config.minimum_evaluation_windows, ml.minimum_comparison_windows)
    indices, eligibility, admitted = _comparison_origins(history, horizon_days, ml, minimum_windows)
    if cutoff is not None and history.days and cutoff != history.days[-1].date:
        eligibility = tuple(CandidateEligibility(method=method, eligible=False, reason="ML inference does not support a stale-data gap; baseline dates are preserved.") for method in ML_METHODS)
        admitted = ()
    if not admitted:
        baseline = forecast_baselines(history, horizon_days=horizon_days, config=config, as_of=as_of)
        seasonal = ("History covers less than one annual cycle; annual seasonal effects are unestablished.",) if history.days and (history.days[-1].date - history.days[0].date).days < 365 else ()
        return baseline.model_copy(update={"model_eligibility": eligibility,
            "warnings": baseline.warnings + tuple(f"{item.method}: {item.reason}" for item in eligibility) + seasonal})
    actuals = {day.date: day for day in history.days}
    points = {method: [] for method in METHODS + admitted}
    reports = {method: [] for method in points}
    fit_times = {method: 0.0 for method in points}
    inference_times = {method: 0.0 for method in points}
    failures = {}
    for index in indices:
        training = _prefix(history, index)
        origin = training.days[-1].date
        for method in points:
            if method in failures:
                continue
            started = perf_counter()
            if method in METHODS:
                predicted = _predict(training, horizon_days, origin, method, config, ()).days
                inference_times[method] += perf_counter() - started
            else:
                try:
                    fitted = fit_ml_candidate(training, method=method, config=ml)
                    fit_times[method] += fitted.fit_seconds
                    reports[method].extend(fitted.feature_reports)
                    started = perf_counter()
                    predicted = recursive_predictions(fitted, training, horizon_days)
                    inference_times[method] += perf_counter() - started
                except ValueError as exc:
                    failures[method] = f"ML numerical/feature validation failed: {exc}"
                    points[method] = []  # Never compare a candidate on fewer windows.
                    continue
            for day in predicted:
                actual = actuals[day.date]
                points[method].append(BacktestPoint(
                    origin=origin, date=day.date, horizon=day.horizon,
                    actual_inflow_cents=actual.inflow_cents, actual_outflow_cents=actual.outflow_cents,
                    predicted_inflow_cents=day.predicted_inflow_cents, predicted_outflow_cents=day.predicted_outflow_cents,
                    effective_method=day.effective_method,
                ))
    evaluations = {}
    for method, rows in points.items():
        horizons = []
        for horizon in range(1, horizon_days + 1):
            subset = [point for point in rows if point.horizon == horizon]
            horizons.append(HorizonEvaluation(horizon=horizon, inflow=_direction_metrics(subset, "inflow", config),
                outflow=_direction_metrics(subset, "outflow", config), has_minimum_evidence=len(subset) >= minimum_windows))
        evaluations[method] = MethodEvaluation(method=method, horizons=tuple(horizons), points=tuple(rows),
            fallback_observations=sum(point.effective_method != method for point in rows),
            fit_seconds=fit_times[method], inference_seconds=inference_times[method], fold_feature_reports=tuple(reports[method]))
    scores = []
    for method, evaluation in evaluations.items():
        eligible = all(item.has_minimum_evidence for item in evaluation.horizons) and not evaluation.fallback_observations
        scores.append(BaselineScore(method=method, eligible=eligible, reason=failures.get(method,
            "Eligible on identical complete outer windows." if eligible else "Insufficient common evidence or baseline fallback."),
            inflow=_direction_metrics(evaluation.points, "inflow", config), outflow=_direction_metrics(evaluation.points, "outflow", config)))
    selected, reasons = {}, []
    baseline_scores = [score for score in scores if score.method in METHODS]
    if not any(score.eligible for score in baseline_scores):
        baseline = forecast_baselines(history, horizon_days=horizon_days, config=config, as_of=as_of)
        return baseline.model_copy(update={"model_eligibility": eligibility,
            "warnings": baseline.warnings + ("Not enough common ML/baseline windows; retained Phase 2 selection.",)})
    evidence = {score.method: {} for score in scores}
    for direction in ("inflow", "outflow"):
        baseline_method, baseline_reason = _select(baseline_scores, direction, config)
        allowed = [score for score in baseline_scores if score.eligible]
        for score in scores:
            if score.method in METHODS or not score.eligible:
                continue
            promotes, why = _paired_advantage(evaluations[score.method], evaluations[baseline_method], direction, config, ml)
            evidence[score.method][direction] = why
            if promotes:
                allowed.append(score)
        chosen, why = _select(allowed, direction, config, complexity_order=METHODS + ML_METHODS)
        selected[direction] = chosen
        reasons.append(why + (" " + evidence[chosen][direction] if chosen in ML_METHODS else " ML did not establish a sufficient advantage over this baseline."))
    scores = [score.model_copy(update={"selection_evidence": evidence[score.method]}) for score in scores]
    predictions, final_reports = {}, []
    # Fit selected candidates only; at most one fitted pair per selected method.
    for method in dict.fromkeys(selected.values()):
        if method in METHODS:
            predictions[method] = _predict(history, horizon_days, cutoff, method, config, ()).days
        else:
            fitted = fit_ml_candidate(history, method=method, config=ml)
            predictions[method] = recursive_predictions(fitted, history, horizon_days)
            final_reports.extend(report for report in fitted.feature_reports if selected[report.direction] == method)
    days = tuple(SelectedPredictionDay(
        date=inflow.date, horizon=inflow.horizon, predicted_inflow_cents=inflow.predicted_inflow_cents,
        predicted_outflow_cents=outflow.predicted_outflow_cents, inflow_method=inflow.effective_method,
        outflow_method=outflow.effective_method, has_minimum_evidence=True,
    ) for inflow, outflow in zip(predictions[selected["inflow"]], predictions[selected["outflow"]]))
    warnings = list(history_warnings)
    warnings.extend(f"{method}: {reason}" for method, reason in failures.items())
    warnings.extend(f"{item.method}: {item.reason}" for item in eligibility if not item.eligible)
    warnings.extend((
        "Outer scores are held-out relative to feature selection, but selection of the final model uses these scores; this is not an independent final-performance holdout.",
        "Paired improvement guards are conservative diagnostics, not calibrated statistical significance or confidence scores.",
        "Negative raw ML predictions are clipped to zero and rounded to integer cents; recursive errors can accumulate.",
        "Prediction intervals are not estimated; historical errors do not guarantee future accuracy.",
    ))
    if (history.days[-1].date - history.days[0].date).days < 365:
        warnings.append("History covers less than one annual cycle; annual seasonal effects are unestablished.")
    backtest = BacktestResult(currency=history.currency, forecast_horizon_days=horizon_days,
        status="evaluated", config=config, ml_config=ml, origins=tuple(history.days[index].date for index in indices),
        skipped_unknown_targets=0, methods=tuple(evaluations.values()), warnings=tuple(warnings))
    eligibility = tuple(CandidateEligibility(method=item.method, eligible=False, reason=failures[item.method]) if item.method in failures else item for item in eligibility)
    return ForecastResult(currency=history.currency, as_of=cutoff, forecast_horizon_days=horizon_days,
        status="forecast", reliability="limited_backtest_evidence", selected_inflow_model=selected["inflow"],
        selected_outflow_model=selected["outflow"], selection_basis="chronological_backtest", selection_reasons=tuple(reasons),
        days=days, evaluated_horizons=tuple(range(1, horizon_days + 1)),
        inflow_evaluation=evaluations[selected["inflow"]].horizons, outflow_evaluation=evaluations[selected["outflow"]].horizons,
        comparison=tuple(scores), backtest=backtest, warnings=tuple(dict.fromkeys(warnings)),
        model_eligibility=eligibility, feature_reports=tuple(final_reports))
