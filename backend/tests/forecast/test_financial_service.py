from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from backend.app.forecast import CashForecastRequest, CashForecastResult, DailyHistory, MLConfig, forecast_baselines, forecast_cash_flow
from backend.tests.forecast.test_reconciliation import START, categorized_request


def test_unified_balances_shortage_evidence_and_statuses():
    request = categorized_request()
    before = request.model_dump_json()
    result = forecast_cash_flow(request)
    assert result.days[0].opening_balance_cents == 1000
    assert [day.predicted_residual_inflow_cents for day in result.days] == [100, 100]
    assert [day.predicted_residual_outflow_cents for day in result.days] == [20, 20]
    assert [day.known_expected_inflow_cents for day in result.days] == [500, 0]
    assert [day.known_expected_outflow_cents for day in result.days] == [0, 1400]
    assert [day.projected_closing_balance_cents for day in result.days] == [1580, 260]
    assert result.days[1].opening_balance_cents == 1580
    assert result.first_reserve_breach_date == START + timedelta(days=1)
    assert result.minimum_projected_cash_balance_cents == 260
    assert result.maximum_reserve_shortfall_cents == 540 and result.days_below_reserve == 1
    assert result.reconciliation.fully_reconciled and not result.risk_assessment_complete
    evidence = result.shortage_evidence[0]
    assert evidence.opening_balance_evidence_id == "bank_snapshot"
    effects = {effect.event_id: effect for effect in evidence.known_event_effects}
    assert effects["supplier_future"].source_id == "bill_future"
    assert effects["supplier_future"].signed_balance_effect_cents == -1400
    assert effects["supplier_future"].closing_balance_without_event_cents == 1660
    assert effects["supplier_future"].reserve_shortfall_difference_cents == 540
    assert effects["invoice_future"].status == "invoice_unpaid"
    assert effects["invoice_future"].reserve_shortfall_difference_cents == -500
    assert CashForecastResult.model_validate_json(result.model_dump_json()) == result
    assert forecast_cash_flow(request) == result
    assert request.model_dump_json() == before


def test_missing_source_known_only_fallback_is_not_presented_as_full_cash_risk():
    request = categorized_request().model_copy(update={"historical_transactions": None})
    result = forecast_cash_flow(request)
    assert [day.projected_closing_balance_cents for day in result.days] == [1500, 100]
    assert all(day.predicted_residual_inflow_cents == day.predicted_residual_outflow_cents == 0 for day in result.days)
    assert result.selected_inflow_model is result.selected_outflow_model is None
    assert not result.statistical_inflow_applied and not result.risk_assessment_complete
    assert result.uncertainty.status == "unavailable"
    assert any("not a lower or upper cash bound" in warning for warning in result.warnings)


def test_verified_completed_receivable_never_added_to_future_cash():
    request = categorized_request()
    event = request.known_events[0].model_copy(update={"status": "verified_completed", "verification_evidence_id": "verified_source"})
    request = request.model_copy(update={"known_events": (event, request.known_events[1])})
    result = forecast_cash_flow(request)
    assert all(day.known_expected_inflow_cents == 0 for day in result.days)
    assert result.days[0].projected_closing_balance_cents == 1080


def test_multiple_events_on_same_day_and_zero_amount_event():
    request = categorized_request()
    a, b = request.known_events
    b = b.model_copy(update={"expected_date": START})
    zero = b.model_copy(update={"event_id": "zero", "source_id": "zero_bill", "amount_cents": 0})
    request = request.model_copy(update={"known_events": (a, b, zero)})
    result = forecast_cash_flow(request)
    assert result.days[0].known_event_ids == ("invoice_future", "supplier_future", "zero")
    assert result.days[0].projected_closing_balance_cents == 180


def test_exact_reserve_is_safe():
    request = categorized_request().model_copy(update={"safety_reserve_cents": 260})
    result = forecast_cash_flow(request)
    assert result.first_reserve_breach_date is None and result.days_below_reserve == 0
    assert result.maximum_reserve_shortfall_cents == 0
    assert result.shortage_evidence == ()


def test_negative_balances_and_large_integer_cents_are_exact():
    request = categorized_request()
    amount = 10**40 + 1
    bill = request.known_events[1].model_copy(update={"amount_cents": amount})
    request = request.model_copy(update={"known_events": (request.known_events[0], bill)})
    result = forecast_cash_flow(request)
    assert result.days[1].projected_closing_balance_cents == 1660 - amount
    assert result.maximum_reserve_shortfall_cents == amount - 860
    assert type(result.days[1].projected_closing_balance_cents) is int


