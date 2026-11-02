"""Isolated fallback behavior tests: no API, provider, or shared fixtures."""

from datetime import date

import pytest
from pydantic import ValidationError

from backend.app.rescue_ai.fallback import analyze_fallback
from backend.app.rescue_ai.schemas import RescueAnalysisRequest, RescueResponse


@pytest.fixture
def payload():
    return {
        "as_of_date": "2026-10-21", "forecast_id": "FC-1",
        "forecast": {
            "currency": "USD", "safety_reserve_cents": 100000,
            "first_reserve_breach_date": "2026-10-22",
            "days": [{"date": "2026-10-22", "opening_balance_cents": 120000,
                      "receipts_cents": 20000, "expenses_cents": 80000,
                      "closing_balance_cents": 60000}],
        },
        "invoices": [{"invoice_id": "INV-104", "currency": "USD",
                      "outstanding_amount_cents": 80000,
                      "due_date": "2026-10-10", "status": "unpaid"}],
        "transactions": [],
    }


def analyze(payload):
    return analyze_fallback(RescueAnalysisRequest.model_validate(payload))


def invoice(record_id, amount=80000, due="2026-10-10", status="unpaid"):
    return dict(invoice_id=record_id, currency="USD", outstanding_amount_cents=amount,
                due_date=due, status=status)


def expense(record_id, amount=20000, day="2026-10-22", discretionary=False,
            status="projected", direction="expense"):
    return dict(transaction_id=record_id, currency="USD", amount_cents=amount,
                date=day, discretionary=discretionary, status=status, direction=direction)


def test_shortage_example(payload):
    result = analyze(payload)
    assert result.risk_level == "high"
    assert "USD 400.00 below the reserve" in result.summary
    assert "USD 600.00" in result.summary
    assert "2026-10-22" in result.summary
    assert result.evidence_ids == ["FC-1", "INV-104"]
    action = result.recommended_actions[0]
    assert action.estimated_impact_cents == 80000
    assert action.requires_approval is True
    assert action.evidence_ids == ["FC-1", "INV-104"]
    assert any("uncertain" in assumption for assumption in action.assumptions)
    assert any("not guaranteed" in assumption for assumption in action.assumptions)
    assert result.source == "deterministic"
    assert RescueResponse.model_validate_json(result.model_dump_json()) == result


@pytest.mark.parametrize("balance,risk", [(100001, "low"), (100000, "medium"),
                                         (99999, "high"), (-1, "high"), (0, "high")])
def test_reserve_boundaries(payload, balance, risk):
    forecast = payload["forecast"]
    forecast["days"][0].update(opening_balance_cents=balance, receipts_cents=0,
                               expenses_cents=0, closing_balance_cents=balance)
    forecast["first_reserve_breach_date"] = "2026-10-22" if risk == "high" else None
    result = analyze(payload)
    assert result.risk_level == risk
    if risk == "low":
        assert result.recommended_actions == []
        assert "does not guarantee" in result.summary


@pytest.mark.parametrize("empty", [True, False])
def test_missing_or_stale_forecast_is_unknown(payload, empty):
    if empty:
        payload["forecast"].update(days=[], first_reserve_breach_date=None)
    else:
        payload["as_of_date"] = "2026-10-23"
    result = analyze(payload)
    assert result.risk_level == "unknown"
    assert result.recommended_actions == []
    assert "Insufficient evidence" in result.summary


@pytest.mark.parametrize("status,amount", [("paid", 0), ("pending", 80000),
                                           ("cancelled", 80000), ("unpaid", 0)])
def test_nonrecoverable_invoices_excluded(payload, status, amount):
    payload["invoices"] = [invoice("I", amount=amount, status=status)]
    result = analyze(payload)
    assert result.recommended_actions == []
    assert "No eligible" in result.summary


@pytest.mark.parametrize("due", ["2026-10-21", "2026-10-22"])
def test_invoice_due_today_or_future_is_not_overdue(payload, due):
    payload["invoices"] = [invoice("I", due=due)]
    assert analyze(payload).recommended_actions == []


def test_invoice_ranking_gap_then_age_then_amount_then_id(payload):
    payload["invoices"] = [
        invoice("small-old", 10000, "2026-09-01"),
        invoice("new-large", 90000, "2026-10-20"),
        invoice("old-B", 50000, "2026-10-01"),
        invoice("old-A", 50000, "2026-10-01"),
        invoice("old-larger", 60000, "2026-10-01"),
    ]
    actions = analyze(payload).recommended_actions
    assert [action.action_id for action in actions] == [
        "follow_up:old-larger", "follow_up:old-A", "follow_up:old-B",
        "follow_up:new-large", "follow_up:small-old",
    ]
    assert [action.priority for action in actions] == list(range(1, 6))
    payload["invoices"].reverse()
    assert analyze(payload).recommended_actions == actions


