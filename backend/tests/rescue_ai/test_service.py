"""Service behavior with local fixtures and fake/mocked providers only."""

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from backend.app.rescue_ai.fallback import analyze_fallback
from backend.app.rescue_ai.provider import (
    ChatCompletionsProvider, ProviderDecision, ProviderError,
)
from backend.app.rescue_ai.schemas import RescueAnalysisRequest, RescueResponse
from backend.app.rescue_ai.service import analyze_rescue
from backend.app.rescue_ai import service as rescue_service


@pytest.fixture
def request_data():
    return {
        "as_of_date": "2026-10-22", "forecast_id": "FC-1",
        "forecast": {
            "currency": "USD", "safety_reserve_cents": 100000,
            "first_reserve_breach_date": "2026-10-23", "is_demo": True,
            "days": [{"date": "2026-10-23", "opening_balance_cents": 120000,
                "receipts_cents": 20000, "expenses_cents": 80000,
                "closing_balance_cents": 60000}],
        },
        "invoices": [{"invoice_id": "INV-1", "currency": "USD",
            "outstanding_amount_cents": 80000, "due_date": "2026-10-10",
            "status": "unpaid"}],
        "transactions": [{"transaction_id": "WAGES-1", "currency": "USD",
            "amount_cents": 80000, "date": "2026-10-23", "direction": "expense",
            "status": "projected", "discretionary": False}],
    }


@pytest.fixture
def analysis_request(request_data):
    return RescueAnalysisRequest.model_validate(request_data)


class FakeProvider:
    """Synchronous selection factory behind an async provider boundary."""

    def __init__(self, select):
        self.select = select
        self.calls = 0
        self.received = None

    async def analyze(self, baseline):
        self.calls += 1
        self.received = baseline
        return self.select(baseline)


def decision_for(baseline):
    return ProviderDecision(
        action_ids=[action.action_id for action in reversed(baseline.recommended_actions)],
        explanation_points=["reserve_breach", "overdue_invoices", "collection_uncertain"],
    )


def run(analysis_request, provider=None, **kwargs):
    return asyncio.run(analyze_rescue(analysis_request, provider, **kwargs))


def test_no_provider_returns_exact_fallback(analysis_request):
    assert run(analysis_request) == analyze_fallback(analysis_request)


def test_valid_ai_changes_only_order_priority_and_supported_explanation(analysis_request):
    baseline = analyze_fallback(analysis_request)
    provider = FakeProvider(decision_for)
    before = analysis_request.model_dump_json()
    result = run(analysis_request, provider)
    assert provider.calls == 1
    assert result.source == "ai"
    assert result.summary.startswith(baseline.summary)
    assert "USD 400.00 below the reserve" in result.summary
    assert "Customer collection and its timing remain uncertain" in result.summary
    assert [action.action_id for action in result.recommended_actions] == [
        "review_expense:WAGES-1", "follow_up:INV-1"]
    assert [action.priority for action in result.recommended_actions] == [1, 2]
    originals = {action.action_id: action for action in baseline.recommended_actions}
    for action in result.recommended_actions:
        assert action.model_dump(exclude={"priority"}) == originals[action.action_id].model_dump(exclude={"priority"})
        assert action.requires_approval
    assert result.risk_level == baseline.risk_level
    assert result.currency == baseline.currency
    assert result.evidence_ids == baseline.evidence_ids
    assert result.is_demo is True
    assert result.assumptions[:len(baseline.assumptions)] == baseline.assumptions
    assert analysis_request.model_dump_json() == before
    assert RescueResponse.model_validate_json(result.model_dump_json()) == result


@pytest.mark.parametrize("empty", [True, False])
def test_no_current_evidence_skips_provider(request_data, empty):
    if empty:
        request_data["forecast"].update(days=[], first_reserve_breach_date=None)
    else:
        request_data["as_of_date"] = "2026-10-24"
    analysis_request = RescueAnalysisRequest.model_validate(request_data)
    def should_not_run(baseline):
        pytest.fail("Unknown risk should not invoke a provider")
    provider = FakeProvider(should_not_run)
    result = run(analysis_request, provider)
    assert result == analyze_fallback(analysis_request)
    assert result.risk_level == "unknown"
    assert provider.calls == 0


