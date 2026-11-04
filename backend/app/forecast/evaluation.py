"""Rolling-origin baseline comparison; every prediction precedes its actual observation."""

from datetime import timedelta
from math import hypot, isfinite, sqrt
from typing import Sequence

from pydantic import TypeAdapter

from .baselines import METHODS, _predict, forecast_context
from .schemas import (
    BacktestPoint, BacktestResult, BaselineConfig, DailyHistory, ErrorMetrics,
    HorizonEvaluation, MethodEvaluation, NonNegativeCents, PositiveInt,
)


def calculate_metrics(
    actual: Sequence[int], predicted: Sequence[int], *, wape_minimum_actual_cents: int = 100,
) -> ErrorMetrics:
    """MAE/bias/std are cents; WAPE is a ratio, not accuracy. Bias is predicted - actual."""
    if len(actual) != len(predicted):
        raise ValueError("actual and predicted must have equal lengths")
    threshold = TypeAdapter(PositiveInt).validate_python(wape_minimum_actual_cents)
    values = TypeAdapter(tuple[NonNegativeCents, ...])
    actual = values.validate_python(tuple(actual))
    predicted = values.validate_python(tuple(predicted))
    if not actual:
        return ErrorMetrics(evaluated_observations=0, mae_cents=None, bias_cents=None,
                            absolute_error_std_cents=None, wape=None, wape_unavailable_reason="no_observations")
    errors = [prediction - observation for observation, prediction in zip(actual, predicted)]
    absolute = [abs(error) for error in errors]
    denominator = sum(actual)
    meaningful = denominator >= threshold
    try:
        mae = sum(absolute) / len(absolute)
        bias = sum(errors) / len(errors)
        # hypot avoids overflow from squaring otherwise representable errors.
        stability = hypot(*(error - mae for error in absolute)) / sqrt(len(absolute))
        wape = sum(absolute) / denominator if meaningful else None
        if not all(isfinite(value) for value in (mae, bias, stability) + (() if wape is None else (wape,))):
            raise OverflowError
    except OverflowError:
        return ErrorMetrics(evaluated_observations=len(actual), mae_cents=None, bias_cents=None,
            absolute_error_std_cents=None, wape=None, wape_unavailable_reason="numeric_range_exceeded")
    return ErrorMetrics(
        evaluated_observations=len(actual), mae_cents=mae, bias_cents=bias,
        absolute_error_std_cents=stability,
        wape=wape,
        wape_unavailable_reason=None if meaningful else "zero_or_near_zero_actuals",
    )


def _direction_metrics(points: Sequence[BacktestPoint], direction: str, config: BaselineConfig) -> ErrorMetrics:
    return calculate_metrics(
        [getattr(point, f"actual_{direction}_cents") for point in points],
        [getattr(point, f"predicted_{direction}_cents") for point in points],
        wape_minimum_actual_cents=config.wape_minimum_actual_cents,
    )


def rolling_origin_backtest(
    history: DailyHistory, *, horizon_days: int = 2, config: BaselineConfig | None = None,
) -> BacktestResult:
    """Compare all three methods on the same origins and known targets, never fill unknowns."""
    config = BaselineConfig.model_validate((config or BaselineConfig()).model_dump())
    history, horizon_days, _, history_warnings = forecast_context(history, horizon_days, None)
    # Use a common training requirement for a fair candidate comparison.
    minimum = max(config.minimum_history_days, config.moving_average_window, 7 * config.weekday_samples)
    actuals = {day.date: day for day in history.days}
    candidates = []
    for index in range(minimum - 1, len(history.days) - 1, config.origin_step):
        cutoff = history.days[index].date
        if any(cutoff + timedelta(days=offset) in actuals for offset in range(1, horizon_days + 1)):
            candidates.append(index)
    indices = candidates[-config.maximum_origins:]
    origins = tuple(history.days[index].date for index in indices)
    points = {method: [] for method in METHODS}
    skipped = 0
    for index, cutoff in zip(indices, origins):
        # Retain only training-time coverage metadata, never the full-data coverage end.
        training = DailyHistory(
            currency=history.currency, days=history.days[:index + 1],
            complete_coverage=history.complete_coverage,
            coverage_start=history.coverage_start if history.complete_coverage else None,
            coverage_end=cutoff if history.complete_coverage else None,
        )
        targets = {offset: actuals.get(cutoff + timedelta(days=offset)) for offset in range(1, horizon_days + 1)}
        skipped += sum(target is None for target in targets.values())
        for method in METHODS:
            prediction = _predict(training, horizon_days, cutoff, method, config, ())
            for day in prediction.days:
                actual = targets[day.horizon]
                if actual is None:
                    continue
                points[method].append(BacktestPoint(
                    origin=cutoff, date=day.date, horizon=day.horizon,
                    actual_inflow_cents=actual.inflow_cents, actual_outflow_cents=actual.outflow_cents,
                    predicted_inflow_cents=day.predicted_inflow_cents,
                    predicted_outflow_cents=day.predicted_outflow_cents,
                    effective_method=day.effective_method,
                ))
    methods = []
    for method in METHODS:
        scores = []
        for horizon in range(1, horizon_days + 1):
            subset = [point for point in points[method] if point.horizon == horizon]
            inflow, outflow = _direction_metrics(subset, "inflow", config), _direction_metrics(subset, "outflow", config)
            scores.append(HorizonEvaluation(
                horizon=horizon, inflow=inflow, outflow=outflow,
                has_minimum_evidence=len(subset) >= config.minimum_evaluation_windows and inflow.mae_cents is not None and outflow.mae_cents is not None,
            ))
        methods.append(MethodEvaluation(
            method=method, horizons=tuple(scores), points=tuple(points[method]),
            fallback_observations=sum(point.effective_method != method for point in points[method]),
        ))
    supported = [score.horizon for score in methods[0].horizons if score.has_minimum_evidence]
    warnings = list(history_warnings)
    if not supported:
        warnings.append(f"Insufficient chronological testing: need {minimum} known training days and {config.minimum_evaluation_windows} targets per horizon.")
    missing = [horizon for horizon in range(1, horizon_days + 1) if horizon not in supported]
    if missing:
        warnings.append(f"Insufficient evaluation windows for horizons {missing}; their accuracy is unestablished.")
    if skipped:
        warnings.append(f"Skipped {skipped} unknown or unavailable targets; none were scored as zero.")
    if len(candidates) > config.maximum_origins:
        warnings.append(f"Evaluation uses the most recent {config.maximum_origins} eligible origins.")
    warnings.append("Backtesting is descriptive, may use overlapping targets, and does not guarantee future accuracy or interval coverage.")
    return BacktestResult(
        currency=history.currency, forecast_horizon_days=horizon_days,
        status="evaluated" if supported else "insufficient_data", config=config,
        origins=origins, skipped_unknown_targets=skipped, methods=tuple(methods),
        warnings=tuple(dict.fromkeys(warnings)),
    )
