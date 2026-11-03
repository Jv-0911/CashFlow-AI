"""Application composition: deterministic analysis and narrowly authorized ledger commands."""
import asyncio
from dataclasses import asdict
from functools import lru_cache
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr

from .demo_data import AS_OF, BUSINESS, EXPENSES, RECEIVABLES, financial_request
from .security import Sessions
from ..forecast.service import forecast_cash_flow
from ..forecast.scenario_schemas import MoveEventOperation, ScenarioRequest
from ..forecast.scenarios import simulate_scenario
from ..ledger.service import LedgerService
from ..ledger.models import State
from ..payments.contracts import entry_view, ledger_view
from ..payments.runtime import PaymentRuntime
from ..payments.evidence_exports import EvidenceUnavailable, rescue_invoice
from ..rescue_ai.schemas import RescueAnalysisRequest
from ..rescue_ai.service import analyze_rescue
from ..rescue_ai.provider import ChatCompletionsProvider

router = APIRouter(prefix='/api/v1')


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Login(Input):
    password: StrictStr = Field(min_length=1, max_length=256)


class Proposal(Input):
    receivable_id: StrictStr = Field(min_length=1, max_length=128)


class Approval(Input):
    expected_sequence: StrictInt = Field(ge=1)
    confirmed: StrictBool


class InvoiceCommand(Input):
    entry_id: StrictStr = Field(min_length=1, max_length=128)


class ScenarioInput(Input):
    horizon_days: StrictInt = Field(default=14, ge=1, le=30)
    event_id: StrictStr = Field(min_length=1, max_length=128)
    delay_days: StrictInt = Field(ge=1, le=30)


class Services:
    def __init__(self, settings, *, ledger=None, payments=None):
        self.settings = settings
        self.sessions = Sessions(settings)
        self.ledger = ledger
        self.payments = payments
        self.ai_provider = None

    def start(self):
        if self.ledger is None:
            path = Path(self.settings.db_path).resolve()
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.ledger = LedgerService(path)
        self.ledger.verify_integrity()
        if self.settings.ai_enabled:
            self.ai_provider = ChatCompletionsProvider.from_env()
        if self.settings.paypal_enabled and self.payments is None:
            recipient = os.environ.get('PAYPAL_SANDBOX_PAYER_EMAIL', '')
            if not recipient:
                raise ValueError('Configure a private Sandbox recipient before enabling payments.')
            self.payments = PaymentRuntime.from_env(lambda ref: recipient if ref == 'demo_payer' else None,
                env=dict(os.environ, LEDGER_DB_PATH=self.settings.db_path))

    def require_payments(self):
        if self.payments is None:
            raise HTTPException(503, 'SANDBOX_NOT_CONFIGURED')
        return self.payments


def services(request):
    return request.app.state.services


def owner(request, *, write=False):
    return services(request).sessions.require(request, write=write)


def analysis_access(request):
    if services(request).settings.password:
        owner(request)


@lru_cache(maxsize=30)
def forecast(horizon):
    return forecast_cash_flow(financial_request(horizon))


def forecast_view(result):
    return {'currency': result.currency, 'safety_reserve_cents': result.safety_reserve_cents,
        'first_reserve_breach_date': result.first_reserve_breach_date,
        'days': [{'date': d.date, 'opening_balance_cents': d.opening_balance_cents,
                  'receipts_cents': d.projected_receipts_cents, 'expenses_cents': d.projected_payments_cents,
                  'closing_balance_cents': d.projected_closing_balance_cents} for d in result.days],
        'is_demo': True, 'disclaimer': 'Synthetic business forecast, not a bank statement or confirmed cash.',
        'details': result.model_dump(mode='json')}


@router.get('/session')
def session(request: Request):
    svc = services(request)
    record = svc.sessions.get(request)
    return {'authenticated': record is not None, 'password_configured': bool(svc.settings.password),
            'csrf_token': record[1] if record else None, 'payments_enabled': svc.payments is not None,
            'read_only_demo': not bool(svc.settings.password)}