@pytest.mark.parametrize("risk,balance,point", [
    ("low", 100001, "above_reserve"), ("medium", 100000, "reserve_boundary"),
])
def test_nonbreach_ai_explanations(request_data, risk, balance, point):
    request_data["forecast"]["days"][0].update(opening_balance_cents=balance,
        receipts_cents=0, expenses_cents=0, closing_balance_cents=balance)
    request_data["forecast"]["first_reserve_breach_date"] = None
    analysis_request = RescueAnalysisRequest.model_validate(request_data)
    provider = FakeProvider(lambda baseline: ProviderDecision(
        action_ids=[action.action_id for action in baseline.recommended_actions],
        explanation_points=[point]))
    result = run(analysis_request, provider)
    assert result.risk_level == risk
    assert result.source == "ai"
    assert "potential reserve breach" not in result.summary
    expected = "remain above the reserve" if risk == "low" else "reaches the reserve"
    assert expected in result.summary


@pytest.mark.parametrize("error", [
    ProviderError("PROVIDER_TIMEOUT"), ProviderError("RATE_LIMITED"),
    ProviderError("PROVIDER_UNAVAILABLE"), ProviderError("INVALID_RESPONSE"),
    TimeoutError("private timeout"), RuntimeError("API_KEY=private-secret"),
    AttributeError("broken custom provider"),
])
def test_provider_failure_returns_unchanged_facts_and_sanitized_notice(analysis_request, error):
    def fail(baseline):
        raise error
    result = run(analysis_request, FakeProvider(fail))
    baseline = analyze_fallback(analysis_request)
    assert result.source == "deterministic"
    assert result.summary == baseline.summary
    assert result.recommended_actions == baseline.recommended_actions
    assert result.evidence_ids == baseline.evidence_ids
    assert result.assumptions[:-1] == baseline.assumptions
    assert "unavailable or rejected" in result.assumptions[-1]
    assert "private" not in result.model_dump_json()
    assert "API_KEY" not in result.model_dump_json()


@pytest.mark.parametrize("bad", [
    None, "not a decision", [], {},
    {"action_ids": [], "explanation_points": ["reserve_breach"]},
    {"action_ids": ["follow_up:INV-1"], "explanation_points": ["reserve_breach"]},
    {"action_ids": ["invented"], "explanation_points": ["reserve_breach"]},
    {"action_ids": ["follow_up:INV-1", "follow_up:INV-1"], "explanation_points": ["reserve_breach"]},
    {"action_ids": ["follow_up:INV-1", "review_expense:WAGES-1"], "explanation_points": ["above_reserve"]},
    {"action_ids": ["follow_up:INV-1", "review_expense:WAGES-1"], "explanation_points": ["overdue_invoices"]},
    {"action_ids": ["follow_up:INV-1", "review_expense:WAGES-1"], "explanation_points": ["reserve_breach", "reserve_breach"]},
    {"action_ids": ["follow_up:INV-1", "review_expense:WAGES-1"], "explanation_points": ["reserve_breach"], "estimated_impact_cents": 999999},
    {"action_ids": ["follow_up:INV-1", "review_expense:WAGES-1"], "explanation_points": ["reserve_breach"], "payment_status": "paid"},
    {"action_ids": ["follow_up:INV-1", "review_expense:WAGES-1"], "explanation_points": ["customer_will_pay"]},
])
def test_untrusted_provider_output_returns_fallback(analysis_request, bad):
    result = run(analysis_request, FakeProvider(lambda baseline: bad))
    baseline = analyze_fallback(analysis_request)
    assert result.source == "deterministic"
    assert result.summary == baseline.summary
    assert result.recommended_actions == baseline.recommended_actions


def test_mutated_decision_model_is_revalidated(analysis_request, monkeypatch):
    observed = []
    mutated = []
    original_validator = rescue_service.validate_decision
    def spy(value, context):
        observed.append(value)
        return original_validator(value, context)
    monkeypatch.setattr(rescue_service, "validate_decision", spy)
    def select(baseline):
        decision = decision_for(baseline)
        decision.explanation_points = ["invented_code"]
        mutated.append(decision.explanation_points.copy())
        return decision
    provider = FakeProvider(select)
    result = run(analysis_request, provider)
    assert provider.calls == 1
    assert mutated == [["invented_code"]]
    assert len(observed) == 1
    assert observed[0]["explanation_points"] == ["invented_code"]
    assert result.source == "deterministic"
    assert "invented_code" not in result.model_dump_json()


