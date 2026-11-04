"""Provider checks use only MockTransport; no live credentials or API calls."""

import asyncio
import json

import httpx
import pytest
from pydantic import ValidationError

from backend.app.rescue_ai.provider import (
    ChatCompletionsProvider, ProviderDecision, ProviderError,
    build_provider_context, validate_decision,
)
from backend.app.rescue_ai.schemas import RecoveryAction, RescueResponse


@pytest.fixture
def baseline():
    return RescueResponse(
        summary="Projected cash may fall below the reserve.", risk_level="high",
        evidence_ids=["FC-1", "INV-1", "TX-1"], currency="USD", is_demo=True,
        recommended_actions=[
            RecoveryAction(action_id="follow_up:INV-1", title="Review invoice",
                estimated_impact_cents=80000, assumptions=["Collection is uncertain."],
                explanation="PRIVATE CUSTOMER NOTE", evidence_ids=["INV-1"],
                currency="USD", priority=1),
            RecoveryAction(action_id="review_expense:TX-1", title="Review expense",
                estimated_impact_cents=None, assumptions=["Payee approval required."],
                evidence_ids=["TX-1"], currency="USD", priority=2),
        ],
    )


@pytest.fixture
def selection():
    return {"action_ids": ["review_expense:TX-1", "follow_up:INV-1"],
            "explanation_points": ["reserve_breach", "collection_uncertain"]}


def envelope(content, finish="stop"):
    return {"choices": [{"finish_reason": finish, "message": {"content": content}}]}


def provider(handler, **options):
    return ChatCompletionsProvider(
        base_url="https://mock.example/v1/", model="test-model", api_key="test-secret",
        transport=httpx.MockTransport(handler), **options,
    )


def run(adapter, baseline):
    return asyncio.run(adapter.analyze(baseline))


def test_http_success_request_shape_and_minimal_context(baseline, selection):
    calls = []
    before = baseline.model_dump_json()
    def handler(request):
        calls.append(request)
        assert request.method == "POST"
        assert str(request.url) == "https://mock.example/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-secret"
        body = json.loads(request.content)
        assert body["model"] == "test-model"
        assert body["response_format"] == {"type": "json_object"}
        context = json.loads(body["messages"][1]["content"])
        assert context["is_demo"] is True
        assert context["candidates"][0]["estimated_impact_cents"] == 80000
        assert "PRIVATE CUSTOMER NOTE" not in json.dumps(body)
        assert "test-secret" not in json.dumps(body)
        return httpx.Response(200, json=envelope(json.dumps(selection)))
    decision = run(provider(handler), baseline)
    assert decision.action_ids == selection["action_ids"]
    assert len(calls) == 1
    assert baseline.model_dump_json() == before


@pytest.mark.parametrize("status,code", [
    (429, "RATE_LIMITED"), (401, "PROVIDER_UNAVAILABLE"),
    (403, "PROVIDER_UNAVAILABLE"), (500, "PROVIDER_UNAVAILABLE"),
    (503, "PROVIDER_UNAVAILABLE"), (302, "PROVIDER_UNAVAILABLE"),
])
def test_http_errors_sanitized_without_retries(baseline, status, code):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, text="private upstream body test-secret",
                              headers={"location": "https://elsewhere.example"})
    with pytest.raises(ProviderError) as caught:
        run(provider(handler), baseline)
    assert caught.value.code == code
    assert str(caught.value) == code
    assert len(calls) == 1


@pytest.mark.parametrize("exception,code", [
    (httpx.ReadTimeout, "PROVIDER_TIMEOUT"),
    (httpx.ConnectTimeout, "PROVIDER_TIMEOUT"),
    (httpx.ConnectError, "PROVIDER_UNAVAILABLE"),
    (httpx.RemoteProtocolError, "PROVIDER_UNAVAILABLE"),
])
def test_transport_failure(baseline, exception, code):
    def handler(request):
        raise exception("private details", request=request)
    with pytest.raises(ProviderError, match=code):
        run(provider(handler), baseline)


def test_total_deadline(baseline, selection):
    async def handler(request):
        await asyncio.sleep(0.1)
        return httpx.Response(200, json=envelope(json.dumps(selection)))
    with pytest.raises(ProviderError, match="PROVIDER_TIMEOUT"):
        run(provider(handler, timeout_seconds=0.01), baseline)


@pytest.mark.parametrize("body", [
    b"not JSON", b"{}", b'{"choices": []}', b'{"choices": {}}',
    b'{"choices": [{"finish_reason":"stop"}]}',
    json.dumps(envelope("not JSON")).encode(),
    json.dumps(envelope(None)).encode(),
    json.dumps(envelope({})).encode(),
    json.dumps(envelope("{}")).encode(),
    json.dumps(envelope("```json\n{}\n```")).encode(),
    b'{"choices": [null]}', b'{"choices": ["bad"]}',
])
def test_malformed_responses_are_controlled_errors(baseline, body):
    with pytest.raises(ProviderError, match="INVALID_RESPONSE"):
        run(provider(lambda request: httpx.Response(200, content=body)), baseline)