@router.post('/session')
def login(body: Login, request: Request, response: Response):
    svc = services(request)
    token, csrf = svc.sessions.login(request, body.password)
    response.set_cookie('cashflow_session', token, max_age=1800, httponly=True,
                        secure=svc.settings.secure_cookie, samesite='strict', path='/')
    return {'authenticated': True, 'csrf_token': csrf}


@router.delete('/session')
def logout(request: Request, response: Response):
    services(request).sessions.logout(request)
    response.delete_cookie('cashflow_session', path='/')
    return {'authenticated': False}


@router.get('/forecast')
def get_forecast(request: Request, response: Response, horizon_days: int = 14):
    analysis_access(request)
    if not 1 <= horizon_days <= 30:
        raise HTTPException(422, 'INVALID_HORIZON')
    response.headers['X-Demo-Data'] = 'true'
    return forecast_view(forecast(horizon_days))


@router.get('/dashboard')
def dashboard(request: Request, horizon_days: int = 14):
    analysis_access(request)
    if not 1 <= horizon_days <= 30:
        raise HTTPException(422, 'INVALID_HORIZON')
    svc = services(request)
    authenticated = svc.sessions.get(request) is not None
    snapshots = svc.ledger.list_entries() if authenticated else ()
    by_source = {s.entry.correlation_key: s for s in snapshots}
    receivables = [dict(r, currency='USD',
        ledger_entry=entry_view(by_source['recovery_'+r['id']]) if 'recovery_'+r['id'] in by_source else None)
        for r in RECEIVABLES]
    return {'business_name': BUSINESS, 'as_of_date': AS_OF, 'is_demo_data': True,
            'forecast': forecast_view(forecast(horizon_days)), 'receivables': receivables,
            'expenses': EXPENSES, 'payments_enabled': svc.payments is not None,
            'recovered_cash': svc.ledger.recovered_cash().get('USD', 0) if authenticated else None,
            'notice': 'Forecast uses a fixed fictional opening snapshot. Verified recoveries are separate; no bank settlement reconciliation is implied.'}


@router.post('/scenarios')
def scenario(body: ScenarioInput, request: Request):
    analysis_access(request)
    services(request).sessions.origin_check(request)
    expense = next((e for e in EXPENSES if e['id'] == body.event_id), None)
    if expense is None:
        raise HTTPException(422, 'SCENARIO_EVENT_INVALID')
    from datetime import timedelta
    comparison = simulate_scenario(financial_request(body.horizon_days), ScenarioRequest(
        scenario_id=f'defer_{body.event_id}_{body.delay_days}',
        operations=(MoveEventOperation(operation_id='move_demo_expense', event_id=expense['id'],
            expected_date=expense['date']+timedelta(days=body.delay_days),
            assumption='Assume the payee explicitly agrees to defer this obligation; no payment is changed.'),)),
        baseline=forecast(body.horizon_days))
    return comparison.model_dump(mode='json') | {'is_demo_data': True}