def test_constructed_decision_cannot_bypass_validation(analysis_request):
    provider = FakeProvider(lambda baseline: ProviderDecision.model_construct(
        action_ids=["follow_up:INV-1", "review_expense:WAGES-1"],
        explanation_points=["reserve_breach"], payment_status="paid"))
    # model_construct ignores extra fields; valid selections still follow AI path.
    result = run(analysis_request, provider)
    assert result.source == "ai"
    assert [action.action_id for action in result.recommended_actions] == [
        "follow_up:INV-1", "review_expense:WAGES-1"]
    assert "payment_status" not in result.model_dump_json()
    assert all(action.requires_approval for action in result.recommended_actions)


def test_constructed_invalid_decision_is_rejected(analysis_request):
    provider = FakeProvider(lambda baseline: ProviderDecision.model_construct(
        action_ids=["invented"], explanation_points=["customer_will_pay"]))
    result = run(analysis_request, provider)
    assert result.source == "deterministic"
    assert result.recommended_actions == analyze_fallback(analysis_request).recommended_actions


def test_provider_mutation_of_copy_cannot_change_trusted_facts(analysis_request):
    before = analysis_request.model_dump_json()
    baseline = analyze_fallback(analysis_request)
    def malicious(copy):
        decision = decision_for(copy)
        copy.summary = "All payments completed; spend freely."
        copy.currency = "EUR"
        copy.risk_level = "low"
        copy.is_demo = False
        copy.evidence_ids.clear()
        copy.assumptions.clear()
        for action in copy.recommended_actions:
            action.estimated_impact_cents = 999999
            action.requires_approval = False
            action.evidence_ids.clear()
            action.assumptions.clear()
        copy.recommended_actions.clear()
        return decision
    provider = FakeProvider(malicious)
    result = run(analysis_request, provider)
    assert result.source == "ai"
    assert result.currency == "USD" and result.risk_level == "high" and result.is_demo
    assert result.evidence_ids == baseline.evidence_ids
    assert "All payments completed" not in result.summary
    assert analysis_request.model_dump_json() == before
    for action in result.recommended_actions:
        assert action.estimated_impact_cents != 999999
        assert action.requires_approval and action.assumptions and action.evidence_ids


def test_provider_mutation_then_failure_still_returns_trusted_fallback(analysis_request):
    def malicious(copy):
        copy.summary = "private-secret"
        copy.recommended_actions.clear()
        raise RuntimeError("private-secret")
    result = run(analysis_request, FakeProvider(malicious))
    assert result.recommended_actions == analyze_fallback(analysis_request).recommended_actions
    assert "private-secret" not in result.model_dump_json()


def test_total_service_timeout_handles_custom_provider(analysis_request):
    class SlowProvider:
        cancelled = False
        async def analyze(self, baseline):
            try:
                await asyncio.sleep(1)
            finally:
                self.cancelled = True
            return decision_for(baseline)
    provider = SlowProvider()
    result = run(analysis_request, provider, timeout_seconds=0.01)
    assert result.source == "deterministic"
    assert provider.cancelled


def test_caller_cancellation_is_not_swallowed(analysis_request):
    async def scenario():
        started = asyncio.Event()
        class WaitingProvider:
            async def analyze(self, baseline):
                started.set()
                await asyncio.Event().wait()
        task = asyncio.create_task(analyze_rescue(analysis_request, WaitingProvider()))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(scenario())


@pytest.mark.parametrize("bad", [0, -1, 61, True, "15", None,
    float("nan"), float("inf"), 10**400, -(10**400)])
@pytest.mark.parametrize("with_provider", [True, False])
def test_invalid_timeout_is_configuration_error(analysis_request, bad, with_provider):
    provider = FakeProvider(decision_for) if with_provider else None
    with pytest.raises(ValueError, match="timeout_seconds"):
        run(analysis_request, provider, timeout_seconds=bad)
    if provider is not None:
        assert provider.calls == 0


