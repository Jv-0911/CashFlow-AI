"""Descriptive held-out error envelopes; no calibrated coverage percentages are claimed."""

from datetime import timedelta

from .financial_schemas import (
    CashUncertainty, EmpiricalRange, HorizonUncertainty, ProjectedCashDay,
    ReconciliationReport, UncertaintyConfig,
)
from .schemas import DailyHistory, ForecastResult


def _unavailable(reason, count=0):
    return EmpiricalRange(status="unavailable", validation_samples=count, reason=reason)


def _range(center, residuals, minimum, *, nonnegative=False):
    if len(residuals) < minimum:
        return _unavailable(f"Need at least {minimum} non-overlapping held-out samples.", len(residuals))
    lower, upper = center + min(residuals), center + max(residuals)
    if nonnegative:
        lower, upper = max(0, lower), max(0, upper)
    return EmpiricalRange(status="approximate_empirical_range", lower_cents=lower,
                          upper_cents=upper, validation_samples=len(residuals))


def _points(forecast, method):
    evaluation = next((item for item in forecast.backtest.methods if item.method == method), None)
    points = {}
    if evaluation is None:
        return points
    for point in evaluation.points:
        if point.date != point.origin + timedelta(days=point.horizon) or point.origin >= point.date:
            raise ValueError("uncertainty requires correctly dated chronological backtest points")
        if forecast.as_of is None or point.date > forecast.as_of:
            raise ValueError("uncertainty must not use outcomes unavailable at the forecast cutoff")
        if point.effective_method != method:
            continue
        key = (point.origin, point.horizon)
        if key in points:
            raise ValueError("duplicate backtest origin/horizon in uncertainty input")
        points[key] = point
    return points


def estimate_cash_uncertainty(
    forecast: ForecastResult, history: DailyHistory, reconciliation: ReconciliationReport,
    days: tuple[ProjectedCashDay, ...], config: UncertaintyConfig,
) -> CashUncertainty:
    config = UncertaintyConfig.model_validate(config.model_dump())
    inflow = _points(forecast, forecast.selected_inflow_model)
    outflow = _points(forecast, forecast.selected_outflow_model)
    origins = sorted({origin for origin, _ in inflow} | {origin for origin, _ in outflow})
    current = bool(history.days) and history.days[-1].date == forecast.as_of
    evidence_by_horizon = {day.horizon: day.has_minimum_evidence for day in forecast.days}
    active = {
        "inflow": reconciliation.inflow_policy in ("aggregate_prediction", "category_residual"),
        "outflow": reconciliation.outflow_policy in ("aggregate_prediction", "category_residual"),
    }
    warnings = [
        "Ranges are observed held-out residual envelopes, not calibrated prediction intervals or coverage guarantees.",
        "Model selection used the backtest scores; these ranges are not an independent final calibration set.",
        "Balance ranges use complete paired error paths, preserving inflow/outflow and cross-day dependence.",
        "Known-event payment and timing uncertainty is excluded; all balance ranges are conditional on the supplied event assumptions.",
        "Limited seasons, future shocks, and zero historical spread may make empirical ranges optimistic.",
    ]
    result = []
    for day in days:
        available = current and history.complete_coverage and evidence_by_horizon.get(day.horizon, False)
        direction_ranges = {}
        for direction, points in (("inflow", inflow), ("outflow", outflow)):
            if not available or not active[direction]:
                direction_ranges[direction] = _unavailable("No applicable validated residual forecast, complete coverage, or current-data evidence.")
                continue
            residuals, last_target = [], None
            for origin in origins:
                point = points.get((origin, day.horizon))
                if point is None or last_target is not None and origin < last_target:
                    continue
                residuals.append(getattr(point, f"actual_{direction}_cents") - getattr(point, f"predicted_{direction}_cents"))
                # Retain disjoint forecast windows rather than count overlapping targets as independent evidence.
                last_target = point.date
            direction_ranges[direction] = _range(getattr(day, f"predicted_residual_{direction}_cents"), residuals,
                                                 config.minimum_samples, nonnegative=True)
        path_errors, last_target = [], None
        if available and all(active.values()) and reconciliation.fully_reconciled:
            for origin in origins:
                if last_target is not None and origin < last_target:
                    continue
                keys = [(origin, horizon) for horizon in range(1, day.horizon + 1)]
                if any(key not in inflow or key not in outflow for key in keys):
                    continue
                if any(inflow[key].date != outflow[key].date or inflow[key].actual_inflow_cents != outflow[key].actual_inflow_cents
                       or inflow[key].actual_outflow_cents != outflow[key].actual_outflow_cents for key in keys):
                    raise ValueError("paired balance paths must share the same actual outcomes")
                path_errors.append(sum(
                    (inflow[key].actual_inflow_cents - inflow[key].predicted_inflow_cents)
                    - (outflow[key].actual_outflow_cents - outflow[key].predicted_outflow_cents)
                    for key in keys
                ))
                last_target = origin + timedelta(days=day.horizon)
            balance_range = _range(day.projected_closing_balance_cents, path_errors, config.minimum_samples)
        else:
            balance_range = _unavailable("Cumulative uncertainty requires both applicable residual forecasts, current complete data, and fully resolved reconciliation.")
        result.append(HorizonUncertainty(horizon=day.horizon, date=day.date,
            residual_inflow=direction_ranges["inflow"], residual_outflow=direction_ranges["outflow"],
            projected_closing_balance=balance_range))
    statuses = [item.status for row in result for item in (row.residual_inflow, row.residual_outflow, row.projected_closing_balance)]
    count = statuses.count("approximate_empirical_range")
    if not count:
        warnings.append("Uncertainty is unavailable: no sufficient applicable residual/path samples; no bounds were fabricated.")
    return CashUncertainty(status="approximate_empirical_ranges" if count == len(statuses) else "partially_available" if count else "unavailable",
        intervals_available=bool(count), horizons=tuple(result), warnings=tuple(warnings))
