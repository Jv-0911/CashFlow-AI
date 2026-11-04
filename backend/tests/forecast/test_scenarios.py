from datetime import timedelta

import pytest
from pydantic import ValidationError

from backend.app.forecast.financial_schemas import ScheduledCashEvent
from backend.app.forecast.scenario_schemas import (
    AddEventOperation, ChangeExpenseAmountOperation, ChangeProjectionOperation,
    MoveEventOperation, RemoveEventOperation, ScenarioComparison, ScenarioRequest,
)
from backend.app.forecast.scenarios import simulate_scenario
from backend.app.forecast.service import forecast_cash_flow
from backend.tests.forecast.test_reconciliation import START, categorized_request


def scenario(*operations):
    return ScenarioRequest(scenario_id="shop-recovery", operations=operations)


def move(event_id, offset, operation_id="move"):
    return MoveEventOperation(operation_id=operation_id, event_id=event_id,
        expected_date=START + timedelta(days=offset), assumption="Assume the counterparty accepts the new cash date.")


def added(amount=200, direction="outflow", offset=0, **changes):
    event = dict(event_id="hypothetical", source_id="hypothetical-source", direction=direction,
        amount_cents=amount, currency="USD", status="scheduled_expense" if direction == "outflow" else "invoice_unpaid",
        expected_date=START + timedelta(days=offset))
    event.update(changes)
    return AddEventOperation(operation_id="add", hypothetical=True,
        event=ScheduledCashEvent(**event), assumption="Assume this cash is additional to every baseline component.")


def test_move_receipt_keeps_total_and_changes_only_the_timing():
    request = categorized_request()
    baseline = forecast_cash_flow(request)
    comparison = simulate_scenario(request, scenario(move("invoice_future", 1)), baseline=baseline)
    assert [day.projected_closing_balance_cents for day in comparison.scenario.days] == [1080, 260]
    assert [item.closing_balance_difference_cents for item in comparison.daily_differences] == [-500, 0]
    assert comparison.baseline == baseline
    assert comparison.scenario.model_forecast == baseline.model_forecast
    change = comparison.changed_events[0]
    assert change.before.status == change.after.status == "invoice_unpaid"
    assert change.before.amount_cents == change.after.amount_cents == 500
    assert change.before.expected_date == START and change.after.expected_date == START + timedelta(days=1)


def test_supplier_deferral_beyond_window_is_retained_and_not_claimed_cancelled():
    comparison = simulate_scenario(categorized_request(), scenario(move("supplier_future", 3)))
    assert [day.projected_closing_balance_cents for day in comparison.scenario.days] == [1580, 1660]
    assert comparison.baseline_shortage_date == START + timedelta(days=1)
    assert comparison.scenario_shortage_date is None
    assert comparison.maximum_reserve_shortfall_change_cents == -540
    assert comparison.changed_events[0].after.expected_date == START + timedelta(days=3)
    assert not comparison.changed_events[0].included_after
    disposition = comparison.scenario.reconciliation.event_dispositions[1]
    assert disposition.event.status == "scheduled_expense" and disposition.event.amount_cents == 1400
    assert not disposition.included and "outside" in disposition.reason
    assert any("contributes zero cash" in warning for warning in comparison.scenario.warnings)


def test_move_expense_earlier_reports_first_breach_and_negative_cash():
    comparison = simulate_scenario(categorized_request(), scenario(move("supplier_future", 0)))
    assert [day.projected_closing_balance_cents for day in comparison.scenario.days] == [180, 260]
    assert comparison.scenario_shortage_date == START
    assert comparison.maximum_reserve_shortfall_change_cents == 80
    assert comparison.scenario.days_below_reserve == 2
    assert comparison.scenario.shortage_evidence[0].known_event_effects[1].signed_balance_effect_cents == -1400


