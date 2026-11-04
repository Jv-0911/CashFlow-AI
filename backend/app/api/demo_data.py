"""Fictional single-business dataset. No bank balance or payment claim is real."""
from datetime import date, timedelta

from ..forecast import CashForecastRequest, CategoryScheduleCoverage, VerifiedOpeningBalance
from ..forecast.financial_schemas import ScheduledCashEvent
from ..forecast.interfaces import PreparationRequest, prepare_history

AS_OF = date(2026, 11, 2)
BUSINESS = 'Juniper Studio'
RECEIVABLES = (
    {'id': 'receivable_northstar', 'customer': 'Northstar Coffee', 'description': 'Brand identity project',
     'amount_cents': 320000, 'due_date': AS_OF - timedelta(days=8), 'expected_date': AS_OF + timedelta(days=3)},
    {'id': 'receivable_arc', 'customer': 'Arc Architecture', 'description': 'October design retainer',
     'amount_cents': 185000, 'due_date': AS_OF - timedelta(days=3), 'expected_date': AS_OF + timedelta(days=6)},
    {'id': 'receivable_form', 'customer': 'Form & Field', 'description': 'Website design milestone',
     'amount_cents': 240000, 'due_date': AS_OF + timedelta(days=5), 'expected_date': AS_OF + timedelta(days=10)},
)
EXPENSES = (
    {'id': 'expense_payroll', 'label': 'Team payroll', 'amount_cents': 640000, 'date': AS_OF + timedelta(days=4), 'discretionary': False},
    {'id': 'expense_rent', 'label': 'Studio rent', 'amount_cents': 160000, 'date': AS_OF + timedelta(days=7), 'discretionary': False},
    {'id': 'expense_campaign', 'label': 'Launch campaign', 'amount_cents': 130000, 'date': AS_OF + timedelta(days=8), 'discretionary': True},
)


def financial_request(horizon=14):
    rows = ['transaction_id,date,amount_cents,direction,currency,category,payment_status']
    for offset in range(56):
        day = AS_OF - timedelta(days=56-offset)
        rows += [f'sale_{offset},{day},{22000 + (offset % 7)*1000},inflow,USD,studio_sales,settled',
                 f'cost_{offset},{day},12500,outflow,USD,operations,settled']
    prepared = prepare_history(PreparationRequest(csv_data='\n'.join(rows),
        coverage_start=AS_OF-timedelta(days=56), coverage_end=AS_OF-timedelta(days=1), complete_coverage=True))
    events = [ScheduledCashEvent(event_id=r['id'], source_id=r['id'], direction='inflow',
        amount_cents=r['amount_cents'], currency='USD', status='invoice_unpaid', category='receivables',
        expected_date=r['expected_date'], due_date=r['due_date'],
        projection_assumption='Demo assumption: collection on the planned date; payment is not guaranteed.')
        for r in RECEIVABLES]
    events += [ScheduledCashEvent(event_id=e['id'], source_id=e['id'], direction='outflow',
        amount_cents=e['amount_cents'], currency='USD', status='scheduled_expense', category='obligations',
        expected_date=e['date']) for e in EXPENSES]
    return CashForecastRequest(history=prepared.history, historical_transactions=prepared.source,
        opening_balance=VerifiedOpeningBalance(balance_cents=420000, currency='USD', balance_date=AS_OF,
            evidence_id='synthetic_opening_balance'), safety_reserve_cents=250000,
        forecast_start_date=AS_OF, forecast_horizon_days=horizon, known_events=tuple(events),
        category_coverage=tuple(CategoryScheduleCoverage(category=category, direction=direction,
            evidence_id='synthetic_complete_'+category, complete_for_forecast_window=True)
            for category,direction in [('receivables','inflow'),('obligations','outflow')]))
