from datetime import datetime, timedelta, timezone
from importlib import import_module

import pytest
from pydantic import ValidationError

from backend.app.forecast import (
    ActualObservation, CashForecastResult, ForecastIssueRequest, IssuedCashForecast,
    KnownAheadCovariate, LocalForecastMonitor, LocalModelRegistry, MoveEventOperation,
    PreparationRequest, RetrainingRequest, ScenarioRequest, covariate_diagnostics,
    issue_forecast, prepare_history, reconcile_history, retrain_model, simulate_scenario, train_forecast_model,
)
from backend.tests.forecast.test_reconciliation import START, categorized_request


STAMP = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)


def issue_request(financial=None, **updates):
    return ForecastIssueRequest(issuance_id="issue1", business_id="shop", generated_at=STAMP,
        financial=financial or categorized_request(), **updates)


def test_public_operations_are_importable_and_request_schemas_generate():
    module = import_module("backend.app.forecast")
    assert len(set(module.__all__)) == len(module.__all__)
    for name in module.__all__:
        assert getattr(module, name) is not None
    for schema in (ForecastIssueRequest, PreparationRequest, RetrainingRequest, ScenarioRequest,
                   IssuedCashForecast, CashForecastResult):
        assert schema.model_json_schema()["type"] == "object"


def test_preparation_keeps_raw_optional_fields_and_exact_amounts():
    request = PreparationRequest(csv_data="transaction_id,date,amount,direction,currency,bookings\nt1,2026-10-12,123.45,inflow,USD,17\n")
    result = prepare_history(request)
    assert result.history.days[0].inflow_cents == 12345
    assert result.source.transactions[0].source_fields["bookings"] == "17"


def test_issued_forecast_has_business_time_versions_and_reproducible_identity():
    financial = categorized_request()
    residual, _ = reconcile_history(financial)
    v1 = train_forecast_model(residual, business_id="shop", model_version="v1", trained_at=STAMP)
    v2 = train_forecast_model(residual, business_id="shop", model_version="v2", trained_at=STAMP)
    first = issue_forecast(issue_request(), trained_model=v1)
    second = issue_forecast(issue_request(), trained_model=v2)
    assert first.business_id == "shop" and first.generated_at == STAMP
    assert first.inflow_model_version == first.outflow_model_version == "v1"
    assert first.forecast.model_artifact_id == v1.metadata.model_id
    assert first.forecast.model_version == "v1"
    assert first.forecast.forecast_id != second.forecast.forecast_id
    assert first.forecast.request_fingerprint == second.forecast.request_fingerprint
    assert issue_forecast(issue_request(), trained_model=v1) == first
    assert IssuedCashForecast.model_validate_json(first.model_dump_json()) == first
    scenario = ScenarioRequest(scenario_id="defer", operations=(MoveEventOperation(operation_id="move", event_id="supplier_future",
        expected_date=START + timedelta(days=3), assumption="Supplier agrees to defer."),))
    comparison = simulate_scenario(financial, scenario, baseline=first.forecast)
    assert comparison.scenario.first_reserve_breach_date is None
    assert comparison.baseline.model_forecast == comparison.scenario.model_forecast


@pytest.mark.parametrize("change", ["business", "currency", "gross_model", "future_training", "config"])
def test_stored_artifact_cannot_cross_business_target_or_config_boundary(change):
    financial = categorized_request()
    residual, _ = reconcile_history(financial)
    if change == "currency":
        residual = residual.model_copy(update={"currency": "EUR", "days": tuple(day.model_copy(update={"currency": "EUR"}) for day in residual.days)})
    model = train_forecast_model(financial.history if change == "gross_model" else residual,
        business_id="other" if change == "business" else "shop", model_version="v1",
        trained_at=STAMP + timedelta(days=1) if change == "future_training" else STAMP)
    if change == "config":
        financial = financial.model_copy(update={"baseline_config": financial.baseline_config.model_copy(update={"moving_average_window": 3})})
    with pytest.raises(ValueError):
        issue_forecast(issue_request(financial), trained_model=model)