@pytest.mark.parametrize("amount,closing,shortfall", [(1000, 660, 140), (2000, -340, 1140), (0, 1660, 0), (10**40 + 1, 1659 - 10**40, 10**40 - 859)])
def test_expense_changes_preserve_exact_integer_cents(amount, closing, shortfall):
    operation = ChangeExpenseAmountOperation(operation_id="expense", event_id="supplier_future",
        amount_cents=amount, assumption="Assume a revised supplier amount.")
    comparison = simulate_scenario(categorized_request(), scenario(operation))
    assert comparison.scenario.days[-1].projected_closing_balance_cents == closing
    assert comparison.scenario.maximum_reserve_shortfall_cents == shortfall
    assert type(closing) is int


@pytest.mark.parametrize("direction,amount,closes", [("outflow", 200, [1380, 60]), ("inflow", 400, [1980, 660])])
def test_hypothetical_addition_is_cash_once_and_explicitly_conditional(direction, amount, closes):
    comparison = simulate_scenario(categorized_request(), scenario(added(amount, direction)))
    assert [day.projected_closing_balance_cents for day in comparison.scenario.days] == closes
    assert comparison.hypothetical and comparison.changed_events[0].hypothetical
    assert not comparison.scenario.risk_assessment_complete
    assert not comparison.scenario.reconciliation.fully_reconciled
    assert comparison.changed_events[0].before is None
    assert comparison.changed_events[0].after.projection_assumption == comparison.assumptions[0]


def test_addition_over_aggregate_forecast_reuses_models_without_suppressing_other_activity():
    request = categorized_request().model_copy(update={"known_events": (), "category_coverage": (), "historical_transactions": None})
    baseline = forecast_cash_flow(request)
    comparison = simulate_scenario(request, scenario(added(200)), baseline=baseline)
    assert [day.projected_closing_balance_cents for day in baseline.days] == [1100, 1200]
    assert [day.projected_closing_balance_cents for day in comparison.scenario.days] == [900, 1000]
    assert comparison.scenario.statistical_inflow_applied and comparison.scenario.statistical_outflow_applied
    assert comparison.scenario.model_forecast == baseline.model_forecast
    assert any("overlap is not independently proven" in warning for warning in comparison.scenario.warnings)


def test_hypothetical_future_addition_outside_horizon_is_not_discarded():
    comparison = simulate_scenario(categorized_request(), scenario(added(offset=30)))
    assert comparison.scenario.days[0].projected_closing_balance_cents == 1580
    assert comparison.scenario.days[1].projected_closing_balance_cents == 260
    assert not comparison.changed_events[0].included_after
    assert comparison.changed_events[0].after.expected_date == START + timedelta(days=30)


@pytest.mark.parametrize("event_id,closing", [("supplier_future", 1660), ("invoice_future", -240)])
def test_remove_eligible_future_event_retains_original_evidence(event_id, closing):
    comparison = simulate_scenario(categorized_request(), scenario(RemoveEventOperation(
        operation_id="remove", event_id=event_id, assumption="Assume no cash for this event in the scenario.")))
    assert comparison.scenario.days[-1].projected_closing_balance_cents == closing
    assert comparison.changed_events[0].after is None
    assert comparison.changed_events[0].before.event_id == event_id
    assert not next(item for item in comparison.scenario.reconciliation.event_dispositions if item.event.event_id == event_id).included


def test_multiple_independent_changes_compound_cash_timing_and_preserve_evidence():
    operations = scenario(move("invoice_future", 1), ChangeExpenseAmountOperation(
        operation_id="bill", event_id="supplier_future", amount_cents=1000,
        assumption="Assume the vendor accepts 1000 cents."), added(50))
    comparison = simulate_scenario(categorized_request(), operations)
    assert [day.projected_closing_balance_cents for day in comparison.scenario.days] == [1030, 610]
    assert [change.closing_balance_difference_cents for change in comparison.daily_differences] == [-550, 350]
    assert len(comparison.changed_events) == 3