@pytest.mark.parametrize("finish", ["length", "content_filter", None])
def test_incomplete_response(baseline, selection, finish):
    with pytest.raises(ProviderError, match="INCOMPLETE_RESPONSE"):
        run(provider(lambda request: httpx.Response(200,
            json=envelope(json.dumps(selection), finish))), baseline)


def test_response_size_bound(baseline):
    with pytest.raises(ProviderError, match="RESPONSE_TOO_LARGE"):
        run(provider(lambda request: httpx.Response(200, content=b"x" * 128001)), baseline)


@pytest.mark.parametrize("ids", [[], ["invented"],
    ["follow_up:INV-1", "follow_up:INV-1"],
    ["follow_up:INV-1", "review_expense:TX-1", "extra"]])
def test_incomplete_duplicate_or_invented_actions_rejected(baseline, selection, ids):
    selection["action_ids"] = ids
    with pytest.raises(ProviderError, match="UNSUPPORTED_ACTIONS"):
        run(provider(lambda request: httpx.Response(200,
            json=envelope(json.dumps(selection)))), baseline)


@pytest.mark.parametrize("points", [["above_reserve"], ["collection_uncertain"],
    ["reserve_breach", "reserve_breach"]])
def test_unsupported_duplicate_or_missing_primary_explanation(baseline, selection, points):
    selection["explanation_points"] = points
    with pytest.raises(ProviderError, match="UNSUPPORTED_EXPLANATION"):
        validate_decision(selection, build_provider_context(baseline))


def test_extra_financial_claim_rejected(baseline, selection):
    selection["payment_status"] = "paid"
    with pytest.raises(ProviderError, match="INVALID_RESPONSE"):
        run(provider(lambda request: httpx.Response(200,
            json=envelope(json.dumps(selection)))), baseline)


@pytest.mark.parametrize("risk,point", [("low", "above_reserve"),
    ("medium", "reserve_boundary"), ("high", "reserve_breach"),
    ("unknown", "insufficient_evidence")])
def test_primary_explanation_mapping(risk, point):
    baseline = RescueResponse(summary="Supplied summary", risk_level=risk,
                              evidence_ids=[], recommended_actions=[])
    context = build_provider_context(baseline)
    assert context["allowed_explanation_points"] == [point]
    assert validate_decision({"action_ids": [], "explanation_points": [point]}, context)


@pytest.mark.parametrize("options", [
    {"base_url": "http://mock.example/v1"}, {"base_url": ""},
    {"base_url": "https://user:password@mock.example/v1"},
    {"base_url": "https://mock.example/v1?key=secret"},
    {"base_url": "https://mock.example/v1#fragment"},
    {"model": " "}, {"api_key": ""}, {"timeout_seconds": 0},
    {"timeout_seconds": -1}, {"timeout_seconds": 61},
    {"timeout_seconds": float("nan")},
])
def test_invalid_configuration(options):
    settings = dict(base_url="https://mock.example/v1", model="test", api_key="secret")
    settings.update(options)
    with pytest.raises(ProviderError, match="INVALID_CONFIGURATION"):
        ChatCompletionsProvider(**settings)


def test_configuration_from_environment(monkeypatch):
    monkeypatch.setenv("AI_BASE_URL", "https://mock.example/v1")
    monkeypatch.setenv("AI_MODEL", "configured-model")
    monkeypatch.setenv("AI_API_KEY", "private-key")
    monkeypatch.setenv("AI_TIMEOUT_SECONDS", "2.5")
    adapter = ChatCompletionsProvider.from_env()
    assert adapter._timeout == 2.5
    assert adapter._model == "configured-model"
    assert "private-key" not in repr(adapter._key)


@pytest.mark.parametrize("timeout", ["not-a-number", "0"])
def test_bad_environment_timeout(monkeypatch, timeout):
    monkeypatch.setenv("AI_BASE_URL", "https://mock.example/v1")
    monkeypatch.setenv("AI_MODEL", "test")
    monkeypatch.setenv("AI_API_KEY", "secret")
    monkeypatch.setenv("AI_TIMEOUT_SECONDS", timeout)
    with pytest.raises(ProviderError, match="INVALID_CONFIGURATION"):
        ChatCompletionsProvider.from_env()


def test_missing_environment_configuration(monkeypatch):
    for key in ["AI_BASE_URL", "AI_MODEL", "AI_API_KEY", "AI_TIMEOUT_SECONDS"]:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ProviderError, match="INVALID_CONFIGURATION"):
        ChatCompletionsProvider.from_env()


@pytest.mark.parametrize("large_id", [False, True])
def test_context_limits_prevent_http_calls(baseline, large_id):
    if large_id:
        baseline.recommended_actions[0].action_id = "follow_up:" + "x" * 64000
    else:
        template = baseline.recommended_actions[0]
        baseline.recommended_actions = [template.model_copy(update={"action_id": f"follow_up:I-{i}"}) for i in range(201)]
    def unexpected(request):
        pytest.fail("Oversized context must not reach HTTP transport")
    with pytest.raises(ProviderError, match="CONTEXT_TOO_LARGE"):
        run(provider(unexpected), baseline)


def test_decision_schema_rejects_arbitrary_explanation_code():
    with pytest.raises(ValidationError):
        ProviderDecision(action_ids=[], explanation_points=["customer_will_pay"])
