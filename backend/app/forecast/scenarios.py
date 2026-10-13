"""Deterministic, explicitly hypothetical adjustments over one fixed issued forecast."""

import hashlib
from datetime import timedelta

from .engine import calculate_balances
from .financial_schemas import (
    CashForecastRequest, CashForecastResult, EventDisposition, KnownEventEffect,
    ProjectedCashDay, ShortageEvidence,
)
from .reconciliation import reconcile_history
from .scenario_schemas import (
    AddEventOperation, ChangeExpenseAmountOperation, ChangeProjectionOperation,
    MoveEventOperation, RemoveEventOperation, ScenarioComparison, ScenarioDailyDifference,
    ScenarioEventChange, ScenarioProjectionChange, ScenarioRequest,
)
from .schemas import DailyCash
from .service import _forecast_identifier, forecast_cash_flow


_ELIGIBLE_STATUSES = {"invoice_unpaid", "pending_verification", "scheduled_expense", "overdue_receivable"}


def _validate_baseline(request, baseline, reconciliation):
    expected_id = _forecast_identifier(request, baseline.model_artifact_id, baseline.model_version, baseline.model_forecast.days)
    if baseline.forecast_id != expected_id:
        raise ValueError("baseline forecast does not belong to the supplied unchanged request")
    if baseline.request_fingerprint is not None and baseline.request_fingerprint != _forecast_identifier(request):
        raise ValueError("baseline request fingerprint does not match supplied request")
    if baseline.reconciliation != reconciliation:
        raise ValueError("baseline reconciliation does not match supplied request")
    if (baseline.currency != request.history.currency or
        baseline.forecast_start_date != request.forecast_start_date or
        baseline.forecast_horizon_days != request.forecast_horizon_days or
        baseline.opening_balance_cents != request.opening_balance.balance_cents or
        baseline.opening_balance_evidence_id != request.opening_balance.evidence_id or
        baseline.safety_reserve_cents != request.safety_reserve_cents):
        raise ValueError("baseline financial context does not match supplied request")
    expected_dates = tuple(request.forecast_start_date + timedelta(days=index)
                           for index in range(request.forecast_horizon_days))
    if tuple(day.date for day in baseline.days) != expected_dates:
        raise ValueError("baseline dates do not match forecast horizon")
    model = baseline.model_forecast
    if model.currency != baseline.currency or model.forecast_horizon_days != request.forecast_horizon_days:
        raise ValueError("baseline model context does not match financial projection")
    if model.days and tuple(day.date for day in model.days) != expected_dates:
        raise ValueError("baseline model dates do not match financial projection")
    model_days = {day.date: day for day in model.days}
    known = {day: {"inflow": 0, "outflow": 0, "ids": []} for day in expected_dates}
    for disposition in reconciliation.event_dispositions:
        if disposition.included:
            event = disposition.event
            known[event.expected_date][event.direction] += event.amount_cents
            known[event.expected_date]["ids"].append(event.event_id)
    opening = request.opening_balance.balance_cents
    for day in baseline.days:
        prediction = model_days.get(day.date)
        expected_inflow = prediction.predicted_inflow_cents if baseline.statistical_inflow_applied and prediction else 0
        expected_outflow = prediction.predicted_outflow_cents if baseline.statistical_outflow_applied and prediction else 0
        if (day.predicted_residual_inflow_cents != expected_inflow or
            day.predicted_residual_outflow_cents != expected_outflow or
            day.known_expected_inflow_cents != known[day.date]["inflow"] or
            day.known_expected_outflow_cents != known[day.date]["outflow"] or
            day.known_net_cash_adjustment_cents != known[day.date]["inflow"] - known[day.date]["outflow"] or
            day.known_event_ids != tuple(known[day.date]["ids"])):
            raise ValueError("baseline cash components do not match its model and supplied events")
        receipts = day.predicted_residual_inflow_cents + day.known_expected_inflow_cents
        payments = day.predicted_residual_outflow_cents + day.known_expected_outflow_cents
        closing = opening + receipts - payments
        if (day.opening_balance_cents != opening or day.projected_receipts_cents != receipts or
            day.projected_payments_cents != payments or day.projected_closing_balance_cents != closing or
            day.reserve_shortfall_cents != max(0, request.safety_reserve_cents - closing) or
            day.below_safety_reserve != (closing < request.safety_reserve_cents)):
            raise ValueError("baseline contains inconsistent financial arithmetic")
        opening = closing


