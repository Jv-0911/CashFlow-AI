"""Deterministic historical baselines, with explicit missing-date and fallback rules."""

from datetime import date, timedelta

from pydantic import TypeAdapter

from .schemas import (
    BaselineConfig, BaselineMethod, BaselinePrediction, DailyHistory, Horizon, PredictionDay,
)


METHODS: tuple[BaselineMethod, ...] = ("recent_value", "moving_average", "seasonal_naive")


def validate_history(history: DailyHistory) -> DailyHistory:
    """Validate cross-record invariants not enforced by the Phase 1 data container."""
    history = DailyHistory.model_validate(history.model_dump())
    dates = [day.date for day in history.days]
    if dates != sorted(set(dates)):
        raise ValueError("daily history must have unique, chronological dates")
    if any(day.currency != history.currency for day in history.days):
        raise ValueError("daily history must contain one currency")
    evidence = [identifier for day in history.days for identifier in day.evidence_ids]
    if any(not identifier.strip() for identifier in evidence) or len(set(evidence)) != len(evidence):
        raise ValueError("historical evidence IDs must be nonblank and unique across days")
    if history.complete_coverage:
        if history.coverage_start is None or history.coverage_end is None:
            raise ValueError("complete history requires both coverage dates")
        span = (history.coverage_end - history.coverage_start).days + 1
        if span < 1 or len(dates) != span or not dates:
            raise ValueError("complete history must explicitly include every covered day, including zeros")
        if dates[0] != history.coverage_start or dates[-1] != history.coverage_end:
            raise ValueError("complete history does not match its coverage bounds")
    elif history.coverage_start is not None or history.coverage_end is not None:
        raise ValueError("coverage bounds require complete_coverage=True")
    return history


def forecast_context(
    history: DailyHistory, horizon_days: int, as_of: date | None,
) -> tuple[DailyHistory, int, date | None, tuple[str, ...]]:
    history = validate_history(history)
    horizon_days = TypeAdapter(Horizon).validate_python(horizon_days)
    if as_of is not None and type(as_of) is not date:
        raise ValueError("as_of must be a date without time")
    last = history.days[-1].date if history.days else None
    cutoff = as_of if as_of is not None else last
    if last is not None and cutoff < last:
        raise ValueError("history contains observations after as_of; explicitly slice history first")
    if cutoff is not None:
        try:
            cutoff + timedelta(days=horizon_days)
        except OverflowError as exc:
            raise ValueError("forecast extends beyond supported dates") from exc
    warnings = list(history.warnings)
    if not history.complete_coverage:
        warnings.append("Historical coverage is unconfirmed; unknown days are not zero-filled and recorded-day totals may be incomplete.")
    if last is not None and cutoff > last:
        warnings.append(f"Latest observation is {(cutoff - last).days} days before as_of; data is stale.")
    return history, horizon_days, cutoff, tuple(dict.fromkeys(warnings))


def _average(values: list[int]) -> int:
    """Exact nonnegative mean rounded to nearest cent, with half cents rounded up."""
    return (2 * sum(values) + len(values)) // (2 * len(values))


def _predict(
    history: DailyHistory, horizon_days: int, cutoff: date | None,
    method: BaselineMethod, config: BaselineConfig, warnings: tuple[str, ...],
) -> BaselinePrediction:
    """Internal primitive reused by backtesting after one history validation."""
    if not history.days:
        return BaselinePrediction(
            currency=history.currency, as_of=cutoff, forecast_horizon_days=horizon_days,
            method=method, status="insufficient_data", days=(),
            warnings=warnings + ("No known daily observations; no predictions were manufactured.",),
        )
    by_date = {day.date: day for day in history.days}
    # A trailing calendar window must contain every date; sparse rows are not a window.
    trailing = [by_date.get(cutoff - timedelta(days=offset))
                for offset in range(min(config.moving_average_window, (cutoff - date.min).days + 1))]
    moving_available = len(trailing) == config.moving_average_window and all(day is not None for day in trailing)
    moving = [day for day in trailing if day is not None]
    recent = history.days[-1]
    weekdays = {weekday: [day for day in history.days if day.date.weekday() == weekday][-config.weekday_samples:]
                for weekday in range(7)}
    messages = list(warnings)
    days: list[PredictionDay] = []
    for horizon in range(1, horizon_days + 1):
        target = cutoff + timedelta(days=horizon)
        effective = method
        samples = [recent]
        if method == "moving_average":
            if moving_available:
                samples = moving
            else:
                effective = "recent_value"
                messages.append(f"Moving average requires {config.moving_average_window} contiguous known days through as_of; using recent_value.")
        elif method == "seasonal_naive":
            comparable = weekdays[target.weekday()]
            if len(comparable) == config.weekday_samples:
                samples = comparable
                if (cutoff - comparable[-1].date).days >= 7:
                    messages.append(f"Comparable weekday history for {target.isoformat()} is stale due to unknown days.")
            else:
                effective = "moving_average" if moving_available else "recent_value"
                samples = moving if moving_available else [recent]
                messages.append(f"Day +{horizon} has fewer than {config.weekday_samples} known matching weekdays; using {effective}.")
        days.append(PredictionDay(
            date=target, horizon=horizon, predicted_inflow_cents=_average([day.inflow_cents for day in samples]),
            predicted_outflow_cents=_average([day.outflow_cents for day in samples]), effective_method=effective,
        ))
    return BaselinePrediction(
        currency=history.currency, as_of=cutoff, forecast_horizon_days=horizon_days,
        method=method, status="predicted", days=tuple(days), warnings=tuple(dict.fromkeys(messages)),
    )


def predict_baseline(
    history: DailyHistory, *, method: BaselineMethod, horizon_days: int = 2,
    config: BaselineConfig | None = None, as_of: date | None = None,
) -> BaselinePrediction:
    """Predict days +1 through +horizon from historical information only."""
    method = TypeAdapter(BaselineMethod).validate_python(method)
    config = BaselineConfig.model_validate((config or BaselineConfig()).model_dump())
    history, horizon_days, cutoff, warnings = forecast_context(history, horizon_days, as_of)
    if len(history.days) < config.minimum_history_days:
        warnings += (f"Fewer than {config.minimum_history_days} known days; predictions are an unvalidated fallback.",)
    return _predict(history, horizon_days, cutoff, method, config, warnings)
