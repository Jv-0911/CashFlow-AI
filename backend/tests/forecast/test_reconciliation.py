from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from backend.app.forecast import (
    CashForecastRequest, CategoryScheduleCoverage, ScheduledCashEvent, VerifiedOpeningBalance,
    aggregate_daily, ingest_csv,
)
from backend.app.forecast.reconciliation import reconcile_history


START = date(2026, 10, 13)


def categorized_request(count=42, *, trend=False, alternating=False):
    first = START - timedelta(days=count)
    rows = ["transaction_id,date,amount_cents,direction,currency,category,payment_status"]
    for i in range(count):
        day = (first + timedelta(days=i)).isoformat()
        sales = (200 if i % 2 == 0 else 0) if alternating else 100 + 20*i if trend else 100
        rows.extend((f"sale_{i},{day},{sales},inflow,USD,sales,settled",
                     f"invoice_paid_{i},{day},50,inflow,USD,invoices,settled",
                     f"expense_{i},{day},20,outflow,USD,operations,settled",
                     f"supplier_paid_{i},{day},30,outflow,USD,suppliers,settled"))
    source = ingest_csv("\n".join(rows))
    history = aggregate_daily(source, coverage_start=first, coverage_end=START - timedelta(days=1), complete_coverage=True)
    events = (
        ScheduledCashEvent(event_id="invoice_future", source_id="inv_future", direction="inflow", amount_cents=500,
            currency="USD", category="invoices", status="invoice_unpaid", expected_date=START,
            projection_assumption="Customer supplies a projected collection date; payment remains unverified."),
        ScheduledCashEvent(event_id="supplier_future", source_id="bill_future", direction="outflow", amount_cents=1400,
            currency="USD", category="suppliers", status="scheduled_expense", expected_date=START + timedelta(days=1)),
    )
    coverage = tuple(CategoryScheduleCoverage(category=category, direction=direction, evidence_id=f"schedule_{category}",
                     complete_for_forecast_window=True) for category, direction in (("invoices", "inflow"), ("suppliers", "outflow")))
    return CashForecastRequest(history=history, historical_transactions=source,
        opening_balance=VerifiedOpeningBalance(balance_cents=1000, currency="USD", balance_date=START, evidence_id="bank_snapshot"),
        safety_reserve_cents=800, forecast_start_date=START, known_events=events, category_coverage=coverage,
        business_timezone="America/Chicago")


def test_exact_category_residual_does_not_double_count_receivables_or_bills():
    request = categorized_request()
    before = request.model_dump_json()
    residual, report = reconcile_history(request)
    assert report.status == "residual_categories" and report.fully_reconciled
    assert all(day.inflow_cents == 100 and day.outflow_cents == 20 for day in residual.days)
    assert len(report.excluded_historical_transaction_ids) == 84
    assert all(identifier.startswith(("invoice_paid_", "supplier_paid_")) for identifier in report.excluded_historical_transaction_ids)
    assert all("invoice_paid_0" not in day.evidence_ids for day in residual.days)
    assert all(item.included for item in report.event_dispositions)
    assert request.model_dump_json() == before


@pytest.mark.parametrize("change", ["no_source", "no_coverage", "missing_event_category", "missing_history_category", "incomplete_history"])
def test_unproven_separation_uses_labeled_known_only_fallback(change):
    request = categorized_request()
    if change == "no_source":
        request = request.model_copy(update={"historical_transactions": None})
    elif change == "no_coverage":
        request = request.model_copy(update={"category_coverage": ()})
    elif change == "missing_event_category":
        event = request.known_events[0].model_copy(update={"category": None})
        request = request.model_copy(update={"known_events": (event, request.known_events[1])})
    elif change == "missing_history_category":
        source = request.historical_transactions
        transactions = tuple(tx.model_copy(update={"category": None}) if tx.transaction_id == "sale_0" else tx for tx in source.transactions)
        request = request.model_copy(update={"historical_transactions": source.model_copy(update={"transactions": transactions})})
    else:
        history = request.history.model_copy(update={"complete_coverage": False, "coverage_start": None, "coverage_end": None})
        request = request.model_copy(update={"history": history})
    _, report = reconcile_history(request)
    assert report.status == "known_only_fallback" and not report.fully_reconciled
    assert report.inflow_policy == "known_events_only"
    assert any("unproven" in warning for warning in report.warnings)


@pytest.mark.parametrize("flag", [False, 1, "true"])
def test_partial_schedule_coverage_is_not_accepted(flag):
    with pytest.raises(ValidationError):
        CategoryScheduleCoverage(category="invoices", direction="inflow", evidence_id="scope", complete_for_forecast_window=flag)


