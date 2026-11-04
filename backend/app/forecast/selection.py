"""Select inflow/outflow baselines from held-out errors, or return an honest fallback."""

from datetime import date

from .baselines import METHODS, _predict, forecast_context
from .evaluation import _direction_metrics, rolling_origin_backtest
from .schemas import (
    BaselineConfig, BaselineScore, DailyHistory, ForecastMethod, ForecastResult, MLConfig, SelectedPredictionDay,
)


def _select(scores: list[BaselineScore], direction: str, config: BaselineConfig, complexity_order=METHODS) -> tuple[ForecastMethod, str]:
    eligible = [score for score in scores if score.eligible and all(
        getattr(getattr(score, direction), name) is not None
        for name in ("mae_cents", "bias_cents", "absolute_error_std_cents")
    )]
    if not eligible:
        raise ValueError("No eligible method with complete held-out metrics")
    best_mae = min(getattr(score, direction).mae_cents for score in eligible)
    tolerance = max(config.mae_tie_absolute_cents, config.mae_tie_relative * best_mae)
    near_best = [score for score in eligible if getattr(score, direction).mae_cents <= best_mae + tolerance]
    # Bias and temporal error dispersion can separate methods with effectively equal MAE.
    best_bias = min(abs(getattr(score, direction).bias_cents) for score in near_best)
    near_best = [score for score in near_best if abs(getattr(score, direction).bias_cents) <= best_bias + tolerance]
    best_stability = min(getattr(score, direction).absolute_error_std_cents for score in near_best)
    near_best = [score for score in near_best if getattr(score, direction).absolute_error_std_cents <= best_stability + tolerance]
    chosen = min(near_best, key=lambda score: complexity_order.index(score.method))
    return chosen.method, (
        f"{direction}: {chosen.method} selected from chronological MAE, then absolute bias and error dispersion; "
        f"simpler methods win within {tolerance:.3f} cents tolerance. "
        f"Selected held-out MAE={getattr(chosen, direction).mae_cents:.3f} cents."
    )


def forecast_baselines(
    history: DailyHistory, *, horizon_days: int = 2, config: BaselineConfig | None = None,
    as_of: date | None = None,
    ml_config: MLConfig | None = None,
) -> ForecastResult:
    """Compare baselines and preserve the requested dates, even when evidence is limited."""
    if ml_config is not None:
        from .ml_evaluation import forecast_models
        return forecast_models(history, horizon_days=horizon_days, config=config, ml_config=ml_config, as_of=as_of)
    config = BaselineConfig.model_validate((config or BaselineConfig()).model_dump())
    history, horizon_days, cutoff, history_warnings = forecast_context(history, horizon_days, as_of)
    backtest = rolling_origin_backtest(history, horizon_days=horizon_days, config=config)
    warnings = list(history_warnings + backtest.warnings)
    supported = tuple(score.horizon for score in backtest.methods[0].horizons if score.has_minimum_evidence)
    predictions = {method: _predict(history, horizon_days, cutoff, method, config, ()) for method in METHODS}
    scores = []
    for evaluation in backtest.methods:
        subset = [point for point in evaluation.points if point.horizon in supported]
        fallbacks = any(point.effective_method != evaluation.method for point in subset)
        future_fallback = any(day.effective_method != evaluation.method for day in predictions[evaluation.method].days)
        eligible = bool(supported) and not fallbacks and not future_fallback
        reason = "Eligible on common supported horizons without algorithm fallback."
        if not supported:
            reason = "Insufficient held-out evidence."
        elif fallbacks or future_fallback:
            reason = "Insufficient method-specific history; fallback required in evaluation or requested forecast."
        scores.append(BaselineScore(
            method=evaluation.method, eligible=eligible, reason=reason,
            inflow=_direction_metrics(subset, "inflow", config),
            outflow=_direction_metrics(subset, "outflow", config),
        ))
    if not history.days:
        return ForecastResult(
            currency=history.currency, as_of=cutoff, forecast_horizon_days=horizon_days,
            status="insufficient_data", reliability="insufficient_data",
            selected_inflow_model=None, selected_outflow_model=None,
            selection_basis="no_history", selection_reasons=("No known daily history; no predictions returned.",),
            days=(), evaluated_horizons=(), inflow_evaluation=(), outflow_evaluation=(),
            comparison=tuple(scores), backtest=backtest,
            warnings=tuple(dict.fromkeys(warnings + ["No historical data; supply daily observations or explicitly covered zero-activity days."])),
        )
    if supported:
        inflow_model, inflow_reason = _select(scores, "inflow", config)
        outflow_model, outflow_reason = _select(scores, "outflow", config)
        basis = "chronological_backtest"
    else:
        inflow_model = outflow_model = "recent_value"
        inflow_reason = outflow_reason = "No defensible backtest comparison; recent_value is an explicitly unvalidated fallback."
        basis = "recent_value_fallback"
        warnings.append(inflow_reason)
    selected = {evaluation.method: evaluation.horizons for evaluation in backtest.methods}
    days = []
    for inflow, outflow in zip(predictions[inflow_model].days, predictions[outflow_model].days):
        days.append(SelectedPredictionDay(
            date=inflow.date, horizon=inflow.horizon,
            predicted_inflow_cents=inflow.predicted_inflow_cents,
            predicted_outflow_cents=outflow.predicted_outflow_cents,
            inflow_method=inflow.effective_method, outflow_method=outflow.effective_method,
            has_minimum_evidence=inflow.horizon in supported and cutoff == history.days[-1].date,
        ))
    if len(history.days) < config.minimum_history_days:
        warnings.append(f"Fewer than {config.minimum_history_days} known history days; predictions have insufficient evidence.")
    warnings.extend(predictions[inflow_model].warnings + predictions[outflow_model].warnings)
    if cutoff != history.days[-1].date:
        warnings.append("Backtesting uses origins at known dates and does not validate this stale-data forecasting gap.")
    reliable_enough = bool(supported) and len(supported) == horizon_days and history.complete_coverage and cutoff == history.days[-1].date
    warnings.append("Prediction intervals are not estimated in Phase 2; held-out errors are diagnostics, not confidence scores.")
    return ForecastResult(
        currency=history.currency, as_of=cutoff, forecast_horizon_days=horizon_days, status="forecast",
        reliability="limited_backtest_evidence" if reliable_enough else "insufficient_evidence",
        selected_inflow_model=inflow_model, selected_outflow_model=outflow_model,
        selection_basis=basis, selection_reasons=(inflow_reason, outflow_reason), days=tuple(days),
        evaluated_horizons=supported, inflow_evaluation=selected[inflow_model],
        outflow_evaluation=selected[outflow_model], comparison=tuple(scores), backtest=backtest,
        warnings=tuple(dict.fromkeys(warnings)),
    )