def test_expense_ranking_and_no_invented_savings(payload):
    payload["transactions"] = [
        expense("essential", day="2026-10-21"),
        expense("optional-B", discretionary=True),
        expense("optional-A", discretionary=True),
        expense("optional-large", amount=30000, discretionary=True),
    ]
    result = analyze(payload)
    assert [action.action_id for action in result.recommended_actions] == [
        "follow_up:INV-104", "review_expense:optional-large",
        "review_expense:optional-A", "review_expense:optional-B",
        "review_expense:essential",
    ]
    for action in result.recommended_actions[1:]:
        assert action.estimated_impact_cents is None
        assert action.requires_approval
        assert any("scenario engine" in assumption for assumption in action.assumptions)


@pytest.mark.parametrize("event", [
    expense("verified", status="verified"), expense("cancelled", status="cancelled"),
    expense("receipt", direction="receipt"), expense("past", day="2026-10-20"),
    expense("late", day="2026-10-23"), expense("zero", amount=0),
])
def test_ineligible_expenses_excluded(payload, event):
    payload["invoices"] = []
    payload["transactions"] = [event]
    assert analyze(payload).recommended_actions == []


def test_demo_flag_and_assumptions_preserved(payload):
    payload["forecast"]["is_demo"] = True
    result = analyze(payload)
    assert result.is_demo
    assert any("demo data" in assumption for assumption in result.assumptions)


def test_no_double_counting_or_input_mutation(payload):
    # Evidence may already be represented in the forecast. Do not credit it again.
    payload["transactions"] = [expense("receipt", amount=80000, direction="receipt")]
    request = RescueAnalysisRequest.model_validate(payload)
    before = request.model_dump_json()
    first = analyze_fallback(request)
    assert analyze_fallback(request) == first
    assert request.model_dump_json() == before
    assert "USD 400.00 below the reserve" in first.summary
    assert request.invoices[0].status == "unpaid"
    assert request.forecast.days[0].closing_balance_cents == 60000
    assert not hasattr(first, "payment_status")


@pytest.mark.parametrize("failure", ["amount", "currency", "duplicate", "balance"])
def test_mutated_invalid_models_revalidated(payload, failure):
    request = RescueAnalysisRequest.model_validate(payload)
    if failure == "amount":
        request.invoices[0].outstanding_amount_cents = -1
    elif failure == "currency":
        request.invoices[0].currency = "EUR"
    elif failure == "duplicate":
        request.invoices.append(request.invoices[0])
    else:
        request.forecast.days[0].closing_balance_cents = 123
    with pytest.raises(ValidationError):
        analyze_fallback(request)


def test_past_breach_not_reported_as_future(payload):
    payload["as_of_date"] = "2026-10-23"
    payload["forecast"]["days"].append(dict(
        date="2026-10-23", opening_balance_cents=60000, receipts_cents=140000,
        expenses_cents=0, closing_balance_cents=200000))
    result = analyze(payload)
    assert result.risk_level == "low"
    assert result.recommended_actions == []
    assert "first fall below" not in result.summary


def test_first_breach_and_minimum_are_distinct(payload):
    payload["forecast"]["days"].append(dict(
        date="2026-10-23", opening_balance_cents=60000, receipts_cents=0,
        expenses_cents=50000, closing_balance_cents=10000))
    result = analyze(payload)
    assert "first fall below the safety reserve on 2026-10-22" in result.summary
    assert "USD 100.00 on 2026-10-23" in result.summary
    assert "USD 900.00 below" in result.summary
    assert "expenses total USD 1,300.00" in result.summary


def test_existing_opening_shortage_is_explained(payload):
    payload["forecast"]["days"][0].update(opening_balance_cents=60000,
        receipts_cents=0, expenses_cents=0, closing_balance_cents=60000)
    assert "opening balance is already below" in analyze(payload).summary


def test_large_integer_money_without_float_rounding(payload):
    balance = 10**18 + 1
    payload["forecast"]["days"][0].update(opening_balance_cents=balance,
        receipts_cents=0, expenses_cents=0, closing_balance_cents=balance)
    payload["forecast"]["first_reserve_breach_date"] = None
    assert "USD 10,000,000,000,000,000.01" in analyze(payload).summary


def test_action_identity_stable_when_rank_changes(payload):
    first = analyze(payload).recommended_actions[0].action_id
    payload["invoices"].append(invoice("older", 90000, "2026-09-01"))
    actions = analyze(payload).recommended_actions
    assert actions[0].action_id == "follow_up:older"
    assert actions[1].action_id == first


def test_evidence_references_resolve_to_supplied_records(payload):
    payload["transactions"] = [expense("TX-1")]
    result = analyze(payload)
    allowed = {"FC-1", "INV-104", "TX-1"}
    assert set(result.evidence_ids) == allowed
    for action in result.recommended_actions:
        assert set(action.evidence_ids) <= allowed
        assert action.currency == result.currency == "USD"