@pytest.mark.parametrize("duplicate", ["event_id", "source_id", "coverage"])
def test_duplicate_event_source_and_coverage_identifiers(duplicate):
    request = categorized_request()
    if duplicate == "coverage":
        request = request.model_copy(update={"category_coverage": request.category_coverage + request.category_coverage[:1]})
    else:
        a, b = request.known_events
        request = request.model_copy(update={"known_events": (a, b.model_copy(update={duplicate: getattr(a, duplicate)}))})
    with pytest.raises(ValueError, match="duplicate"):
        reconcile_history(request)


@pytest.mark.parametrize("status", ["verified_completed", "cancelled", "failed"])
def test_completed_cancelled_and_failed_events_are_not_projected(status):
    request = categorized_request()
    event = request.known_events[0].model_copy(update={"status": status, "verification_evidence_id": "provider_record"})
    request = request.model_copy(update={"known_events": (event, request.known_events[1])})
    _, report = reconcile_history(request)
    assert not report.event_dispositions[0].included
    assert status in report.event_dispositions[0].reason


def test_already_settled_historical_receipt_does_not_become_future_invoice():
    request = categorized_request()
    event = request.known_events[0].model_copy(update={"historical_transaction_id": "invoice_paid_0"})
    request = request.model_copy(update={"known_events": (event, request.known_events[1])})
    _, report = reconcile_history(request)
    assert not report.event_dispositions[0].included
    assert "settled history" in report.event_dispositions[0].reason


def test_historical_daily_evidence_also_prevents_duplicate_completed_receipt():
    request = categorized_request()
    event = request.known_events[0].model_copy(update={"source_id": "invoice_paid_0"})
    request = request.model_copy(update={"historical_transactions": None, "known_events": (event,)})
    _, report = reconcile_history(request)
    assert not report.event_dispositions[0].included


def test_explicit_link_cannot_hide_a_source_id_already_settled():
    request = categorized_request()
    event = request.known_events[0].model_copy(update={"source_id": "invoice_paid_0", "historical_transaction_id": "other_record"})
    request = request.model_copy(update={"known_events": (event, request.known_events[1])})
    _, report = reconcile_history(request)
    assert not report.event_dispositions[0].included


def test_two_events_cannot_share_a_historical_transaction_link():
    request = categorized_request()
    a, b = request.known_events
    request = request.model_copy(update={"known_events": (
        a.model_copy(update={"historical_transaction_id": "pending_record"}),
        b.model_copy(update={"historical_transaction_id": "pending_record"}),
    )})
    with pytest.raises(ValueError, match="duplicate historical"):
        reconcile_history(request)


@pytest.mark.parametrize("field,value,reason", [
    ("expected_date", None, "unknown expected"),
    ("projection_assumption", None, "no explicit payment assumption"),
    ("expected_date", START - timedelta(days=1), "outside"),
    ("expected_date", START + timedelta(days=2), "outside"),
])
def test_unknown_unassumed_or_out_of_window_receipts_are_not_invented(field, value, reason):
    request = categorized_request()
    event = request.known_events[0].model_copy(update={field: value, "due_date": START})
    request = request.model_copy(update={"known_events": (event, request.known_events[1])})
    _, report = reconcile_history(request)
    assert not report.event_dispositions[0].included
    assert reason in report.event_dispositions[0].reason


@pytest.mark.parametrize("status", ["pending_verification", "overdue_receivable"])
def test_unverified_payment_with_explicit_assumption_preserves_status(status):
    request = categorized_request()
    event = request.known_events[0].model_copy(update={"status": status})
    request = request.model_copy(update={"known_events": (event, request.known_events[1])})
    _, report = reconcile_history(request)
    assert report.event_dispositions[0].included
    assert report.event_dispositions[0].event.status == status
    assert any("unverified projected" in warning for warning in report.warnings)


def test_source_must_reproduce_daily_totals_before_any_category_exclusion():
    request = categorized_request()
    days = (request.history.days[0].model_copy(update={"inflow_cents": 9999}),) + request.history.days[1:]
    request = request.model_copy(update={"history": request.history.model_copy(update={"days": days})})
    with pytest.raises(ValueError, match="reproduce"):
        reconcile_history(request)


@pytest.mark.parametrize("change", [{"status": "COMPLETED"}, {"status": "verified_completed"},
    {"direction": "outflow", "status": "invoice_unpaid"}, {"event_id": " "},
    {"amount_cents": True}, {"amount_cents": -1}, {"expected_date": "2026-10-13T00:00:00Z"}])
def test_invalid_event_contracts_fail_validation(change):
    event = categorized_request().known_events[0].model_dump()
    event.update(change)
    with pytest.raises(ValidationError):
        ScheduledCashEvent.model_validate(event)