@pytest.mark.parametrize("direction,amount,closing", [("inflow", 300, 460), ("outflow", 300, -20)])
def test_explicit_projection_replacement_preserves_underlying_model_and_changes_balances(direction, amount, closing):
    request = categorized_request()
    baseline = forecast_cash_flow(request)
    operation = ChangeProjectionOperation(operation_id="projection", direction=direction,
        date=START, amount_cents=amount, assumption="Assume a changed daily trading level.")
    comparison = simulate_scenario(request, scenario(operation), baseline=baseline)
    assert comparison.scenario.days[-1].projected_closing_balance_cents == closing
    assert comparison.scenario.model_forecast == baseline.model_forecast
    assert comparison.changed_projections[0].after_cents == amount
    assert comparison.changed_projections[0].before_cents == (100 if direction == "inflow" else 20)


def test_uncertainty_preserves_complete_path_errors_and_shifts_only_cash_difference():
    request = categorized_request()
    baseline = forecast_cash_flow(request)
    comparison = simulate_scenario(request, scenario(move("invoice_future", 1)), baseline=baseline)
    for index, delta in enumerate((-500, 0)):
        before = baseline.uncertainty.horizons[index]
        after = comparison.scenario.uncertainty.horizons[index]
        assert after.residual_inflow == before.residual_inflow
        assert after.residual_outflow == before.residual_outflow
        assert after.projected_closing_balance.validation_samples == before.projected_closing_balance.validation_samples
        assert after.projected_closing_balance.lower_cents == before.projected_closing_balance.lower_cents + delta
        assert after.projected_closing_balance.upper_cents == before.projected_closing_balance.upper_cents + delta
    assert comparison.scenario.uncertainty.calibrated_coverage is None


def test_missing_uncertainty_is_never_invented_by_a_scenario():
    request = categorized_request(count=1)
    comparison = simulate_scenario(request, scenario(move("supplier_future", 5)))
    assert comparison.scenario.uncertainty.status == "unavailable"
    assert all(item.projected_closing_balance.lower_cents is None for item in comparison.scenario.uncertainty.horizons)


def test_request_baseline_immutability_json_roundtrip_and_no_retraining(monkeypatch):
    request = categorized_request()
    baseline = forecast_cash_flow(request)
    request_json, baseline_json = request.model_dump_json(), baseline.model_dump_json()
    monkeypatch.setattr("backend.app.forecast.scenarios.forecast_cash_flow",
        lambda _: pytest.fail("supplied baseline must prevent retraining"))
    changes = scenario(move("supplier_future", 5))
    first = simulate_scenario(request, changes, baseline=baseline)
    second = simulate_scenario(request, changes, baseline=baseline)
    assert first == second
    assert ScenarioComparison.model_validate_json(first.model_dump_json()) == first
    assert request.model_dump_json() == request_json and baseline.model_dump_json() == baseline_json


@pytest.mark.parametrize("change", ["operation_id", "event_id", "projection_key"])
def test_duplicate_scenario_changes_are_rejected(change):
    if change == "operation_id":
        operations = (move("supplier_future", 4), move("invoice_future", 1))
    elif change == "event_id":
        operations = (move("supplier_future", 4), ChangeExpenseAmountOperation(operation_id="amount",
            event_id="supplier_future", amount_cents=100, assumption="Assume a lower amount."))
    else:
        first = ChangeProjectionOperation(operation_id="a", direction="inflow", date=START,
            amount_cents=100, assumption="Assume sales.")
        operations = (first, first.model_copy(update={"operation_id": "b"}))
    with pytest.raises(ValidationError, match="duplicate|only once"):
        scenario(*operations)


@pytest.mark.parametrize("status", ["verified_completed", "cancelled", "failed"])
def test_authoritative_or_excluded_statuses_cannot_be_changed(status):
    request = categorized_request()
    event = request.known_events[0].model_copy(update={"status": status,
        "verification_evidence_id": "provider-evidence" if status == "verified_completed" else None})
    request = request.model_copy(update={"known_events": (event, request.known_events[1])})
    with pytest.raises(ValueError, match="not an eligible"):
        simulate_scenario(request, scenario(move("invoice_future", 1)))


