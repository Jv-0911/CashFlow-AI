"""Exclude explicit complete category schedules from proven historical transaction totals."""

from datetime import timedelta

from .baselines import validate_history
from .financial_schemas import CashForecastRequest, EventDisposition, ReconciliationReport
from .ingestion import aggregate_daily
from .schemas import DailyCash, DailyHistory


def reconcile_history(request: CashForecastRequest) -> tuple[DailyHistory, ReconciliationReport]:
    history = validate_history(request.history)
    cutoff = request.forecast_start_date - timedelta(days=1)
    end = request.forecast_start_date + timedelta(days=request.forecast_horizon_days - 1)
    if any(day.date > cutoff for day in history.days):
        raise ValueError("historical daily data must precede forecast_start_date")
    events = request.known_events
    if len({event.event_id for event in events}) != len(events):
        raise ValueError("duplicate scheduled event IDs")
    if len({event.source_id for event in events}) != len(events):
        raise ValueError("duplicate scheduled source IDs; installments require an explicit future contract")
    historical_links = [event.historical_transaction_id for event in events if event.historical_transaction_id is not None]
    if len(set(historical_links)) != len(historical_links):
        raise ValueError("duplicate historical transaction links in scheduled events")
    if any(event.currency != history.currency for event in events):
        raise ValueError("known event currency must match history and opening balance")
    scopes = {(scope.direction, scope.category): scope for scope in request.category_coverage}
    if len(scopes) != len(request.category_coverage):
        raise ValueError("duplicate category coverage")
    source = request.historical_transactions
    settled = {}
    historical_ids = {identifier for day in history.days for identifier in day.evidence_ids}
    if source is not None:
        source = type(source).model_validate(source.model_dump())
        if source.currency != history.currency:
            raise ValueError("historical transaction source currency does not match history")
        if any(tx.date > cutoff for tx in source.transactions):
            raise ValueError("historical source includes future transactions")
        # Do not let partial or mismatched source records establish a residual forecast.
        source_daily = aggregate_daily(source,
            coverage_start=history.coverage_start if history.complete_coverage else None,
            coverage_end=history.coverage_end if history.complete_coverage else None,
            complete_coverage=history.complete_coverage)
        expected = [(day.date, day.inflow_cents, day.outflow_cents) for day in history.days]
        actual = [(day.date, day.inflow_cents, day.outflow_cents) for day in source_daily.days]
        if expected != actual:
            raise ValueError("historical transactions do not reproduce the supplied daily history")
        settled = {tx.transaction_id: tx for tx in source.transactions if tx.payment_status == "settled"}
    represented_historical_ids = settled.keys() | historical_ids
    dispositions, warnings, relevant = [], [], {"inflow": [], "outflow": []}
    for event in events:
        included, reason = False, ""
        linked_ids = {event.source_id}
        if event.historical_transaction_id is not None:
            linked_ids.add(event.historical_transaction_id)
        represented = linked_ids.intersection(represented_historical_ids)
        if event.status in ("verified_completed", "cancelled", "failed"):
            reason = f"{event.status}: excluded from future cash movements"
        elif represented:
            reason = "already represented in settled history; excluded to avoid counting it again"
            if any(settled[identifier].direction != event.direction for identifier in represented if identifier in settled):
                raise ValueError("linked settled transaction direction conflicts with scheduled event")
        elif event.expected_date is not None and not request.forecast_start_date <= event.expected_date <= end:
            reason = "expected date is outside forecast window; no automatic rescheduling"
        else:
            relevant[event.direction].append(event)
            if event.expected_date is None:
                reason = "unknown expected payment date; not assigned to the due date or another invented date"
            elif event.status != "scheduled_expense" and event.projection_assumption is None:
                reason = "no explicit payment assumption; unpaid or pending cash is not assumed collected"
            else:
                included = True
                reason = "included as expected cash only, conditional on supplied timing and payment assumptions"
        dispositions.append(EventDisposition(event=event, included=included, reason=reason))
        if not included:
            warnings.append(f"Event {event.event_id}: {reason}.")
        elif event.direction == "inflow" or event.status == "pending_verification":
            warnings.append(f"Event {event.event_id} is an unverified projected payment; completion and timing are not guaranteed.")
    policies, excluded_ids, residual_amounts = {}, [], {}
    for direction in ("inflow", "outflow"):
        covered_categories = {category for key_direction, category in scopes if key_direction == direction}
        needs_separation = bool(relevant[direction] or covered_categories)
        if not history.days:
            policies[direction] = "no_prediction"
            continue
        if not needs_separation:
            policies[direction] = "aggregate_prediction"
            continue
        proven_source = source is not None and history.complete_coverage
        categorized = proven_source and all(tx.category and tx.category.strip() for tx in settled.values() if tx.direction == direction)
        event_categories_covered = all(event.category in covered_categories for event in relevant[direction])
        if not (proven_source and categorized and event_categories_covered):
            policies[direction] = "known_events_only"
            warnings.append(f"{direction}: category separation is unproven; statistical activity is suppressed rather than added to potentially overlapping events. Omitted activity may materially change cash risk.")
            continue
        policies[direction] = "category_residual"
        residual_amounts[direction] = {}
        for tx in settled.values():
            if tx.direction != direction:
                continue
            category = tx.category.strip().casefold()
            if category in covered_categories:
                excluded_ids.append(tx.transaction_id)
            else:
                residual_amounts[direction][tx.date] = residual_amounts[direction].get(tx.date, 0) + tx.amount_cents
    excluded_ids = set(excluded_ids)
    residual = DailyHistory(
        currency=history.currency, complete_coverage=history.complete_coverage,
        coverage_start=history.coverage_start, coverage_end=history.coverage_end,
        warnings=history.warnings,
        days=tuple(DailyCash(
            date=day.date, currency=history.currency,
            inflow_cents=residual_amounts["inflow"].get(day.date, 0) if policies["inflow"] == "category_residual" else day.inflow_cents,
            outflow_cents=residual_amounts["outflow"].get(day.date, 0) if policies["outflow"] == "category_residual" else day.outflow_cents,
            evidence_ids=tuple(identifier for identifier in day.evidence_ids if identifier not in excluded_ids),
        ) for day in history.days),
    )
    if not history.days:
        status = "no_history"
        warnings.append("No historical observations: only identifiable supplied future events are projected; ordinary activity is unknown.")
    elif "known_events_only" in policies.values():
        status = "known_only_fallback"
    elif "category_residual" in policies.values():
        status = "residual_categories"
    else:
        status = "aggregate_only"
    unresolved = any(not disposition.included and disposition.event in relevant[disposition.event.direction] for disposition in dispositions)
    fully_reconciled = history.complete_coverage and status not in ("known_only_fallback", "no_history") and not unresolved
    return residual, ReconciliationReport(
        status=status, fully_reconciled=fully_reconciled, inflow_policy=policies["inflow"], outflow_policy=policies["outflow"],
        excluded_historical_transaction_ids=tuple(sorted(excluded_ids)),
        coverage_evidence_ids=tuple(scope.evidence_id for scope in request.category_coverage),
        event_dispositions=tuple(dispositions), warnings=tuple(warnings),
    )