@pytest.mark.parametrize("bad", ["amount", "balance", "currency", "duplicate"])
def test_invalid_request_not_hidden_by_provider_fallback(analysis_request, bad):
    if bad == "amount":
        analysis_request.invoices[0].outstanding_amount_cents = -1
    elif bad == "balance":
        analysis_request.forecast.days[0].closing_balance_cents = 999
    elif bad == "currency":
        analysis_request.invoices[0].currency = "EUR"
    else:
        analysis_request.invoices.append(analysis_request.invoices[0])
    provider = FakeProvider(decision_for)
    with pytest.raises(ValidationError):
        run(analysis_request, provider)
    assert provider.calls == 0


@pytest.mark.parametrize("code", [200, 429, 503])
def test_service_with_real_adapter_and_mocked_http(analysis_request, code):
    seen = []
    def handler(http_request):
        seen.append(http_request)
        body = json.loads(http_request.content)
        context = json.loads(body["messages"][1]["content"])
        selected = {"action_ids": [item["action_id"] for item in reversed(context["candidates"])],
                    "explanation_points": ["reserve_breach", "collection_uncertain"]}
        return httpx.Response(code, json={"choices": [{"finish_reason": "stop",
            "message": {"content": json.dumps(selected)}}]})
    provider = ChatCompletionsProvider(base_url="https://mock.example/v1", model="test",
        api_key="test-secret", transport=httpx.MockTransport(handler))
    result = run(analysis_request, provider)
    assert len(seen) == 1
    assert result.source == ("ai" if code == 200 else "deterministic")
    assert "USD 400.00 below" in result.summary
    assert "test-secret" not in result.model_dump_json()


def test_concurrent_calls_have_independent_results(analysis_request):
    async def scenario():
        provider = FakeProvider(decision_for)
        first, second = await asyncio.gather(
            analyze_rescue(analysis_request, provider), analyze_rescue(analysis_request, provider))
        assert first == second
        first.recommended_actions[0].assumptions.clear()
        assert second.recommended_actions[0].assumptions
        assert provider.calls == 2
    asyncio.run(scenario())


def test_no_environment_provider_is_created_implicitly(analysis_request, monkeypatch):
    monkeypatch.setenv("AI_BASE_URL", "https://must-not-call.example/v1")
    monkeypatch.setenv("AI_API_KEY", "must-not-read-secret")
    result = run(analysis_request)
    assert result == analyze_fallback(analysis_request)
    assert "must-not-read-secret" not in result.model_dump_json()


@pytest.mark.parametrize("ids,points", [
    (["ghost"], ["reserve_breach"]),
    (["follow_up:INV-1"], ["reserve_breach"]),
    (["follow_up:INV-1", "follow_up:INV-1"], ["reserve_breach"]),
    (["follow_up:INV-1", "review_expense:WAGES-1"], ["unknown_code"]),
    (["follow_up:INV-1", "review_expense:WAGES-1"], ["above_reserve"]),
    (["follow_up:INV-1", "review_expense:WAGES-1"], []),
    (["follow_up:INV-1", "review_expense:WAGES-1"], ["reserve_breach", "reserve_breach"]),
])
def test_assembly_defends_against_weakened_validator(analysis_request, monkeypatch, ids, points):
    monkeypatch.setattr(rescue_service, "validate_decision",
        lambda value, context: SimpleNamespace(action_ids=ids, explanation_points=points))
    result = run(analysis_request, FakeProvider(decision_for))
    baseline = analyze_fallback(analysis_request)
    assert result.source == "deterministic"
    assert result.summary == baseline.summary
    assert result.recommended_actions == baseline.recommended_actions


def test_missing_explanation_template_returns_fallback(analysis_request, monkeypatch):
    monkeypatch.delitem(rescue_service._EXPLANATIONS, "reserve_breach")
    result = run(analysis_request, FakeProvider(decision_for))
    assert result.source == "deterministic"
    assert result.summary == analyze_fallback(analysis_request).summary


def test_final_output_validation_failure_returns_fallback(analysis_request, monkeypatch):
    # Whitespace is an invalid summary. Force it during AI assembly only;
    # the existing deterministic baseline remains valid.
    original_join_template = rescue_service._EXPLANATIONS["reserve_breach"]
    original_validator = RescueResponse.model_validate.__func__
    def validate(cls, value, *args, **kwargs):
        if isinstance(value, dict) and value.get("source") == "ai":
            invalid = dict(value, summary="   ")
            return original_validator(cls, invalid, *args, **kwargs)
        return original_validator(cls, value, *args, **kwargs)
    monkeypatch.setattr(RescueResponse, "model_validate", classmethod(validate))
    result = run(analysis_request, FakeProvider(decision_for))
    assert result.source == "deterministic"
    assert result.summary == analyze_fallback(analysis_request).summary
    assert rescue_service._EXPLANATIONS["reserve_breach"] == original_join_template


