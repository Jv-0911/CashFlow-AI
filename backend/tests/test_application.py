from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

from backend.app.api.app import create_app
from backend.app.api.security import Settings
from backend.app.ledger.service import LedgerService
from backend.app.payments.invoice_service import InvoiceService, invoice_number
from backend.app.payments.runtime import PaymentRuntime
from backend.app.payments.verification import VerificationService
from backend.app.payments.reconciliation import ReconciliationService
from backend.app.payments.webhooks import WebhookHandler
from backend.app.payments.paypal_client import Response
from backend.tests.payments.fakes import client as fake_client, invoice, oauth, response

ORIGIN = 'http://127.0.0.1:8000'


@pytest.fixture
def application(tmp_path):
    password = uuid4().hex
    app = create_app(Settings(password=password, db_path=str(tmp_path/'ledger.db')))
    with TestClient(app, base_url=ORIGIN) as client:
        yield app, client, password


def sign_in(client, password):
    result = client.post('/api/v1/session', json={'password': password}, headers={'Origin': ORIGIN})
    assert result.status_code == 200
    return {'Origin': ORIGIN, 'X-CSRF-Token': result.json()['csrf_token']}


def proposal(client, headers):
    result = client.post('/api/v1/ledger/proposals', json={'receivable_id': 'receivable_northstar'}, headers=headers)
    assert result.status_code == 200
    return result.json()


def test_public_demo_uses_engine_and_keeps_private_ledger_closed(tmp_path):
    app = create_app(Settings(db_path=str(tmp_path/'ledger.db')))
    with TestClient(app, base_url=ORIGIN) as client:
        result = client.get('/api/v1/dashboard').json()
        assert result['is_demo_data'] is True
        assert len(result['forecast']['days']) == 14
        assert result['forecast']['details']['forecast_id'].startswith('cash_forecast_')
        assert result['recovered_cash'] is None
        assert client.get('/api/v1/ledger').status_code == 401
        assert client.post('/api/v1/ledger/proposals', json={'receivable_id': 'receivable_northstar'}).status_code == 401


def test_login_origin_cookie_and_csrf(application):
    app, client, password = application
    assert client.get('/api/v1/dashboard').status_code == 401
    assert client.post('/api/v1/session', json={'password': password}, headers={'Origin': 'https://attacker.test'}).status_code == 403
    headers = sign_in(client, password)
    assert client.get('/api/v1/session').json()['authenticated']
    assert client.get('/api/v1/dashboard').status_code == 200
    assert client.post('/api/v1/ledger/proposals', json={'receivable_id': 'receivable_northstar'}, headers={'Origin': ORIGIN}).status_code == 403
    cookie = client.cookies.get('cashflow_session')
    assert cookie
    proposal(client, headers)
    assert client.delete('/api/v1/session', headers=headers).status_code == 200
    assert client.get('/api/v1/ledger').status_code == 401


def test_proposals_idempotent_and_explicit_approval_required(application):
    app, client, password = application
    headers = sign_in(client, password)
    item = proposal(client, headers)
    assert proposal(client, headers)['entry_id'] == item['entry_id']
    url = '/api/v1/ledger/'+item['entry_id']+'/approve'
    assert client.post(url, json={'expected_sequence': item['sequence'], 'confirmed': False}, headers=headers).status_code == 422
    assert client.post(url, json={'expected_sequence': item['sequence'], 'confirmed': True, 'approved_by': 'ai'}, headers=headers).status_code == 422
    approved = client.post(url, json={'expected_sequence': item['sequence'], 'confirmed': True}, headers=headers)
    assert approved.json()['status'] == 'APPROVED'
    assert app.state.services.ledger.get(item['entry_id']).events[-1].actor == 'business_owner'
    assert client.get('/api/v1/ledger').json()['recovered_cash'] == [{'amount_cents': 0, 'currency': 'USD'}]


