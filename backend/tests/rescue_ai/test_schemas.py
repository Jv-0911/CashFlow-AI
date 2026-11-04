"""Self-contained rescue contract tests; no API, payment, or provider imports."""

from copy import deepcopy
from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from backend.app.rescue_ai.schemas import (
    ForecastDay, ForecastEvidence, InvoiceEvidence, RecoveryAction,
    RescueAnalysisRequest, RescueResponse, TransactionEvidence,
)


@pytest.fixture
def forecast():
    return {
        "currency": "USD", "safety_reserve_cents": 100000,
        "first_reserve_breach_date": "2026-10-16",
        "days": [{
            "date": "2026-10-16", "opening_balance_cents": 120000,
            "receipts_cents": 20000, "expenses_cents": 80000,
            "closing_balance_cents": 60000,
        }],
    }


@pytest.fixture
def invoice():
    return {
        "invoice_id": "INV-104", "currency": "USD",
        "outstanding_amount_cents": 80000, "due_date": "2026-10-10",
        "status": "unpaid",
    }


@pytest.fixture
def transaction():
    return {
        "transaction_id": "TX-1", "currency": "USD", "amount_cents": 80000,
        "date": "2026-10-16", "direction": "expense", "status": "projected",
    }


@pytest.fixture
def request_data(forecast, invoice, transaction):
    return {
        "as_of_date": "2026-10-15", "forecast_id": "FC-1",
        "forecast": forecast, "invoices": [invoice], "transactions": [transaction],
    }


@pytest.fixture
def action():
    return {
        "action_id": "follow_up_INV-104", "title": "Review overdue invoice",
        "estimated_impact_cents": 80000,
        "assumptions": ["The customer pays; timing is uncertain."],
        "evidence_ids": ["INV-104"], "currency": "USD", "priority": 1,
    }


@pytest.fixture
def response(action):
    return {
        "summary": "Projected cash may fall below the reserve.",
        "risk_level": "high", "evidence_ids": ["FC-1", "INV-104"],
        "recommended_actions": [action], "currency": "USD",
    }


def test_valid_request_and_json_round_trip(request_data):
    parsed = RescueAnalysisRequest.model_validate(request_data)
    assert parsed.as_of_date == date(2026, 10, 15)
    assert parsed.forecast.days[0].closing_balance_cents == 60000
    assert RescueAnalysisRequest.model_validate_json(parsed.model_dump_json()) == parsed


def test_valid_response_and_default_approval(response):
    parsed = RescueResponse.model_validate(response)
    assert parsed.recommended_actions[0].requires_approval is True
    assert parsed.source == "deterministic"


def test_existing_rescue_example_shape():
    # Local fixture mirrors the shared example without importing shared setup.
    parsed = RescueResponse.model_validate({
        "summary": "Projected cash may fall below the configured safety reserve.",
        "risk_level": "high", "evidence_ids": ["txn_demo_001"],
        "recommended_actions": [{
            "action_id": "action_demo_001", "title": "Follow up on an overdue invoice",
            "estimated_impact_cents": 50000,
            "assumptions": ["The customer pays the invoice in full"],
        }],
    })
    assert parsed.recommended_actions[0].estimated_impact_cents == 50000


def test_empty_forecast_and_evidence(request_data):
    request_data["forecast"].update(days=[], first_reserve_breach_date=None)
    request_data["invoices"] = []
    request_data["transactions"] = []
    parsed = RescueAnalysisRequest.model_validate(request_data)
    assert parsed.forecast.days == []
    result = RescueResponse(summary="Insufficient evidence.", risk_level="unknown",
                            evidence_ids=[], recommended_actions=[])
    assert result.risk_level == "unknown"


@pytest.mark.parametrize("balance,breach", [(100000, None), (140000, None),
                                          (-10000, "2026-10-16")])
def test_reserve_boundary_and_negative_balance(forecast, balance, breach):
    forecast["days"][0].update(opening_balance_cents=balance, receipts_cents=0,
                               expenses_cents=0, closing_balance_cents=balance)
    forecast["first_reserve_breach_date"] = breach
    assert ForecastEvidence.model_validate(forecast).days[0].closing_balance_cents == balance


@pytest.mark.parametrize("bad", [True, 1.5, "100", -1])
def test_invalid_money(invoice, bad):
    invoice["outstanding_amount_cents"] = bad
    with pytest.raises(ValidationError):
        InvoiceEvidence.model_validate(invoice)


@pytest.mark.parametrize("amount", [0, 10**18])
def test_zero_and_large_amounts(invoice, amount):
    invoice["outstanding_amount_cents"] = amount
    assert InvoiceEvidence.model_validate(invoice).outstanding_amount_cents == amount


@pytest.mark.parametrize("bad", ["2026-02-30", "not-a-date"])
def test_invalid_date(invoice, bad):
    invoice["due_date"] = bad
    with pytest.raises(ValidationError):
        InvoiceEvidence.model_validate(invoice)


@pytest.mark.parametrize("bad", ["usd", "US", "123"])
def test_invalid_currency_shape(forecast, bad):
    forecast["currency"] = bad
    with pytest.raises(ValidationError):
        ForecastEvidence.model_validate(forecast)


def test_incorrect_daily_arithmetic(forecast):
    forecast["days"][0]["closing_balance_cents"] += 1
    with pytest.raises(ValidationError, match="Daily closing balance"):
        ForecastEvidence.model_validate(forecast)


