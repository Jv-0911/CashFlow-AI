"""Thin adapter for Member 4's existing scenario controls; no payment authority."""
from datetime import date
from typing import Literal
from fastapi import APIRouter, Request, HTTPException
from pydantic import Field, StrictInt
from .application import Input, analysis_access, services, forecast, forecast_view
from ..forecast.engine import calculate_balances
from ..forecast.schemas import DailyCash

router = APIRouter(prefix='/api/v1')


class Modifiers(Input):
    preset_id: Literal['delayed_receivables', 'headcount_expansion', 'vendor_price_hike', 'revenue_dip', 'custom'] | None = None
    receipts_modifier_pct: StrictInt = Field(ge=-100, le=200)
    expenses_modifier_pct: StrictInt = Field(ge=-100, le=200)
    delayed_receivables_days: StrictInt = Field(ge=0, le=90)
    lump_sum_expense_cents: StrictInt = Field(ge=0, le=100_000_000)
    recurring_payroll_cents: StrictInt = Field(default=0, ge=0, le=100_000_000)
    lump_sum_date: date | None = None


class ScenarioControls(Input):
    business_id: Literal['demo_shop_001']
    forecast_days: StrictInt = Field(ge=1, le=30)
    safety_reserve_cents: StrictInt = Field(ge=0, le=100_000_000)
    evidence_ids: list[str] = Field(max_length=100)
    currency: Literal['USD']
    modifiers: Modifiers


@router.post('/scenario')
def simulate_controls(body: ScenarioControls, request: Request):
    analysis_access(request)
    services(request).sessions.origin_check(request)
    baseline = forecast_view(forecast(body.forecast_days))
    days, m = baseline['days'], body.modifiers
    if m.lump_sum_date is not None and m.lump_sum_date not in {d['date'] for d in days}:
        raise HTTPException(422, 'SCENARIO_EVENT_INVALID')
    # Translate the existing controls to supplied cash flows; Member 1 owns all balances.
    # Integer rounding matches the existing UI's Math.round rule, with no floats.
    def adjusted(cents, pct):
        return max(0, cents + (cents * pct + 50) // 100)
    supplied = []
    for i, day in enumerate(days):
        prior = i - m.delayed_receivables_days
        receipts = adjusted(days[prior]['receipts_cents'], m.receipts_modifier_pct) if prior >= 0 else 0
        expense = adjusted(day['expenses_cents'], m.expenses_modifier_pct)
        if i % 30 == 0:
            expense += m.recurring_payroll_cents
        if day['date'] == (m.lump_sum_date or days[0]['date']):
            expense += m.lump_sum_expense_cents
        supplied.append(DailyCash(date=day['date'], currency='USD', inflow_cents=receipts, outflow_cents=expense))
    result = calculate_balances(supplied, start_date=days[0]['date'], horizon_days=body.forecast_days,
        opening_balance_cents=days[0]['opening_balance_cents'], safety_reserve_cents=body.safety_reserve_cents, currency='USD')
    before_min = min(d['closing_balance_cents'] for d in days)
    after_min = min(d.closing_balance_cents for d in result.days)
    assumptions = ['Hypothetical timing and amount changes only; no accounts, invoices or ledger entries are changed.',
        'Receipts shifted beyond this window remain uncollected in this view; they are not erased.',
        'The baseline uses fictional business data. Client evidence IDs do not authorize or establish payment facts.']
    return dict(currency='USD', safety_reserve_cents=body.safety_reserve_cents,
        first_reserve_breach_date=result.first_reserve_breach_date,
        days=[d.model_dump(mode='json') for d in result.days], is_demo=True, backend_unavailable=False,
        disclaimer='Hypothetical scenario calculated by the backend financial engine. Not confirmed cash.',
        comparison=dict(baseline_ending_balance_cents=days[-1]['closing_balance_cents'],
            scenario_ending_balance_cents=result.days[-1].closing_balance_cents,
            baseline_breach_date=next((d['date'] for d in days if d['closing_balance_cents'] < body.safety_reserve_cents), None),
            scenario_breach_date=result.first_reserve_breach_date, changes_applied=assumptions,
            net_variance_cents=result.days[-1].closing_balance_cents-days[-1]['closing_balance_cents'],
            baseline_min_balance_cents=before_min, scenario_min_balance_cents=after_min,
            shortfall_change_cents=max(0, body.safety_reserve_cents-after_min)-max(0, body.safety_reserve_cents-before_min)))
