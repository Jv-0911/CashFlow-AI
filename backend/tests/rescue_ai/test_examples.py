"""Acceptance checks for the fictional demos, command line and handoff fixtures."""

import asyncio
import json
from pathlib import Path
import subprocess
import sys

import pytest

from backend.app.rescue_ai.examples import (
    DEMO_SCENARIOS, build_demo_request, main, run_demo,
)
from backend.app.rescue_ai.schemas import RescueAnalysisRequest, RescueResponse
from backend.app.rescue_ai.service import analyze_rescue


MODULE_DIR = Path(__file__).resolve().parents[2] / 'app' / 'rescue_ai'
REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize('scenario,risk,source,action_count', [
    ('shortage', 'high', 'deterministic', 2),
    ('safe', 'low', 'deterministic', 0),
    ('reserve_boundary', 'medium', 'deterministic', 2),
    ('insufficient_evidence', 'unknown', 'deterministic', 0),
    ('stale', 'unknown', 'deterministic', 0),
    ('paid_invoice', 'high', 'deterministic', 1),
    ('provider_failure', 'high', 'deterministic', 2),
    ('ai_selection', 'high', 'ai', 2),
])
def test_demo_acceptance(scenario, risk, source, action_count):
    record = asyncio.run(run_demo(scenario))
    request = RescueAnalysisRequest.model_validate(record['request'])
    response = RescueResponse.model_validate(record['response'])
    assert response.risk_level == risk
    assert response.source == source
    assert len(response.recommended_actions) == action_count
    assert request.forecast.is_demo and response.is_demo and record['is_demo']
    assert response.currency == 'USD'
    for action in response.recommended_actions:
        assert action.requires_approval
        assert action.assumptions
        assert set(action.evidence_ids) <= set(response.evidence_ids)


def test_business_example_exact_amounts_and_no_double_counting():
    record = asyncio.run(run_demo('shortage'))
    day = record['request']['forecast']['days'][0]
    assert day['opening_balance_cents'] == 120000
    assert day['receipts_cents'] == 20000
    assert day['expenses_cents'] == 80000
    assert day['closing_balance_cents'] == 60000
    assert 'USD 400.00 below the reserve' in record['response']['summary']
    action = record['response']['recommended_actions'][0]
    assert action['action_id'] == 'follow_up:INV-DEMO-104'
    assert action['estimated_impact_cents'] == 80000
    assert any('not guaranteed or incremental' in item for item in action['assumptions'])
    expense = record['response']['recommended_actions'][1]
    assert expense['estimated_impact_cents'] is None


def test_demo_provider_is_explicitly_simulated():
    record = asyncio.run(run_demo('ai_selection'))
    assert record['provider_mode'] == 'simulated_selection'
    assert record['response']['source'] == 'ai'
    assert any('simulated locally; no AI model was called' in text
               for text in record['response']['assumptions'])
    assert record['response']['recommended_actions'][0]['action_id'] == 'review_expense:WAGES-DEMO-001'


def test_simulated_outage_preserves_actions_and_risk():
    good = asyncio.run(run_demo('shortage'))['response']
    failed_record = asyncio.run(run_demo('provider_failure'))
    failed = failed_record['response']
    assert failed_record['provider_mode'] == 'simulated_failure'
    for key in ['summary', 'risk_level', 'evidence_ids', 'recommended_actions', 'currency']:
        assert failed[key] == good[key]
    assert 'unavailable or rejected' in failed['assumptions'][-1]


def test_all_demos_run_without_http_or_credentials(monkeypatch):
    import httpx
    def forbidden(*args, **kwargs):
        pytest.fail('Local demos must not construct an HTTP client')
    monkeypatch.setattr(httpx, 'AsyncClient', forbidden)
    monkeypatch.setenv('AI_BASE_URL', 'https://must-not-call.example/v1')
    monkeypatch.setenv('AI_API_KEY', 'private-do-not-print')
    for scenario in DEMO_SCENARIOS:
        record = asyncio.run(run_demo(scenario))
        assert 'private-do-not-print' not in json.dumps(record)


def test_scenarios_are_reproducible_and_independent():
    for scenario in DEMO_SCENARIOS:
        assert asyncio.run(run_demo(scenario)) == asyncio.run(run_demo(scenario))
    first = build_demo_request('shortage')
    first.invoices[0].outstanding_amount_cents = 1
    assert build_demo_request('shortage').invoices[0].outstanding_amount_cents == 80000


def test_paid_status_does_not_credit_cash():
    record = asyncio.run(run_demo('paid_invoice'))
    assert record['request']['forecast']['days'][0]['closing_balance_cents'] == 60000
    assert record['response']['risk_level'] == 'high'
    assert all(not action['action_id'].startswith('follow_up:')
               for action in record['response']['recommended_actions'])


