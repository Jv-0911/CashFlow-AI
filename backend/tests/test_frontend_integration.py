"""Member 4 controls use the existing financial engine and cannot authorize payments."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.api.app import create_app
from backend.app.api.security import Settings

ORIGIN = 'https://cashflow.example.test'


@pytest.fixture
def connected(tmp_path):
    password = uuid4().hex
    app = create_app(Settings(password=password, origin=ORIGIN,
        backend_host='api.example.test', db_path=str(tmp_path/'ledger.db')))
    with TestClient(app, base_url='https://api.example.test') as client:
        result = client.post('/api/v1/session', json={'password': password}, headers={'Origin': ORIGIN})
        assert result.status_code == 200
        assert 'Secure' in result.headers['set-cookie'] and 'HttpOnly' in result.headers['set-cookie']
        yield app, client, {'Origin': ORIGIN, 'X-CSRF-Token': result.json()['csrf_token']}


def payload(**modifiers):
    return dict(business_id='demo_shop_001', forecast_days=30, safety_reserve_cents=100000,
        evidence_ids=[], currency='USD', modifiers=dict(receipts_modifier_pct=0,
            expenses_modifier_pct=0, delayed_receivables_days=0, lump_sum_expense_cents=0, **modifiers))


def test_scenario_identity_and_no_ledger_mutation(connected):
    app, client, headers = connected
    before = app.state.services.ledger.verify_integrity()
    baseline = client.get('/api/v1/forecast?horizon_days=30').json()
    result = client.post('/api/v1/scenario', json=payload(), headers=headers)
    assert result.status_code == 200, result.text
    data = result.json()
    assert [{k: d[k] for k in baseline['days'][0]} for d in data['days']] == baseline['days']
    assert data['comparison']['net_variance_cents'] == 0
    assert data['is_demo'] is True and data['backend_unavailable'] is False
    assert app.state.services.ledger.verify_integrity() == before
    assert client.get('/api/v1/forecast?horizon_days=30').json() == baseline


@pytest.mark.parametrize('modifier,value', [('receipts_modifier_pct', -17), ('expenses_modifier_pct', 23),
    ('delayed_receivables_days', 14), ('delayed_receivables_days', 90), ('lump_sum_expense_cents', 12345),
    ('recurring_payroll_cents', 650000)])
def test_scenario_controls_preserve_integer_balances(connected, modifier, value):
    _, client, headers = connected
    body = payload()
    body['modifiers'][modifier] = value
    baseline = client.get('/api/v1/forecast?horizon_days=30').json()['days']
    result = client.post('/api/v1/scenario', json=body, headers=headers)
    assert result.status_code == 200, result.text
    rows = result.json()['days']
    for i, row in enumerate(rows):
        assert all(type(v) is int for k, v in row.items() if k.endswith('_cents'))
        assert row['closing_balance_cents'] == row['opening_balance_cents'] + row['receipts_cents'] - row['expenses_cents']
        if i:
            assert row['opening_balance_cents'] == rows[i-1]['closing_balance_cents']
        if modifier == 'delayed_receivables_days':
            assert row['receipts_cents'] == (baseline[i-value]['receipts_cents'] if i >= value else 0)
        if modifier == 'receipts_modifier_pct':
            assert row['receipts_cents'] == baseline[i]['receipts_cents'] + (baseline[i]['receipts_cents'] * value + 50)//100
    if modifier == 'lump_sum_expense_cents':
        assert result.json()['comparison']['net_variance_cents'] == -value


@pytest.mark.parametrize('field,value', [('receipts_modifier_pct', 1.5), ('delayed_receivables_days', True),
    ('lump_sum_expense_cents', -1), ('lump_sum_expense_cents', '100'), ('lump_sum_date', '2099-01-01')])
def test_malformed_controls_fail_without_writes(connected, field, value):
    app, client, headers = connected
    before = app.state.services.ledger.verify_integrity()
    body = payload()
    body['modifiers'][field] = value
    assert client.post('/api/v1/scenario', json=body, headers=headers).status_code == 422
    assert app.state.services.ledger.verify_integrity() == before


def test_proxy_preserves_origin_and_authorization_boundary(connected):
    app, client, headers = connected
    assert client.post('/api/v1/scenario', json=payload(), headers={'Origin':'https://evil.example'}).status_code == 403
    assert client.get('/health', headers={'Host':'evil.example'}).status_code == 400
    assert client.post('/api/v1/ledger/proposals', json={'receivable_id':'receivable_northstar'}, headers={'Origin':ORIGIN}).status_code == 403
    client.cookies.clear()
    assert client.post('/api/v1/scenario', json=payload(), headers=headers).status_code == 401
    assert client.get('/api/v1/ledger').status_code == 401
    assert not app.state.services.ledger.list_entries()


@pytest.mark.parametrize('host', ['*', '*.example.test', 'https://api.example.test', 'api.example.test:443', 'api.example.test/path', 'api.example.test\n'])
def test_invalid_backend_host_fails_closed(host):
    with pytest.raises(ValueError):
        Settings(backend_host=host)