@pytest.mark.parametrize("field,value", [("expected_date", None), ("projection_assumption", None), ("historical_transaction_id", "invoice_paid_0")])
def test_undated_unassumed_or_historical_receipts_cannot_be_changed(field, value):
    request = categorized_request()
    event = request.known_events[0].model_copy(update={field: value})
    request = request.model_copy(update={"known_events": (event, request.known_events[1])})
    with pytest.raises(ValueError, match="not an eligible"):
        simulate_scenario(request, scenario(move("invoice_future", 1)))


def test_baseline_from_different_request_or_tampered_cash_is_rejected():
    request = categorized_request()
    baseline = forecast_cash_flow(request)
    changed = request.model_copy(update={"safety_reserve_cents": 700})
    with pytest.raises(ValueError, match="unchanged request"):
        simulate_scenario(changed, scenario(move("invoice_future", 1)), baseline=baseline)
    incorrect = baseline.days[0].model_copy(update={"projected_closing_balance_cents": 999})
    with pytest.raises(ValueError, match="inconsistent financial"):
        simulate_scenario(request, scenario(move("invoice_future", 1)), baseline=baseline.model_copy(update={"days": (incorrect, baseline.days[1])}))


def test_arithmetically_consistent_baseline_cannot_invent_a_known_receipt():
    request = categorized_request()
    baseline = forecast_cash_flow(request)
    invented = baseline.days[0].model_copy(update={"known_expected_inflow_cents": 501,
        "known_net_cash_adjustment_cents": 501, "projected_receipts_cents": 601,
        "projected_closing_balance_cents": 1581})
    carried = baseline.days[1].model_copy(update={"opening_balance_cents": 1581,
        "projected_closing_balance_cents": 261, "reserve_shortfall_cents": 539})
    with pytest.raises(ValueError, match="cash components"):
        simulate_scenario(request, scenario(move("invoice_future", 1)),
            baseline=baseline.model_copy(update={"days": (invented, carried)}))


@pytest.mark.parametrize("operation,error", [
    (move("missing", 1), "unknown"), (move("invoice_future", -1), "before"),
    (ChangeExpenseAmountOperation(operation_id="amount", event_id="invoice_future", amount_cents=50, assumption="Assume a revised amount."), "outflow"),
    (ChangeProjectionOperation(operation_id="project", direction="inflow", date=START + timedelta(days=2), amount_cents=50, assumption="Assume sales."), "inside"),
])
def test_invalid_operation_targets_are_rejected(operation, error):
    with pytest.raises(ValueError, match=error):
        simulate_scenario(categorized_request(), scenario(operation))


def test_projection_change_requires_an_applied_statistical_forecast():
    request = categorized_request().model_copy(update={"historical_transactions": None})
    with pytest.raises(ValueError, match="not applied"):
        simulate_scenario(request, scenario(ChangeProjectionOperation(operation_id="project", direction="inflow",
            date=START, amount_cents=50, assumption="Assume sales.")))


@pytest.mark.parametrize("changes,error", [
    ({"currency": "EUR"}, "currency"), ({"event_id": "invoice_future"}, "distinct"),
    ({"source_id": "bill_future"}, "distinct"), ({"source_id": "sale_0"}, "historical"),
    ({"historical_transaction_id": "sale_0"}, "historical"), ({"expected_date": None}, "explicit future"),
    ({"expected_date": START - timedelta(days=1)}, "explicit future"), ({"status": "failed"}, "completion"),
])
def test_hypothetical_additions_require_separate_valid_future_cash(changes, error):
    with pytest.raises(ValueError, match=error):
        simulate_scenario(categorized_request(), scenario(added(**changes)))


@pytest.mark.parametrize("value", [False, 1, "true"])
def test_hypothetical_flag_requires_literal_boolean_true(value):
    data = added().model_dump()
    data["hypothetical"] = value
    with pytest.raises(ValidationError, match="explicit boolean"):
        AddEventOperation.model_validate(data)


@pytest.mark.parametrize("value", [-1, 1.5, True])
def test_scenario_money_must_be_nonnegative_integer_cents(value):
    with pytest.raises(ValidationError):
        ChangeExpenseAmountOperation(operation_id="amount", event_id="supplier_future",
            amount_cents=value, assumption="Assume a revised supplier amount.")