@router.post('/rescue/analyze')
async def rescue(request: Request, horizon_days: int = 14):
    analysis_access(request)
    services(request).sessions.origin_check(request)
    if not 1 <= horizon_days <= 30:
        raise HTTPException(422, 'INVALID_HORIZON')
    svc = services(request)
    if svc.ai_provider is not None:
        owner(request, write=True)
    result = await asyncio.to_thread(forecast, horizon_days)
    view = forecast_view(result)
    view.pop('details')
    snapshots = await asyncio.to_thread(svc.ledger.list_entries) if svc.sessions.get(request) else ()
    by_source = {s.entry.correlation_key: s for s in snapshots}
    invoices, warnings = [], []
    for r in RECEIVABLES:
        snapshot = by_source.get('recovery_'+r['id'])
        if snapshot is not None and snapshot.state not in {State.PROPOSED, State.APPROVED}:
            try:
                evidence = await asyncio.to_thread(rescue_invoice, svc.ledger, snapshot.entry.entry_id, due_date=r['due_date'])
            except EvidenceUnavailable:
                warnings.append('A recovery item has incomplete or unsupported evidence; collection advice excludes it.')
                continue
            # Keep the original receivable citation; it is a server-owned association.
            evidence['invoice_id'] = r['id']
            invoices.append(evidence)
        else:
            invoices.append({'invoice_id': r['id'], 'currency': 'USD', 'outstanding_amount_cents': r['amount_cents'],
                             'due_date': r['due_date'], 'status': 'unpaid'})
    data = RescueAnalysisRequest.model_validate({'as_of_date': AS_OF, 'forecast_id': result.forecast_id,
        'forecast': view, 'invoices': invoices,
        'transactions': [{'transaction_id': e['id'], 'currency': 'USD', 'amount_cents': e['amount_cents'],
            'date': e['date'], 'direction': 'expense', 'status': 'projected', 'discretionary': e['discretionary']}
            for e in EXPENSES]})
    analysis = await analyze_rescue(data, provider=svc.ai_provider)
    return analysis.model_dump(mode='json') | {'integration_warnings': list(dict.fromkeys(warnings))}


@router.get('/ledger')
def ledger(request: Request):
    owner(request)
    return ledger_view(services(request).ledger, is_demo_data=True)


@router.get('/invoices')
def invoices(request: Request):
    owner(request)
    return ledger_view(services(request).ledger, is_demo_data=True)


@router.post('/ledger/proposals')
def propose(body: Proposal, request: Request):
    owner(request, write=True)
    source = next((r for r in RECEIVABLES if r['id'] == body.receivable_id), None)
    if source is None:
        raise HTTPException(404, 'RECEIVABLE_NOT_FOUND')
    store = services(request).ledger
    entry = store.propose(idempotency_key='recovery_'+source['id'], amount_cents=source['amount_cents'], currency='USD')
    return entry_view(store.get(entry.entry_id))


@router.post('/ledger/{entry_id}/approve')
def approve(entry_id: str, body: Approval, request: Request):
    principal = owner(request, write=True)
    if body.confirmed is not True:
        raise HTTPException(422, 'EXPLICIT_APPROVAL_REQUIRED')
    store = services(request).ledger
    store.approve(entry_id, idempotency_key='approve_'+entry_id,
        expected_sequence=body.expected_sequence, approved_by=principal, payer_reference='demo_payer')
    return entry_view(store.get(entry_id))


@router.post('/invoices')
def create_invoice(body: InvoiceCommand, request: Request):
    owner(request, write=True)
    runtime = services(request).require_payments()
    return entry_view(runtime.invoices.create_draft(body.entry_id, idempotency_key='create_'+body.entry_id))


@router.post('/invoices/{entry_id}/send')
def send_invoice(entry_id: str, request: Request):
    owner(request, write=True)
    runtime = services(request).require_payments()
    return entry_view(runtime.invoices.send(entry_id, idempotency_key='send_'+entry_id))


@router.get('/payments/{entry_id}')
def payment(entry_id: str, request: Request):
    owner(request)
    # A read never dispatches a provider request or mutates ledger history.
    return entry_view(services(request).ledger.get(entry_id))


@router.post('/payments/{entry_id}/verify')
def verify_payment(entry_id: str, request: Request):
    owner(request, write=True)
    runtime = services(request).require_payments()
    return entry_view(runtime.verification.verify(entry_id))


@router.post('/payments/reconcile')
def reconcile(request: Request):
    owner(request, write=True)
    runtime = services(request).require_payments()
    return {'results': [asdict(item) for item in runtime.reconciliation.sweep()]}


@router.post('/webhooks/paypal')
async def webhook(request: Request):
    runtime = services(request).require_payments()
    raw = await request.body()
    result = await asyncio.to_thread(runtime.webhooks.handle, raw, dict(request.headers))
    return {'result': result}