def test_no_history_and_no_activity_is_labeled_known_only_not_invented_ml():
    request = categorized_request().model_copy(update={"history": DailyHistory(currency="USD", days=()),
        "historical_transactions": None, "known_events": (), "category_coverage": ()})
    result = forecast_cash_flow(request)
    assert all(day.projected_closing_balance_cents == 1000 for day in result.days)
    assert result.reconciliation.status == "no_history"
    assert result.model_forecast.status == "insufficient_data"
    assert not result.risk_assessment_complete and result.uncertainty.status == "unavailable"


def test_no_known_schedule_reuses_aggregate_baselines_without_adjustments():
    request = categorized_request().model_copy(update={"known_events": (), "category_coverage": (), "historical_transactions": None})
    result = forecast_cash_flow(request)
    baseline = forecast_baselines(request.history, as_of=START - timedelta(days=1))
    assert result.reconciliation.status == "aggregate_only" and result.risk_assessment_complete
    assert [day.predicted_residual_inflow_cents for day in result.days] == [day.predicted_inflow_cents for day in baseline.days]
    assert [day.predicted_residual_outflow_cents for day in result.days] == [day.predicted_outflow_cents for day in baseline.days]
    assert all(day.known_expected_inflow_cents == day.known_expected_outflow_cents == 0 for day in result.days)
    assert [day.projected_closing_balance_cents for day in result.days] == [1100, 1200]


def test_known_events_work_without_historical_observations():
    request = categorized_request().model_copy(update={"history": DailyHistory(currency="USD", days=()),
        "historical_transactions": None})
    result = forecast_cash_flow(request)
    assert [day.projected_closing_balance_cents for day in result.days] == [1500, 100]
    assert result.reconciliation.status == "no_history"


@pytest.mark.parametrize("change", ["opening_currency", "event_currency", "balance_date", "future_history", "future_source"])
def test_incompatible_financial_inputs_are_rejected(change):
    request = categorized_request()
    if change == "opening_currency":
        request = request.model_copy(update={"opening_balance": request.opening_balance.model_copy(update={"currency": "EUR"})})
    elif change == "event_currency":
        request = request.model_copy(update={"known_events": (request.known_events[0].model_copy(update={"currency": "EUR"}),)})
    elif change == "balance_date":
        request = request.model_copy(update={"opening_balance": request.opening_balance.model_copy(update={"balance_date": START - timedelta(days=1)})})
    elif change == "future_history":
        request = request.model_copy(update={"forecast_start_date": START - timedelta(days=1),
            "opening_balance": request.opening_balance.model_copy(update={"balance_date": START - timedelta(days=1)})})
    else:
        source = request.historical_transactions
        future = source.transactions[0].model_copy(update={"date": START})
        request = request.model_copy(update={"historical_transactions": source.model_copy(update={"transactions": (future,) + source.transactions[1:]})})
    with pytest.raises(ValueError):
        forecast_cash_flow(request)


@pytest.mark.parametrize("horizon", [1, 2, 30])
def test_horizon_length_and_date_boundaries(horizon):
    request = categorized_request().model_copy(update={"forecast_horizon_days": horizon})
    result = forecast_cash_flow(request)
    assert len(result.days) == horizon
    assert result.days[-1].date == START + timedelta(days=horizon - 1)
    if horizon == 1:
        assert all(day.known_expected_outflow_cents == 0 for day in result.days)


@pytest.mark.parametrize("change", [{"forecast_horizon_days": 0}, {"forecast_horizon_days": 31},
    {"safety_reserve_cents": 1.5}, {"business_timezone": "unknown/zone"},
    {"forecast_start_date": "2026-10-13T00:00:00Z"}])
def test_request_validation(change):
    data = categorized_request().model_dump()
    data.update(change)
    with pytest.raises(ValidationError):
        CashForecastRequest.model_validate(data)


def test_phase_three_ml_is_reused_on_residual_history():
    request = categorized_request(count=84, trend=True).model_copy(update={"ml_config": MLConfig()})
    result = forecast_cash_flow(request)
    assert result.selected_inflow_model == "ridge"
    assert result.statistical_inflow_applied
    assert result.days[0].predicted_residual_inflow_cents > 1700
    assert result.days[0].known_expected_inflow_cents == 500
    assert result.uncertainty.status == "unavailable"  # Default minimum 8 exceeds six outer ML origins.