def test_no_false_paid_from_client_fields_or_unconfigured_provider(application):
    app, client, password = application
    headers = sign_in(client, password)
    for extra in ({'status': 'VERIFIED_PAID'}, {'amount_cents': 1}, {'paid_amount_cents': 320000}):
        assert client.post('/api/v1/ledger/proposals', json={'receivable_id': 'receivable_northstar', **extra}, headers=headers).status_code == 422
    item = proposal(client, headers)
    before = app.state.services.ledger.verify_integrity()
    assert client.post('/api/v1/invoices', json={'entry_id': item['entry_id']}, headers=headers).status_code == 503
    assert client.post('/api/v1/payments/'+item['entry_id']+'/verify', headers=headers).status_code == 503
    assert client.post('/api/v1/webhooks/paypal', json={'status': 'PAID'}).status_code == 503
    assert app.state.services.ledger.verify_integrity() == before


def test_scenario_and_rescue_are_real_read_only_module_calls(application):
    app, client, password = application
    headers = sign_in(client, password)
    before = app.state.services.ledger.verify_integrity()
    forecast_before = client.get('/api/v1/forecast').json()
    result = client.post('/api/v1/scenarios', json={'event_id': 'expense_payroll', 'delay_days': 7}, headers=headers)
    assert result.status_code == 200, result.text
    assert result.json()['hypothetical'] is True
    assert any(day['closing_balance_difference_cents'] != 0 for day in result.json()['daily_differences'])
    assert client.get('/api/v1/forecast').json() == forecast_before
    rescue = client.post('/api/v1/rescue/analyze', headers=headers)
    assert rescue.status_code == 200, rescue.text
    assert rescue.json()['source'] == 'deterministic'
    assert all(a['requires_approval'] for a in rescue.json()['recommended_actions'])
    assert app.state.services.ledger.verify_integrity() == before


def test_body_and_origin_limits_and_sanitized_errors(application):
    app, client, password = application
    result = client.post('/api/v1/session', content=b'x'*65537, headers={'Origin': ORIGIN})
    assert result.status_code == 413
    result = client.post('/api/v1/session', json={'password': password, 'secret_extra': password}, headers={'Origin': ORIGIN})
    assert result.status_code == 422
    assert password not in result.text
    assert client.get('/api/v1/dashboard', headers={'Host': 'attacker.test'}).status_code == 400


def test_login_throttling_and_security_headers(application):
    app, client, password = application
    for _ in range(5):
        assert client.post('/api/v1/session', json={'password': uuid4().hex}, headers={'Origin': ORIGIN}).status_code == 401
    assert client.post('/api/v1/session', json={'password': password}, headers={'Origin': ORIGIN}).status_code == 429
    result = client.get('/health')
    assert result.headers['cache-control'] == 'no-store'
    assert result.headers['x-content-type-options'] == 'nosniff'


def test_unsafe_public_settings_fail_closed(tmp_path):
    for args in ({'origin': 'http://public.example'}, {'origin': 'https://public.example'},
                 {'password': 'short'}, {'paypal_enabled': True}):
        with pytest.raises(ValueError):
            Settings(**args)


def test_expired_session_and_secure_public_cookie(tmp_path, monkeypatch):
    from backend.app.api import security
    password = uuid4().hex
    origin = 'https://cashflow.example.test'
    app = create_app(Settings(password=password, origin=origin, db_path=str(tmp_path/'ledger.db')))
    with TestClient(app, base_url=origin) as client:
        result = client.post('/api/v1/session', json={'password': password}, headers={'Origin': origin})
        cookie = result.headers['set-cookie'].lower()
        assert 'httponly' in cookie and 'secure' in cookie and 'samesite=strict' in cookie
        now = security.time.monotonic()
        monkeypatch.setattr(security.time, 'monotonic', lambda: now + 1801)
        assert client.get('/api/v1/ledger').status_code == 401


