"""Unified conditional financial projections, without provider operations or AI recommendations."""

import hashlib
from datetime import date, timedelta
from typing import TYPE_CHECKING

from .engine import calculate_balances
from .financial_schemas import CashForecastRequest, CashForecastResult, KnownEventEffect, ProjectedCashDay, ShortageEvidence
from .reconciliation import reconcile_history
from .schemas import DailyCash
from .selection import forecast_baselines
from .uncertainty import estimate_cash_uncertainty

if TYPE_CHECKING:
    from .trained import TrainedForecastModel


def _forecast_identifier(request, artifact_id=None, model_version=None, model_days=()):
    identity = request.model_dump_json()
    if artifact_id is not None:
        identity += "|" + artifact_id + "|" + model_version + "|" + repr(tuple(
            (day.date.isoformat(), day.predicted_inflow_cents, day.predicted_outflow_cents) for day in model_days))
    return "cash_forecast_" + hashlib.sha256(identity.encode()).hexdigest()[:20]


def forecast_cash_flow(request: CashForecastRequest, *, trained_model: "TrainedForecastModel | None" = None) -> CashForecastResult:
    request = CashForecastRequest.model_validate(request.model_dump())
    start = request.forecast_start_date
    if start == date.min:
        raise ValueError("forecast start must allow a preceding historical cutoff date")
    try:
        forecast_dates = tuple(start + timedelta(days=i) for i in range(request.forecast_horizon_days))
    except OverflowError as exc:
        raise ValueError("forecast extends beyond supported dates") from exc
    if request.opening_balance.balance_date != start:
        raise ValueError("verified opening balance must be immediately before the requested start date")
    if request.opening_balance.currency != request.history.currency:
        raise ValueError("opening balance currency does not match historical currency")
    residual, reconciliation = reconcile_history(request)
    if trained_model is None:
        model = forecast_baselines(residual, horizon_days=request.forecast_horizon_days,
                                   config=request.baseline_config, ml_config=request.ml_config,
                                   as_of=start - timedelta(days=1))
    else:
        from .trained import forecast_trained_model
        if request.baseline_config != trained_model.metadata.baseline_config or request.ml_config != trained_model.metadata.ml_config:
            raise ValueError("request model configuration must match the trained artifact")
        model = forecast_trained_model(trained_model, history=residual,
            horizon_days=request.forecast_horizon_days, as_of=start - timedelta(days=1))
    active = {
        "inflow": bool(model.days) and reconciliation.inflow_policy in ("aggregate_prediction", "category_residual"),
        "outflow": bool(model.days) and reconciliation.outflow_policy in ("aggregate_prediction", "category_residual"),
    }
    if model.days and tuple(day.date for day in model.days) != forecast_dates:
        raise ValueError("forecasting module did not preserve the requested forecast dates")
    model_days = {day.date: day for day in model.days}
    included = [item.event for item in reconciliation.event_dispositions if item.included]
    known = {day: {"inflow": 0, "outflow": 0, "ids": []} for day in forecast_dates}
    for event in included:
        known[event.expected_date][event.direction] += event.amount_cents
        known[event.expected_date]["ids"].append(event.event_id)
    supplied, components = [], {}
    for day, movements in known.items():
        prediction = model_days.get(day)
        inflow = prediction.predicted_inflow_cents if active["inflow"] else 0
        outflow = prediction.predicted_outflow_cents if active["outflow"] else 0
        components[day] = (inflow, outflow)
        supplied.append(DailyCash(date=day, currency=residual.currency,
            inflow_cents=inflow + movements["inflow"], outflow_cents=outflow + movements["outflow"], evidence_ids=tuple(movements["ids"])))
    balance = calculate_balances(supplied, start_date=start, horizon_days=request.forecast_horizon_days,
        opening_balance_cents=request.opening_balance.balance_cents,
        safety_reserve_cents=request.safety_reserve_cents, currency=residual.currency)
    artifact_id = trained_model.metadata.model_id if trained_model is not None else None
    model_version = trained_model.metadata.model_version if trained_model is not None else None
    identifier = _forecast_identifier(request, artifact_id, model_version, model.days)
    projections = tuple(ProjectedCashDay(
        evidence_id=f"{identifier}_{day.date.isoformat()}", date=day.date, horizon=index + 1,
        opening_balance_cents=day.opening_balance_cents,
        predicted_residual_inflow_cents=components[day.date][0], predicted_residual_outflow_cents=components[day.date][1],
        known_expected_inflow_cents=known[day.date]["inflow"], known_expected_outflow_cents=known[day.date]["outflow"],
        known_net_cash_adjustment_cents=known[day.date]["inflow"] - known[day.date]["outflow"],
        projected_receipts_cents=day.receipts_cents, projected_payments_cents=day.expenses_cents,
        projected_closing_balance_cents=day.closing_balance_cents, below_safety_reserve=day.below_safety_reserve,
        reserve_shortfall_cents=day.shortfall_cents, known_event_ids=day.evidence_ids,
    ) for index, day in enumerate(balance.days))
    evidence = []
    for day in projections:
        if not day.below_safety_reserve:
            continue
        effects = []
        for event in included:
            if event.expected_date > day.date:
                continue
            signed = event.amount_cents if event.direction == "inflow" else -event.amount_cents
            without = day.projected_closing_balance_cents - signed
            effects.append(KnownEventEffect(event_id=event.event_id, source_id=event.source_id, status=event.status,
                expected_date=event.expected_date, signed_balance_effect_cents=signed,
                closing_balance_without_event_cents=without,
                reserve_shortfall_difference_cents=day.reserve_shortfall_cents - max(0, request.safety_reserve_cents - without),
                assumption=event.projection_assumption or "Scheduled expense paid on its supplied expected date."))
        evidence.append(ShortageEvidence(forecast_day_evidence_id=day.evidence_id, date=day.date,
            closing_balance_cents=day.projected_closing_balance_cents, reserve_shortfall_cents=day.reserve_shortfall_cents,
            known_event_effects=tuple(effects), opening_balance_evidence_id=request.opening_balance.evidence_id))
    uncertainty = estimate_cash_uncertainty(model, residual, reconciliation, projections, request.uncertainty_config)
    warnings = list(reconciliation.warnings + model.warnings + uncertainty.warnings)
    if reconciliation.status == "known_only_fallback":
        warnings.append("Known-only fallback is not a lower or upper cash bound: omitted receipts or expenses can change shortages. Unapplied aggregate model diagnostics do not describe residual activity.")
    if residual.days and (residual.days[-1].date - residual.days[0].date).days < 365:
        warnings.append("Historical coverage lacks a complete annual cycle; missing seasonal patterns remain unknown.")
    warnings.append("Input verification is a caller responsibility; this service preserves supplied statuses and never verifies or completes payments.")
    conditional_events = any(event.direction == "inflow" or event.status == "pending_verification" for event in included)
    risk_complete = reconciliation.fully_reconciled and residual.complete_coverage and bool(model.days) and all(day.has_minimum_evidence for day in model.days) and not conditional_events
    return CashForecastResult(
        forecast_id=identifier, request_fingerprint=_forecast_identifier(request),
        model_artifact_id=artifact_id, model_version=model_version,
        currency=residual.currency, business_timezone=request.business_timezone,
        forecast_start_date=start, forecast_horizon_days=request.forecast_horizon_days,
        opening_balance_cents=request.opening_balance.balance_cents, opening_balance_evidence_id=request.opening_balance.evidence_id,
        safety_reserve_cents=request.safety_reserve_cents,
        selected_inflow_model=model.selected_inflow_model if active["inflow"] else None,
        selected_outflow_model=model.selected_outflow_model if active["outflow"] else None,
        statistical_inflow_applied=active["inflow"], statistical_outflow_applied=active["outflow"],
        model_forecast=model, reconciliation=reconciliation, days=projections,
        first_reserve_breach_date=balance.first_reserve_breach_date,
        minimum_projected_cash_balance_cents=min(day.closing_balance_cents for day in balance.days),
        maximum_reserve_shortfall_cents=max(day.shortfall_cents for day in balance.days),
        days_below_reserve=sum(day.below_safety_reserve for day in balance.days), risk_assessment_complete=risk_complete,
        shortage_evidence=tuple(evidence), uncertainty=uncertainty,
        assumptions=(
            "Opening balance is caller-verified cash immediately before forecast_start_date in the configured business timezone.",
            "All dates are business-calendar dates; timestamps must be converted by the caller, never inferred here.",
            "Category coverage is an explicit caller attestation of the complete category schedule in the forecast window, including intentional zero activity.",
            "Unpaid or pending events remain estimates conditional on supplied collection and timing assumptions.",
            "Event effects hold other projections fixed and describe arithmetic differences, not causal findings or recommended actions.",
        ), warnings=tuple(dict.fromkeys(warnings)),
    )
