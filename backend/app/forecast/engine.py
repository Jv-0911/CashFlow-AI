"""Deterministic balances for supplied daily cash flows; no ML or invoice integration."""

from datetime import date, timedelta
from typing import Annotated, Sequence

from pydantic import Field, StrictInt, TypeAdapter

from .schemas import BalanceDay, BalanceResult, Currency, DailyCash, NonNegativeCents


def calculate_balances(
    daily_cash: Sequence[DailyCash], *, start_date: date, horizon_days: int,
    opening_balance_cents: int, safety_reserve_cents: int, currency: Currency,
) -> BalanceResult:
    """Opening balance is immediately before start_date; all amounts are integer cents."""
    horizon_days = TypeAdapter(Annotated[StrictInt, Field(ge=1, le=30)]).validate_python(horizon_days)
    opening_balance_cents = TypeAdapter(StrictInt).validate_python(opening_balance_cents)
    safety_reserve_cents = TypeAdapter(NonNegativeCents).validate_python(safety_reserve_cents)
    currency = TypeAdapter(Currency).validate_python(currency)
    if type(start_date) is not date:
        raise ValueError("start_date must be a date without time")
    try:
        end_date = start_date + timedelta(days=horizon_days - 1)
    except OverflowError as exc:
        raise ValueError("calculation extends beyond supported dates") from exc
    by_date: dict[date, DailyCash] = {}
    evidence: set[str] = set()
    for supplied in daily_cash:
        day = DailyCash.model_validate(supplied)
        if day.currency != currency:
            raise ValueError("daily cash currency does not match calculation currency")
        if day.date in by_date:
            raise ValueError("duplicate daily cash date; aggregate transactions first")
        if not start_date <= day.date <= end_date:
            raise ValueError("daily cash date lies outside calculation window")
        for identifier in day.evidence_ids:
            if not identifier.strip() or identifier in evidence:
                raise ValueError("evidence IDs must be nonblank and unique across daily cash")
            evidence.add(identifier)
        by_date[day.date] = day
    result: list[BalanceDay] = []
    balance = opening_balance_cents
    first_breach = None
    for offset in range(horizon_days):
        current = start_date + timedelta(days=offset)
        cash = by_date.get(current, DailyCash(date=current, currency=currency))
        closing = balance + cash.inflow_cents - cash.outflow_cents
        below = closing < safety_reserve_cents
        if below and first_breach is None:
            first_breach = current
        result.append(BalanceDay(
            date=current, opening_balance_cents=balance, receipts_cents=cash.inflow_cents,
            expenses_cents=cash.outflow_cents, closing_balance_cents=closing,
            below_safety_reserve=below, shortfall_cents=max(0, safety_reserve_cents - closing),
            evidence_ids=cash.evidence_ids,
        ))
        balance = closing
    return BalanceResult(currency=currency, safety_reserve_cents=safety_reserve_cents,
                         first_reserve_breach_date=first_breach, days=tuple(result))