def test_covariate_extension_is_explicitly_unsupported_retained_and_known_before_issue():
    item = KnownAheadCovariate(business_id="shop", name="advance_bookings", date=START,
        value=17, known_at=STAMP - timedelta(days=1), evidence_id="booking_snapshot")
    request = issue_request(covariates=(item,))
    diagnostics = covariate_diagnostics(request)
    assert not diagnostics.model_support_available and diagnostics.records == (item,)
    issued = issue_forecast(request)
    assert any("not consumed" in warning for warning in issued.forecast.warnings)
    assert issued.forecast.days == issue_forecast(issue_request()).forecast.days


@pytest.mark.parametrize("change", ["future", "tenant", "duplicate", "infinite"])
def test_covariate_leakage_or_invalid_availability_rejected(change):
    data = dict(business_id="shop", name="orders", date=START, value=4,
        known_at=STAMP, evidence_id="order_snapshot")
    if change == "future":
        data["known_at"] = STAMP + timedelta(seconds=1)
    elif change == "tenant":
        data["business_id"] = "other"
    elif change == "infinite":
        data["value"] = float("inf")
    with pytest.raises(ValidationError):
        item = KnownAheadCovariate(**data)
        issue_request(covariates=(item, item) if change == "duplicate" else (item,))


def test_complete_synthetic_workflow_including_new_actuals_and_retraining(tmp_path):
    financial = categorized_request()
    residual, _ = reconcile_history(financial)
    model = train_forecast_model(residual, business_id="shop", model_version="v1", trained_at=STAMP)
    registry = LocalModelRegistry(tmp_path / "models")
    registry.save_candidate(model)
    registry.promote("shop", "v1")
    loaded = registry.load("shop", "v1", expected_currency="USD")
    issued = issue_forecast(issue_request(), trained_model=loaded)
    assert [day.projected_closing_balance_cents for day in issued.forecast.days] == [1580, 260]
    scenario = ScenarioRequest(scenario_id="defer", operations=(MoveEventOperation(operation_id="move", event_id="supplier_future",
        expected_date=START + timedelta(days=3), assumption="Hypothetical supplier agreement."),))
    comparison = simulate_scenario(financial, scenario, baseline=issued.forecast)
    assert comparison.scenario.maximum_reserve_shortfall_cents == 0
    monitor = LocalForecastMonitor(tmp_path / "monitor")
    monitor.record_forecast(issued)
    for day in issued.forecast.days:
        monitor.record_actual(ActualObservation(business_id="shop", observation_id=f"actual_{day.date}",
            currency="USD", date=day.date, inflow_cents=day.projected_receipts_cents, outflow_cents=day.projected_payments_cents,
            verified=True, complete=True, verification_evidence_id=f"settlement_{day.date}",
            observed_at=STAMP + timedelta(days=day.horizon)))
    report = monitor.evaluate("shop")
    assert report.eligible_direction_errors == 4 and all(error.error_cents == 0 for error in report.errors)
    assert not report.material_deterioration  # Gross actuals are not a residual validation reference.
    from backend.app.forecast import DailyCash, DailyHistory
    additions = tuple(DailyCash(date=START + timedelta(days=i), currency="USD", inflow_cents=100, outflow_cents=20,
        evidence_ids=(f"new_sale_{i}", f"new_cost_{i}")) for i in range(14))
    updated = DailyHistory(currency="USD", days=residual.days + additions, complete_coverage=True,
        coverage_start=residual.coverage_start, coverage_end=additions[-1].date)
    decision = retrain_model(registry, RetrainingRequest(business_id="shop", decision_id="new14", candidate_version="v2",
        now=STAMP + timedelta(days=14), history=updated, verified=True, verification_evidence_id="verified_residual_export"), monitoring=report)
    assert decision.status == "retained" and decision.active_version == "v1"
    assert "new_verified_observations" in decision.triggers