def test_incorrect_breach_date(forecast):
    forecast["first_reserve_breach_date"] = None
    with pytest.raises(ValidationError, match="Reserve breach date"):
        ForecastEvidence.model_validate(forecast)


@pytest.mark.parametrize("kind", ["gap", "duplicate", "reversed", "carry"])
def test_invalid_forecast_sequence(forecast, kind):
    second = deepcopy(forecast["days"][0])
    second.update(date="2026-10-17", opening_balance_cents=60000,
                  receipts_cents=0, expenses_cents=0, closing_balance_cents=60000)
    if kind == "gap":
        second["date"] = "2026-10-18"
    elif kind == "duplicate":
        second["date"] = "2026-10-16"
    elif kind == "reversed":
        second["date"] = "2026-10-15"
    else:
        second.update(opening_balance_cents=60001, closing_balance_cents=60001)
    forecast["days"].append(second)
    with pytest.raises(ValidationError):
        ForecastEvidence.model_validate(forecast)


@pytest.mark.parametrize("count", [30, 31])
def test_forecast_horizon(forecast, count):
    forecast["days"] = [
        dict(date=(date(2026, 10, 16) + timedelta(days=i)).isoformat(),
             opening_balance_cents=100000, receipts_cents=0, expenses_cents=0,
             closing_balance_cents=100000)
        for i in range(count)
    ]
    forecast["first_reserve_breach_date"] = None
    if count == 30:
        assert len(ForecastEvidence.model_validate(forecast).days) == 30
    else:
        with pytest.raises(ValidationError):
            ForecastEvidence.model_validate(forecast)


@pytest.mark.parametrize("collision", ["invoice", "transaction", "forecast"])
def test_duplicate_evidence_ids(request_data, collision):
    if collision == "invoice":
        request_data["invoices"].append(deepcopy(request_data["invoices"][0]))
    elif collision == "transaction":
        request_data["transactions"][0]["transaction_id"] = "INV-104"
    else:
        request_data["invoices"][0]["invoice_id"] = "FC-1"
    with pytest.raises(ValidationError, match="identifiers must be unique"):
        RescueAnalysisRequest.model_validate(request_data)


@pytest.mark.parametrize("collection", ["invoices", "transactions"])
def test_mixed_currency(request_data, collection):
    request_data[collection][0]["currency"] = "EUR"
    with pytest.raises(ValidationError, match="forecast currency"):
        RescueAnalysisRequest.model_validate(request_data)


def test_paid_invoice_cannot_have_outstanding_balance(invoice):
    invoice["status"] = "paid"
    with pytest.raises(ValidationError, match="paid invoice"):
        InvoiceEvidence.model_validate(invoice)
    invoice["outstanding_amount_cents"] = 0
    assert InvoiceEvidence.model_validate(invoice).status == "paid"


def test_pending_invoice_is_not_paid(invoice):
    invoice["status"] = "pending"
    assert InvoiceEvidence.model_validate(invoice).status == "pending"


@pytest.mark.parametrize("status", ["projected", "verified", "cancelled"])
def test_transaction_status_preserved(transaction, status):
    transaction["status"] = status
    assert TransactionEvidence.model_validate(transaction).status == status


def test_unknown_fields_and_missing_required_fields(request_data):
    request_data["api_key"] = "should-not-be-here"
    with pytest.raises(ValidationError):
        RescueAnalysisRequest.model_validate(request_data)
    with pytest.raises(ValidationError):
        RescueAnalysisRequest.model_validate({})


@pytest.mark.parametrize("field,value", [
    ("title", "   "), ("action_id", "bad id"), ("estimated_impact_cents", -1),
    ("estimated_impact_cents", True), ("priority", 0), ("assumptions", []),
])
def test_invalid_action(action, field, value):
    action[field] = value
    with pytest.raises(ValidationError):
        RecoveryAction.model_validate(action)


def test_uncalculable_impact_is_null(action):
    action["estimated_impact_cents"] = None
    assert RecoveryAction.model_validate(action).estimated_impact_cents is None


@pytest.mark.parametrize("failure", ["action_id", "evidence_id", "reference", "currency"])
def test_response_consistency(response, failure):
    if failure == "action_id":
        response["recommended_actions"].append(deepcopy(response["recommended_actions"][0]))
    elif failure == "evidence_id":
        response["evidence_ids"].append("FC-1")
    elif failure == "reference":
        response["recommended_actions"][0]["evidence_ids"] = ["UNKNOWN"]
    else:
        response["recommended_actions"][0]["currency"] = "EUR"
    with pytest.raises(ValidationError):
        RescueResponse.model_validate(response)


def test_unknown_risk_rejected(response):
    response["risk_level"] = "guaranteed_safe"
    with pytest.raises(ValidationError):
        RescueResponse.model_validate(response)


def test_request_not_mutated(request_data):
    before = deepcopy(request_data)
    RescueAnalysisRequest.model_validate(request_data)
    assert request_data == before


def test_mutable_defaults_are_independent(forecast):
    first = RescueAnalysisRequest(as_of_date="2026-10-15", forecast_id="A", forecast=forecast)
    second = RescueAnalysisRequest(as_of_date="2026-10-15", forecast_id="B", forecast=forecast)
    first.invoices.append(InvoiceEvidence(invoice_id="I", currency="USD",
        outstanding_amount_cents=0, due_date="2026-10-15", status="paid"))
    assert second.invoices == []