def _shift_range(interval, shift, *, nonnegative=False):
    if interval.status == "unavailable":
        return interval
    lower, upper = interval.lower_cents + shift, interval.upper_cents + shift
    if nonnegative:
        lower, upper = max(0, lower), max(0, upper)
    return interval.model_copy(update={"lower_cents": lower, "upper_cents": upper})


def simulate_scenario(
    request: CashForecastRequest, scenario: ScenarioRequest, *, baseline: CashForecastResult | None = None,
) -> ScenarioComparison:
    """Compare assumed cash changes, without rescheduling, paying, verifying, or retraining.

    Existing events must already contribute to the baseline and have no historical identity
    link. Each event can be changed once. Newly added cash is explicitly incremental over
    the fixed baseline, including when its categories have not been reconciled.
    """
    request = CashForecastRequest.model_validate(request.model_dump())
    scenario = ScenarioRequest.model_validate(scenario.model_dump())
    if baseline is None:
        baseline = forecast_cash_flow(request)
    else:
        baseline = CashForecastResult.model_validate(baseline.model_dump())
    _, reconciliation = reconcile_history(request)
    _validate_baseline(request, baseline, reconciliation)
    start = request.forecast_start_date
    end = start + timedelta(days=request.forecast_horizon_days - 1)
    dispositions = {item.event.event_id: item for item in reconciliation.event_dispositions}
    active_events = {item.event.event_id: item.event for item in dispositions.values() if item.included}
    source_ids = {event.source_id for event in request.known_events}
    historical_ids = {identifier for day in request.history.days for identifier in day.evidence_ids}
    if request.historical_transactions is not None:
        historical_ids.update(tx.transaction_id for tx in request.historical_transactions.transactions)
    components = {day.date: {"inflow": day.predicted_residual_inflow_cents,
                             "outflow": day.predicted_residual_outflow_cents} for day in baseline.days}
    changed_events, changed_projections, warnings = [], [], []
    assumptions = tuple(operation.assumption for operation in scenario.operations)
    for operation in scenario.operations:
        if isinstance(operation, ChangeProjectionOperation):
            if not start <= operation.date <= end:
                raise ValueError("projected cash changes require a date inside the forecast horizon")
            applied = baseline.statistical_inflow_applied if operation.direction == "inflow" else baseline.statistical_outflow_applied
            if not applied:
                raise ValueError("cannot modify a statistical projection that was not applied; add an explicit hypothetical event instead")
            before = components[operation.date][operation.direction]
            components[operation.date][operation.direction] = operation.amount_cents
            changed_projections.append(ScenarioProjectionChange(operation_id=operation.operation_id,
                direction=operation.direction, date=operation.date, before_cents=before,
                after_cents=operation.amount_cents, assumption=operation.assumption))
            continue
        if isinstance(operation, AddEventOperation):
            event = operation.event
            if event.event_id in dispositions or event.source_id in source_ids:
                raise ValueError("hypothetical event and source identifiers must be distinct from existing events")
            if event.currency != baseline.currency:
                raise ValueError("hypothetical event currency must match baseline")
            if (event.status not in _ELIGIBLE_STATUSES or event.historical_transaction_id is not None or
                event.verification_evidence_id is not None or event.source_id in historical_ids or event.event_id in historical_ids):
                raise ValueError("hypothetical event cannot claim completion, verification, or a historical transaction identity")
            if event.expected_date is None or event.expected_date < start:
                raise ValueError("hypothetical event requires an explicit future expected date")
            event = event.model_copy(update={"projection_assumption": operation.assumption})
            included = event.expected_date <= end
            dispositions[event.event_id] = EventDisposition(event=event, included=included,
                reason="Hypothetical incremental cash over the unchanged baseline; not an actual payment." if included
                       else "Hypothetical future event retained outside the forecast horizon; no cash contributed in this window.")
            source_ids.add(event.source_id)
            if included:
                active_events[event.event_id] = event
            else:
                warnings.append(f"Event {event.event_id} remains scheduled hypothetically for {event.expected_date}; it contributes zero cash inside this forecast horizon.")
            warnings.append(f"Event {event.event_id} is assumed incremental over fixed baseline activity; category overlap is not independently proven.")
            changed_events.append(ScenarioEventChange(operation_id=operation.operation_id, operation="add_event",
                event_id=event.event_id, before=None, after=event, included_before=False,
                included_after=included, assumption=operation.assumption))
            continue
        event_id = operation.event_id
        if event_id not in dispositions:
            raise ValueError(f"unknown scenario event ID: {event_id}")
        disposition = dispositions[event_id]
        event = disposition.event
        if (not disposition.included or event.status not in _ELIGIBLE_STATUSES or
            event.historical_transaction_id is not None or event.verification_evidence_id is not None or
            event.source_id in historical_ids or event.event_id in historical_ids):
            raise ValueError(f"event {event_id} is not an eligible included future event; historical and authoritative statuses cannot be changed")
        if isinstance(operation, MoveEventOperation):
            if operation.expected_date < start:
                raise ValueError("cannot move an event before the forecast start date")
            updated = event.model_copy(update={"expected_date": operation.expected_date,
                                               "projection_assumption": operation.assumption})
        elif isinstance(operation, ChangeExpenseAmountOperation):
            if event.direction != "outflow":
                raise ValueError("change_expense_amount requires an eligible outflow event")
            updated = event.model_copy(update={"amount_cents": operation.amount_cents,
                                               "projection_assumption": operation.assumption})
        elif isinstance(operation, RemoveEventOperation):
            updated = None
        else:
            raise ValueError("unsupported scenario operation")
        active_events.pop(event_id)
        included = updated is not None and updated.expected_date <= end
        if included:
            active_events[event_id] = updated
        if updated is None:
            reason = "Hypothetically removed from future cash; the source event and payment status remain unchanged."
        elif not included:
            reason = "Hypothetical event retained outside forecast horizon; no cash contributed in this window."
            warnings.append(f"Event {event_id} remains scheduled hypothetically for {updated.expected_date}; it contributes zero cash inside this forecast horizon.")
        else:
            reason = "Hypothetical cash change only; the authoritative event and payment status remain unchanged."
        dispositions[event_id] = EventDisposition(event=updated or event, included=included, reason=reason)
        changed_events.append(ScenarioEventChange(operation_id=operation.operation_id, operation=operation.operation,
            event_id=event_id, before=event, after=updated, included_before=True,
            included_after=included, assumption=operation.assumption))

    known = {day.date: {"inflow": 0, "outflow": 0, "ids": []} for day in baseline.days}
    for event in active_events.values():
        known[event.expected_date][event.direction] += event.amount_cents
        known[event.expected_date]["ids"].append(event.event_id)
    supplied = tuple(DailyCash(date=day.date, currency=baseline.currency,
        inflow_cents=components[day.date]["inflow"] + known[day.date]["inflow"],
        outflow_cents=components[day.date]["outflow"] + known[day.date]["outflow"],
        evidence_ids=tuple(known[day.date]["ids"])) for day in baseline.days)
    balances = calculate_balances(supplied, start_date=start, horizon_days=request.forecast_horizon_days,
        opening_balance_cents=baseline.opening_balance_cents,
        safety_reserve_cents=baseline.safety_reserve_cents, currency=baseline.currency)
    identifier = "scenario_forecast_" + hashlib.sha256((baseline.forecast_id + scenario.model_dump_json()).encode()).hexdigest()[:20]
    days = tuple(ProjectedCashDay(evidence_id=f"{identifier}_{day.date.isoformat()}", date=day.date, horizon=index + 1,
        opening_balance_cents=day.opening_balance_cents,
        predicted_residual_inflow_cents=components[day.date]["inflow"],
        predicted_residual_outflow_cents=components[day.date]["outflow"],
        known_expected_inflow_cents=known[day.date]["inflow"], known_expected_outflow_cents=known[day.date]["outflow"],
        known_net_cash_adjustment_cents=known[day.date]["inflow"] - known[day.date]["outflow"],
        projected_receipts_cents=day.receipts_cents, projected_payments_cents=day.expenses_cents,
        projected_closing_balance_cents=day.closing_balance_cents, below_safety_reserve=day.below_safety_reserve,
        reserve_shortfall_cents=day.shortfall_cents, known_event_ids=day.evidence_ids,
    ) for index, day in enumerate(balances.days))
    evidence = []
    for day in days:
        if not day.below_safety_reserve:
            continue
        effects = []
        for event in active_events.values():
            if event.expected_date > day.date:
                continue
            signed = event.amount_cents if event.direction == "inflow" else -event.amount_cents
            without = day.projected_closing_balance_cents - signed
            effects.append(KnownEventEffect(event_id=event.event_id, source_id=event.source_id, status=event.status,
                expected_date=event.expected_date, signed_balance_effect_cents=signed,
                closing_balance_without_event_cents=without,
                reserve_shortfall_difference_cents=day.reserve_shortfall_cents - max(0, baseline.safety_reserve_cents - without),
                assumption=event.projection_assumption or "Hypothetical scenario holds original scheduled expense timing fixed."))
        evidence.append(ShortageEvidence(forecast_day_evidence_id=day.evidence_id, date=day.date,
            closing_balance_cents=day.projected_closing_balance_cents,
            reserve_shortfall_cents=day.reserve_shortfall_cents, known_event_effects=tuple(effects),
            opening_balance_evidence_id=baseline.opening_balance_evidence_id))
    uncertainty_days = []
    for original, changed, intervals in zip(baseline.days, days, baseline.uncertainty.horizons):
        uncertainty_days.append(intervals.model_copy(update={
            "residual_inflow": _shift_range(intervals.residual_inflow,
                changed.predicted_residual_inflow_cents - original.predicted_residual_inflow_cents, nonnegative=True),
            "residual_outflow": _shift_range(intervals.residual_outflow,
                changed.predicted_residual_outflow_cents - original.predicted_residual_outflow_cents, nonnegative=True),
            "projected_closing_balance": _shift_range(intervals.projected_closing_balance,
                changed.projected_closing_balance_cents - original.projected_closing_balance_cents),
        }))
    uncertainty_warning = "Scenario ranges shift existing held-out errors conditional on deterministic assumed changes; they do not validate the scenario or payment timing."
    scenario_reconciliation = reconciliation.model_copy(update={
        "fully_reconciled": False,
        "event_dispositions": tuple(dispositions.values()),
        "warnings": reconciliation.warnings + ("Scenario cash is hypothetical; original reconciliation evidence does not verify proposed changes.",),
    })
    limitations = (
        "This comparison executes no payments and changes no authoritative statuses or historical records.",
        "Original models and backtests are reused; scenario cash changes are explicit assumptions, not newly learned predictions.",
        "Events may be changed once per scenario and must already be included; excluded or undated baseline events require a separate explicit hypothetical addition with a new identity.",
        "Moving an event beyond the horizon postpones its contribution in this window; it does not cancel the obligation.",
        "Hypothetical additions are assumed incremental over the unchanged baseline; callers must assess economic overlap.",
        uncertainty_warning,
    )
    scenario_result = baseline.model_copy(update={
        "forecast_id": identifier, "reconciliation": scenario_reconciliation, "days": days,
        "first_reserve_breach_date": balances.first_reserve_breach_date,
        "minimum_projected_cash_balance_cents": min(day.closing_balance_cents for day in balances.days),
        "maximum_reserve_shortfall_cents": max(day.shortfall_cents for day in balances.days),
        "days_below_reserve": sum(day.below_safety_reserve for day in balances.days),
        "risk_assessment_complete": False, "shortage_evidence": tuple(evidence),
        "uncertainty": baseline.uncertainty.model_copy(update={"horizons": tuple(uncertainty_days),
            "warnings": baseline.uncertainty.warnings + (uncertainty_warning,)}),
        "assumptions": baseline.assumptions + assumptions,
        "warnings": tuple(dict.fromkeys(baseline.warnings + tuple(warnings) + limitations)),
    })
    scenario_result = CashForecastResult.model_validate(scenario_result.model_dump())
    return ScenarioComparison(scenario_id=scenario.scenario_id, baseline=baseline, scenario=scenario_result,
        baseline_shortage_date=baseline.first_reserve_breach_date,
        scenario_shortage_date=scenario_result.first_reserve_breach_date,
        baseline_minimum_cash_balance_cents=baseline.minimum_projected_cash_balance_cents,
        scenario_minimum_cash_balance_cents=scenario_result.minimum_projected_cash_balance_cents,
        maximum_reserve_shortfall_change_cents=scenario_result.maximum_reserve_shortfall_cents - baseline.maximum_reserve_shortfall_cents,
        daily_differences=tuple(ScenarioDailyDifference(date=original.date,
            baseline_closing_balance_cents=original.projected_closing_balance_cents,
            scenario_closing_balance_cents=changed.projected_closing_balance_cents,
            closing_balance_difference_cents=changed.projected_closing_balance_cents - original.projected_closing_balance_cents,
            receipts_difference_cents=changed.projected_receipts_cents - original.projected_receipts_cents,
            payments_difference_cents=changed.projected_payments_cents - original.projected_payments_cents,
        ) for original, changed in zip(baseline.days, days)),
        changed_events=tuple(changed_events), changed_projections=tuple(changed_projections),
        assumptions=assumptions, limitations=limitations)