def test_empty_actions_allow_a_supported_ai_explanation(request_data):
    request_data["forecast"]["days"][0].update(opening_balance_cents=200000,
        receipts_cents=0, expenses_cents=0, closing_balance_cents=200000)
    request_data["forecast"]["first_reserve_breach_date"] = None
    analysis_request = RescueAnalysisRequest.model_validate(request_data)
    provider = FakeProvider(lambda baseline: ProviderDecision(
        action_ids=[], explanation_points=["above_reserve"]))
    result = run(analysis_request, provider)
    assert provider.calls == 1
    assert result.source == "ai"
    assert result.recommended_actions == []
    assert "remain above the reserve" in result.summary
    assert not any("unavailable or rejected" in note for note in result.assumptions)


def test_upcoming_expense_explanation_is_rendered(analysis_request):
    provider = FakeProvider(lambda baseline: ProviderDecision(
        action_ids=[action.action_id for action in baseline.recommended_actions],
        explanation_points=["reserve_breach", "upcoming_expenses"]))
    result = run(analysis_request, provider)
    assert result.source == "ai"
    assert "Upcoming projected expenses can be reviewed with the scenario engine" in result.summary
    assert all(action.requires_approval for action in result.recommended_actions)


def test_multiple_actions_keep_all_records_and_sequential_priorities(analysis_request):
    invoice = analysis_request.invoices[0].model_copy(deep=True)
    invoice.invoice_id = "INV-2"
    analysis_request.invoices.append(invoice)
    expense = analysis_request.transactions[0].model_copy(deep=True)
    expense.transaction_id = "RENT-1"
    analysis_request.transactions.append(expense)
    baseline = analyze_fallback(analysis_request)
    result = run(analysis_request, FakeProvider(decision_for))
    assert result.source == "ai"
    assert len(result.recommended_actions) == 4
    assert [action.action_id for action in result.recommended_actions] == [
        action.action_id for action in reversed(baseline.recommended_actions)]
    assert [action.priority for action in result.recommended_actions] == [1, 2, 3, 4]
    assert set(result.evidence_ids) == set(baseline.evidence_ids)


def test_provider_receives_independent_nested_objects(analysis_request, monkeypatch):
    baseline = analyze_fallback(analysis_request)
    monkeypatch.setattr(rescue_service, "analyze_fallback", lambda value: baseline)
    provider = FakeProvider(decision_for)
    result = run(analysis_request, provider)
    assert result.source == "ai"
    assert provider.received is not baseline
    assert provider.received.assumptions is not baseline.assumptions
    assert provider.received.recommended_actions[0] is not baseline.recommended_actions[0]
    assert provider.received.recommended_actions[0].assumptions is not baseline.recommended_actions[0].assumptions


def test_sync_provider_misconfiguration_falls_back(analysis_request):
    class SyncProvider:
        def analyze(self, baseline):
            return decision_for(baseline)
    result = run(analysis_request, SyncProvider())
    assert result.source == "deterministic"
    assert result.summary == analyze_fallback(analysis_request).summary


def test_provider_originated_cancellation_propagates(analysis_request):
    def cancel(baseline):
        raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        run(analysis_request, FakeProvider(cancel))


def test_fallback_construction_does_not_chain_provider_exception(analysis_request, monkeypatch):
    def fail(baseline):
        raise RuntimeError("private-provider-secret")
    original_validator = RescueResponse.model_validate.__func__
    def validate(cls, value, *args, **kwargs):
        if isinstance(value, dict) and any(
            "AI analysis was unavailable" in item for item in value.get("assumptions", [])
        ):
            raise ValueError("simulated local schema failure")
        return original_validator(cls, value, *args, **kwargs)
    monkeypatch.setattr(RescueResponse, "model_validate", classmethod(validate))
    with pytest.raises(ValueError, match="local schema failure") as caught:
        run(analysis_request, FakeProvider(fail))
    assert caught.value.__context__ is None
