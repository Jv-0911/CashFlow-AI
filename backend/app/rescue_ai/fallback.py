"""Deterministic rescue analysis with no network calls or payment mutations."""

from .schemas import RecoveryAction, RescueAnalysisRequest, RescueResponse


def _money(cents: int, currency: str) -> str:
    """Format integer cents without floating-point rounding."""
    sign = "-" if cents < 0 else ""
    whole, fraction = divmod(abs(cents), 100)
    return f"{currency} {sign}{whole:,}.{fraction:02d}"


def analyze_fallback(request: RescueAnalysisRequest) -> RescueResponse:
    """Explain a validated snapshot and return proposed actions.

    Risk policy: unknown for no current/future days, high below reserve, medium
    exactly at reserve, low above it. Only dates on/after as_of_date are assessed.
    The forecast is accepted from Member 1, never recalculated or credited with
    proposed recoveries. No payment status or input record is changed.

    Ranking: overdue unpaid invoices first (contribution to the reserve gap,
    overdue age, outstanding amount, ID); then projected expenses (discretionary
    first, date, amount, ID). This is a transparent heuristic, not a prediction
    of payment probability. An action's impact is a standalone potential amount,
    not an incremental forecast improvement and must never be summed as cash.
    """
    # Revalidate even an existing model, which callers could have mutated.
    data = RescueAnalysisRequest.model_validate(request.model_dump(mode="json"))
    forecast = data.forecast
    currency = forecast.currency
    days = [day for day in forecast.days if day.date >= data.as_of_date]
    assumptions = [
        "Analysis covers only the supplied forecast dates on or after the as-of date.",
        "Projected receipts and expenses are uncertain; no payment is verified by this analysis.",
        "Evidence records are not added to the forecast again; actions do not change its balances.",
    ]
    if forecast.is_demo:
        assumptions.append("This analysis uses demo data, not live business records.")
    if not days:
        return RescueResponse(
            summary="Insufficient evidence: no current or future forecast days were supplied.",
            risk_level="unknown", evidence_ids=[data.forecast_id],
            recommended_actions=[], currency=currency, assumptions=assumptions,
            source="deterministic", is_demo=forecast.is_demo,
        )

    lowest = min(days, key=lambda day: (day.closing_balance_cents, day.date))
    gap = max(0, forecast.safety_reserve_cents - lowest.closing_balance_cents)
    breach = next((day for day in days
                   if day.closing_balance_cents < forecast.safety_reserve_cents), None)
    evidence = [data.forecast_id]
    actions: list[RecoveryAction] = []
    if breach is not None:
        risk = "high"
        summary = (
            f"Projected cash may first fall below the safety reserve on {breach.date.isoformat()}. "
            f"The lowest supplied projected balance is {_money(lowest.closing_balance_cents, currency)} "
            f"on {lowest.date.isoformat()}, {_money(gap, currency)} below the reserve."
        )
        # Diagnose net movements only from forecast aggregates, not an assumed
        # relationship between transactions and forecast events.
        through_lowest = [day for day in days if day.date <= lowest.date]
        receipts = sum(day.receipts_cents for day in through_lowest)
        expenses = sum(day.expenses_cents for day in through_lowest)
        summary += (
            f" Through that date, supplied projected expenses total {_money(expenses, currency)} "
            f"and projected receipts total {_money(receipts, currency)}."
        )
        if days[0].opening_balance_cents < forecast.safety_reserve_cents:
            summary += " The first assessed day's opening balance is already below the reserve."
        summary += " Individual causes cannot be established without linked source records."
    elif lowest.closing_balance_cents == forecast.safety_reserve_cents:
        risk = "medium"
        summary = (
            "No reserve breach is shown in the assessed dates, but the lowest projected "
            "balance equals the safety reserve, leaving no margin above it."
        )
    else:
        risk = "low"
        summary = (
            "No reserve breach is shown in the assessed dates. "
            f"The lowest projected balance is {_money(lowest.closing_balance_cents, currency)}. "
            "This does not guarantee sufficient cash outside the supplied forecast or if receipts are late."
        )

    if risk in {"high", "medium"}:
        invoices = sorted(
            (invoice for invoice in data.invoices
             if invoice.status == "unpaid" and invoice.outstanding_amount_cents > 0
             and invoice.due_date < data.as_of_date),
            key=lambda invoice: (
                -min(invoice.outstanding_amount_cents, gap),
                -(data.as_of_date - invoice.due_date).days,
                -invoice.outstanding_amount_cents, invoice.invoice_id,
            ),
        )
        for invoice in invoices:
            evidence.append(invoice.invoice_id)
            actions.append(RecoveryAction(
                action_id=f"follow_up:{invoice.invoice_id}",
                title=f"Review and follow up on overdue invoice {invoice.invoice_id}",
                explanation=(
                    f"The supplied unpaid invoice has {_money(invoice.outstanding_amount_cents, currency)} "
                    "outstanding. Review its status and approve any customer contact."
                ),
                estimated_impact_cents=invoice.outstanding_amount_cents,
                assumptions=[
                    "The customer pays the outstanding amount; timing and collection are uncertain.",
                    "This is potential invoice collection, not guaranteed or incremental forecast cash.",
                    "A late receipt cannot resolve an earlier shortage; use the scenario engine to assess timing.",
                ],
                evidence_ids=[data.forecast_id, invoice.invoice_id], currency=currency,
                priority=len(actions) + 1, requires_approval=True,
            ))

        horizon_end = breach.date if breach is not None else lowest.date
        expenses_to_review = sorted(
            (event for event in data.transactions
             if event.direction == "expense" and event.status == "projected"
             and event.amount_cents > 0
             and data.as_of_date <= event.date <= horizon_end),
            key=lambda event: (not event.discretionary, event.date, -event.amount_cents,
                               event.transaction_id),
        )
        for event in expenses_to_review:
            evidence.append(event.transaction_id)
            actions.append(RecoveryAction(
                action_id=f"review_expense:{event.transaction_id}",
                title=f"Review upcoming expense {event.transaction_id}",
                explanation=(
                    f"A supplied projected expense of {_money(event.amount_cents, currency)} "
                    f"is dated {event.date.isoformat()}. "
                    "Consider a scenario to assess an approved change in timing."
                ),
                estimated_impact_cents=None,
                assumptions=[
                    "Changing a payment date requires approval and may require agreement with the payee.",
                    "No saving or deferral impact is calculated without the financial scenario engine.",
                    "The supplied expense has not been linked to a specific forecast event.",
                ],
                evidence_ids=[data.forecast_id, event.transaction_id], currency=currency,
                priority=len(actions) + 1, requires_approval=True,
            ))
        if not actions:
            summary += " No eligible overdue unpaid invoices or upcoming expense records support a specific recovery action."

    return RescueResponse(
        summary=summary, risk_level=risk, evidence_ids=evidence,
        recommended_actions=actions, currency=currency, assumptions=assumptions,
        source="deterministic", is_demo=forecast.is_demo,
    )