def test_caller_supplies_refreshed_forecast_after_verified_receipt():
    # Fictional caller updates both invoice and forecast after verification.
    # Rescue never assumes that changing a status itself creates received cash.
    payload = build_demo_request('paid_invoice').model_dump(mode='json')
    before = asyncio.run(analyze_rescue(RescueAnalysisRequest.model_validate(payload)))
    assert before.risk_level == 'high'
    day = payload['forecast']['days'][0]
    day['opening_balance_cents'] += 80000
    day['closing_balance_cents'] += 80000
    payload['forecast']['first_reserve_breach_date'] = None
    after = asyncio.run(analyze_rescue(RescueAnalysisRequest.model_validate(payload)))
    assert after.risk_level == 'low'
    assert 'USD 1,400.00' in after.summary


def test_late_expected_receipt_changes_supplied_forecast_not_invoice_status():
    payload = build_demo_request('shortage').model_dump(mode='json')
    payload['forecast']['days'][0].update(receipts_cents=0, closing_balance_cents=40000)
    result = asyncio.run(analyze_rescue(RescueAnalysisRequest.model_validate(payload)))
    assert 'USD 600.00 below the reserve' in result.summary
    assert payload['invoices'][0]['status'] == 'unpaid'


@pytest.mark.parametrize('scenario', ['', 'unknown', 'SHORTAGE'])
def test_unknown_scenario_rejected(scenario):
    with pytest.raises(ValueError, match='Unknown demo scenario'):
        build_demo_request(scenario)
    with pytest.raises(ValueError, match='Unknown demo scenario'):
        asyncio.run(run_demo(scenario))


def test_saved_example_fixture_is_complete_and_matches_runner():
    records = json.loads((MODULE_DIR / 'example_data.json').read_text(encoding='utf-8-sig'))
    assert [record['scenario'] for record in records] == list(DEMO_SCENARIOS)
    for record in records:
        RescueAnalysisRequest.model_validate(record['request'])
        RescueResponse.model_validate(record['response'])
        assert record == asyncio.run(run_demo(record['scenario']))


@pytest.mark.parametrize('args,expected', [
    ([], 'all'), (['--scenario', 'shortage'], 'shortage'),
    (['--scenario', 'ai_selection', '--pretty'], 'ai_selection'),
])
def test_cli_output_is_json(args, expected, capsys):
    main(args)
    value = json.loads(capsys.readouterr().out)
    if expected == 'all':
        assert len(value) == len(DEMO_SCENARIOS)
    else:
        assert value['scenario'] == expected


def test_cli_unknown_scenario_exits_cleanly(capsys):
    with pytest.raises(SystemExit) as caught:
        main(['--scenario', 'does-not-exist'])
    assert caught.value.code == 2
    assert 'invalid choice' in capsys.readouterr().err


def test_documented_module_command_runs_from_repository_root():
    completed = subprocess.run(
        [sys.executable, '-B', '-m', 'backend.app.rescue_ai.examples',
         '--scenario', 'shortage', '--pretty'],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)['response']['risk_level'] == 'high'


def test_demo_runner_creates_no_files():
    before = {path.relative_to(MODULE_DIR) for path in MODULE_DIR.rglob('*')}
    for scenario in DEMO_SCENARIOS:
        asyncio.run(run_demo(scenario))
    after = {path.relative_to(MODULE_DIR) for path in MODULE_DIR.rglob('*')}
    assert after == before


def test_inputs_use_explicit_fixed_dates():
    request = build_demo_request()
    assert request.as_of_date.isoformat() == '2026-10-26'
    assert request.forecast.days[0].date.isoformat() == '2026-10-27'


def test_documented_api_wrapper_runs_with_the_saved_request():
    import re
    guide = (MODULE_DIR / 'INTEGRATION.md').read_text(encoding='utf-8-sig')
    snippet = re.findall(r'```python\n(.*?)\n```', guide, re.DOTALL)[0]
    namespace = {}
    exec(compile(snippet, 'INTEGRATION.md:api-example', 'exec'), namespace)
    payload = build_demo_request('shortage').model_dump(mode='json')
    result = asyncio.run(namespace['analyze_for_api'](payload))
    assert result['risk_level'] == 'high'
    assert result['source'] == 'deterministic'
    assert result['recommended_actions'][0]['estimated_impact_cents'] == 80000


def test_documented_optional_configuration_handles_missing_settings(monkeypatch):
    import re
    for key in ['AI_BASE_URL', 'AI_MODEL', 'AI_API_KEY', 'AI_TIMEOUT_SECONDS']:
        monkeypatch.delenv(key, raising=False)
    guide = (MODULE_DIR / 'INTEGRATION.md').read_text(encoding='utf-8-sig')
    snippet = re.findall(r'```python\n(.*?)\n```', guide, re.DOTALL)[2]
    namespace = {}
    exec(compile(snippet, 'INTEGRATION.md:configuration-example', 'exec'), namespace)
    assert namespace['configured_provider'] is None


def test_readme_local_markdown_links_resolve():
    import re
    readme = (MODULE_DIR / 'README.md').read_text(encoding='utf-8-sig')
    targets = re.findall(r'\[[^\]]+\]\(([^)]+)\)', readme)
    assert targets
    for target in targets:
        assert (MODULE_DIR / target).is_file(), target