def test_alternate_paypal_hosts_fail_even_when_payments_disabled(monkeypatch):
    monkeypatch.setenv('CASHFLOW_PAYPAL_ENABLED', 'false')
    monkeypatch.setenv('PAYPAL_BASE_URL', 'https://api-m.paypal.com')
    with pytest.raises(ValueError):
        Settings.from_env()


def test_action_rate_limit_and_status_routes_cannot_bypass_ledger(application):
    app, client, password = application
    headers = sign_in(client, password)
    item = proposal(client, headers)
    before = app.state.services.ledger.verify_integrity()
    for method in ('put', 'patch', 'delete'):
        result = getattr(client, method)('/api/v1/payments/'+item['entry_id'], headers=headers)
        assert result.status_code == 405
    assert app.state.services.ledger.verify_integrity() == before
    for _ in range(29):
        assert client.post('/api/v1/ledger/proposals', json={'receivable_id': 'receivable_northstar'}, headers=headers).status_code == 200
    assert client.post('/api/v1/ledger/proposals', json={'receivable_id': 'receivable_northstar'}, headers=headers).status_code == 429
    assert app.state.services.ledger.verify_integrity() == before


def test_integrated_ai_outage_falls_back_without_payment_writes(application):
    app, client, password = application
    class Unavailable:
        async def analyze(self, baseline):
            raise TimeoutError('must never be reflected')
    app.state.services.ai_provider = Unavailable()
    headers = sign_in(client, password)
    before = app.state.services.ledger.verify_integrity()
    result = client.post('/api/v1/rescue/analyze', headers=headers)
    assert result.status_code == 200
    assert result.json()['source'] == 'deterministic'
    assert 'must never be reflected' not in result.text
    assert app.state.services.ledger.verify_integrity() == before


def test_end_to_end_api_payment_requires_fresh_provider_evidence(tmp_path):
    ledger = LedgerService(tmp_path/'ledger.db')
    api, fake = fake_client()
    invoices = InvoiceService(ledger, api, lambda ref: 'demo-payer@example.test')
    runtime = PaymentRuntime(ledger, invoices, VerificationService(ledger, api),
        ReconciliationService(ledger, api, invoices), WebhookHandler(ledger, api))
    password = uuid4().hex
    app = create_app(Settings(password=password, db_path=str(tmp_path/'ledger.db')), ledger=ledger, payments=runtime)
    with TestClient(app, base_url=ORIGIN) as client:
        headers = sign_in(client, password)
        item = proposal(client, headers)
        entry_id = item['entry_id']
        result = client.post('/api/v1/invoices', json={'entry_id': entry_id}, headers=headers)
        assert result.status_code != 200
        assert not fake.calls
        assert client.post('/api/v1/ledger/'+entry_id+'/approve', json={'expected_sequence': item['sequence'], 'confirmed': True}, headers=headers).status_code == 200
        draft = invoice('DRAFT', value='3200.00', reference=entry_id, number=invoice_number(entry_id))
        fake.steps += [oauth(), response(draft, 201)]
        assert client.post('/api/v1/invoices', json={'entry_id': entry_id}, headers=headers).json()['status'] == 'INVOICE_DRAFTED'
        fake.steps += [response(draft), Response(202, b'')]
        assert client.post('/api/v1/invoices/'+entry_id+'/send', headers=headers).json()['status'] == 'INVOICE_SENT'
        assert ledger.recovered_cash() == {'USD': 0}
        fake.steps += [response(invoice('PAID', value='3200.00', paid='3200.00', reference=entry_id, number=invoice_number(entry_id)))]
        assert client.post('/api/v1/payments/'+entry_id+'/verify', headers=headers).json()['status'] == 'VERIFIED_PAID'
        assert client.get('/api/v1/ledger').json()['recovered_cash'] == [{'amount_cents': 320000, 'currency': 'USD'}]
        assert not client.post('/api/v1/rescue/analyze', headers=headers).json().get('error')
