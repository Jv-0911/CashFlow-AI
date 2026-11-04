from datetime import datetime, time, timedelta, timezone
import json
import os

import pytest
from pydantic import ValidationError

from backend.app.forecast import forecast_cash_flow
from backend.app.forecast.monitoring import LocalForecastMonitor
from backend.app.forecast.monitoring_schemas import (
    ActualObservation, ForecastActualError, IssuedCashForecast, MonitoringConfig, MonitoringReport,
)
from backend.tests.forecast.test_reconciliation import START, categorized_request


def issued(target=START, *, issuance_id="issued_1", business_id="shop_1", known=False,
           version="v1", horizon=2):
    request = categorized_request()
    offset = target - START
    history = request.history.model_copy(update={
        "days": tuple(day.model_copy(update={"date": day.date + offset}) for day in request.history.days),
        "coverage_start": request.history.coverage_start + offset,
        "coverage_end": request.history.coverage_end + offset,
    })
    events = tuple(event.model_copy(update={"expected_date": event.expected_date + offset})
                   for event in request.known_events) if known else ()
    source = request.historical_transactions
    source = source.model_copy(update={"transactions": tuple(
        item.model_copy(update={"date": item.date + offset}) for item in source.transactions
    )}) if known else None
    request = request.model_copy(update={
        "history": history, "forecast_start_date": target, "forecast_horizon_days": horizon,
        "known_events": events, "category_coverage": request.category_coverage if known else (),
        "historical_transactions": source,
        "opening_balance": request.opening_balance.model_copy(update={"balance_date": target}),
    })
    return IssuedCashForecast(
        issuance_id=issuance_id, business_id=business_id,
        generated_at=datetime.combine(target - timedelta(days=1), time(12), timezone.utc),
        inflow_model_version=version, outflow_model_version=version, forecast=forecast_cash_flow(request),
    )


def actual(target=START, *, observation_id=None, business_id="shop_1", inflow=160,
           outflow=40, **extra):
    return ActualObservation(
        business_id=business_id, observation_id=observation_id or f"actual_{target.isoformat()}",
        currency="USD", date=target, inflow_cents=inflow, outflow_cents=outflow,
        verified=True, complete=True, verification_evidence_id=f"ledger_{target.isoformat()}",
        observed_at=datetime.combine(target + timedelta(days=1), time(12), timezone.utc), **extra,
    )


def test_matches_verified_actuals_to_original_issuance_and_horizon(tmp_path):
    monitor = LocalForecastMonitor(tmp_path / "monitor")
    forecast = issued()
    monitor.record_forecast(forecast)
    monitor.record_actual(actual())
    monitor.record_actual(actual(START + timedelta(days=1), inflow=130, outflow=60))
    report = monitor.evaluate("shop_1")
    assert report.forecast_actual_pairs == 2 and report.eligible_direction_errors == 4
    assert report.unique_actual_dates == 2 and report.recorded_actual_days == 2
    assert {item.horizon for item in report.errors} == {1, 2}
    assert all(item.generated_at == forecast.generated_at for item in report.errors)
    assert all(item.actual_observed_at == actual(item.target_date).observed_at for item in report.errors)
    assert all(item.issuance_date == START - timedelta(days=1) for item in report.errors)
    assert all(item.model_as_of == START - timedelta(days=1) for item in report.errors)
    values = {(item.direction, item.horizon): item for item in report.errors}
    assert values["inflow", 1].error_cents == -10
    assert values["outflow", 1].error_cents == 10
    assert values["inflow", 2].error_cents == 20
    assert values["outflow", 2].error_cents == -10
    assert values["inflow", 1].model_version == "v1"
    assert values["inflow", 1].validation_reference_mae_cents == 0
    assert MonitoringReport.model_validate_json(report.model_dump_json()) == report


def test_missing_actuals_are_not_scored_as_zero(tmp_path):
    monitor = LocalForecastMonitor(tmp_path / "monitor")
    monitor.record_forecast(issued())
    report = monitor.evaluate("shop_1")
    assert not report.errors and not report.groups
    assert len(report.missing_actuals) == 2
    monitor.record_actual(actual())
    report = monitor.evaluate("shop_1")
    assert report.forecast_actual_pairs == 1 and len(report.missing_actuals) == 1
    assert report.missing_actuals[0].horizon == 2


@pytest.mark.parametrize("field", ["verified", "complete"])
@pytest.mark.parametrize("value", [False, 1, "true", None])
def test_unverified_or_incomplete_actuals_are_rejected(field, value):
    data = actual().model_dump()
    data[field] = value
    with pytest.raises(ValidationError):
        ActualObservation.model_validate(data)


@pytest.mark.parametrize("field", ["verified", "complete", "verification_evidence_id"])
def test_actual_verification_cannot_be_implicit(field):
    data = actual().model_dump()
    data.pop(field)
    with pytest.raises(ValidationError):
        ActualObservation.model_validate(data)


def test_recording_revalidates_model_copy_actuals(tmp_path):
    monitor = LocalForecastMonitor(tmp_path / "monitor")
    with pytest.raises(ValidationError):
        monitor.record_actual(actual().model_copy(update={"verified": False}))
    assert monitor.evaluate("shop_1").recorded_actual_days == 0


def test_rejects_duplicate_ids_conflicts_and_duplicate_business_dates(tmp_path):
    monitor = LocalForecastMonitor(tmp_path / "monitor")
    forecast = issued()
    observation = actual()
    assert monitor.record_forecast(forecast) == monitor.record_forecast(forecast)
    assert monitor.record_actual(observation) == monitor.record_actual(observation)
    with pytest.raises(ValueError, match="issuance_id"):
        monitor.record_forecast(forecast.model_copy(update={"inflow_model_version": "v2"}))
    with pytest.raises(ValueError, match="observation_id"):
        monitor.record_actual(observation.model_copy(update={"inflow_cents": 161}))
    with pytest.raises(ValueError, match="business date"):
        monitor.record_actual(observation.model_copy(update={"observation_id": "other_actual"}))
    assert monitor.evaluate("shop_1").recorded_forecasts == 1
    assert monitor.evaluate("shop_1").recorded_actual_days == 1


def test_persisted_reload_matches_and_businesses_are_isolated(tmp_path):
    root = tmp_path / "monitor"
    monitor = LocalForecastMonitor(root)
    monitor.record_forecast(issued())
    monitor.record_actual(actual())
    monitor.record_forecast(issued(business_id="shop_2"))
    monitor.record_actual(actual(business_id="shop_2", inflow=1, outflow=2))
    first = monitor.evaluate("shop_1")
    reloaded = LocalForecastMonitor(root)
    assert reloaded.evaluate("shop_1") == first
    second = reloaded.evaluate("shop_2")
    assert first.errors[0].actual_cents != second.errors[0].actual_cents
    assert all(item.actual_cents in (1, 2) for item in second.errors)
    assert reloaded.evaluate("no_business").currency is None
    assert not reloaded.evaluate("no_business").errors


def test_mixed_currency_is_rejected_before_storage(tmp_path):
    monitor = LocalForecastMonitor(tmp_path / "monitor")
    monitor.record_forecast(issued())
    with pytest.raises(ValueError, match="currencies"):
        monitor.record_actual(actual().model_copy(update={"currency": "EUR"}))
    assert monitor.evaluate("shop_1").recorded_actual_days == 0


@pytest.mark.parametrize("business_id", ["../shop", "/tmp/shop", "a/b", "a\\b", "", ".", "..", "a.b", "a" * 65])
def test_filesystem_unsafe_business_ids_are_rejected(tmp_path, business_id):
    with pytest.raises(ValueError):
        LocalForecastMonitor(tmp_path / "monitor").evaluate(business_id)


def test_symlink_root_tenant_and_snapshot_are_rejected(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        LocalForecastMonitor(link)
    monitor = LocalForecastMonitor(tmp_path / "monitor")
    (monitor.root / "shop_1").symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        monitor.record_forecast(issued())
    monitor.record_forecast(issued(business_id="shop_2"))
    snapshot = monitor.root / "shop_2" / "monitor.json"
    snapshot.unlink()
    external = tmp_path / "external.json"
    external.write_text("{}", encoding="utf-8")
    snapshot.symlink_to(external)
    with pytest.raises(ValueError, match="symlink"):
        monitor.evaluate("shop_2")
    assert external.read_text(encoding="utf-8") == "{}"


@pytest.mark.parametrize("timestamp", [datetime(2026, 10, 12, 12), "2026-10-12T12:00:00-05:00", "invalid"])
def test_timestamp_requires_utc_awareness(timestamp):
    data = issued().model_dump()
    data["generated_at"] = timestamp
    with pytest.raises(ValidationError):
        IssuedCashForecast.model_validate(data)
    data = actual().model_dump()
    data["observed_at"] = timestamp
    with pytest.raises(ValidationError):
        ActualObservation.model_validate(data)


def test_actual_must_be_observed_after_complete_business_day(tmp_path):
    monitor = LocalForecastMonitor(tmp_path / "monitor")
    monitor.record_forecast(issued())
    # UTC next calendar day at 01:00 is still the target evening in Chicago.
    early = actual().model_copy(update={"observed_at": datetime.combine(START + timedelta(days=1), time(1), timezone.utc)})
    with pytest.raises(ValueError, match="day has ended"):
        monitor.record_actual(early)


def test_actual_known_before_issuance_is_never_accuracy(tmp_path):
    monitor = LocalForecastMonitor(tmp_path / "monitor")
    forecast = issued()
    future_actual = actual().model_copy(update={"date": START - timedelta(days=3), "observation_id": "older"})
    monitor.record_actual(future_actual)
    monitor.record_forecast(forecast)
    assert monitor.evaluate("shop_1").forecast_actual_pairs == 0


@pytest.mark.parametrize("offset", [-1, 0])
def test_error_contract_rejects_actual_observed_before_or_at_issuance(tmp_path, offset):
    monitor = LocalForecastMonitor(tmp_path / "monitor")
    forecast = issued()
    monitor.record_forecast(forecast)
    monitor.record_actual(actual())
    error = monitor.evaluate("shop_1").errors[0].model_dump()
    error["actual_observed_at"] = forecast.generated_at + timedelta(seconds=offset)
    with pytest.raises(ValidationError, match="observed after"):
        ForecastActualError.model_validate(error)


def test_report_preserves_future_observation_time_for_retraining_to_check(tmp_path):
    monitor = LocalForecastMonitor(tmp_path / "monitor")
    monitor.record_forecast(issued())
    recorded = actual().model_copy(update={"observed_at": datetime.combine(START + timedelta(days=3), time(12), timezone.utc)})
    monitor.record_actual(recorded)
    report = monitor.evaluate("shop_1")
    assert report.errors[0].actual_observed_at == recorded.observed_at
    assert report.errors[0].target_date == START
    assert report.errors[0].actual_observed_at.date() > report.errors[0].target_date


@pytest.mark.parametrize("change", ["late_issue", "future_training", "bad_lead", "bad_receipts", "bad_closing", "bad_model"])
def test_issued_date_and_financial_invariants_are_validated(tmp_path, change):
    forecast = issued()
    result = forecast.forecast
    if change == "late_issue":
        forecast = forecast.model_copy(update={"generated_at": datetime.combine(START + timedelta(days=1), time(12), timezone.utc)})
    elif change == "future_training":
        forecast = forecast.model_copy(update={"generated_at": forecast.generated_at - timedelta(days=1)})
    else:
        day = result.days[0]
        fields = {"bad_lead": {"horizon": 2}, "bad_receipts": {"projected_receipts_cents": 151},
                  "bad_closing": {"projected_closing_balance_cents": 999},
                  "bad_model": {"predicted_residual_inflow_cents": 149, "projected_receipts_cents": 149,
                                "projected_closing_balance_cents": 1099}}[change]
        result = result.model_copy(update={"days": (day.model_copy(update=fields),) + result.days[1:]})
        forecast = forecast.model_copy(update={"forecast": result})
    with pytest.raises(ValueError):
        LocalForecastMonitor(tmp_path / "monitor").record_forecast(forecast)


def test_known_event_forecast_has_real_gross_errors_without_false_residual_reference(tmp_path):
    monitor = LocalForecastMonitor(tmp_path / "monitor")
    monitor.record_forecast(issued(known=True))
    monitor.record_actual(actual(inflow=600, outflow=20))
    report = monitor.evaluate("shop_1")
    assert report.eligible_direction_errors == 2
    inflow = next(item for item in report.errors if item.direction == "inflow")
    assert inflow.predicted_cents == 600 and inflow.error_cents == 0
    assert inflow.validation_reference_mae_cents is None
    assert "Residual-category" in inflow.reference_unavailable_reason


def test_unreconciled_known_only_forecasts_cannot_claim_accuracy(tmp_path):
    monitor = LocalForecastMonitor(tmp_path / "monitor")
    request = categorized_request().model_copy(update={"historical_transactions": None})
    forecast = issued().model_copy(update={"forecast": forecast_cash_flow(request),
        "inflow_model_version": None, "outflow_model_version": None})
    monitor.record_forecast(forecast)
    monitor.record_actual(actual())
    report = monitor.evaluate("shop_1")
    assert report.forecast_actual_pairs == 1 and report.eligible_direction_errors == 0
    assert all(item.error_cents is None and not item.accuracy_eligible for item in report.errors)
    assert not report.groups


def test_mae_bias_wape_and_unique_date_metrics(tmp_path):
    monitor = LocalForecastMonitor(tmp_path / "monitor")
    for index, inflow in enumerate((130, 180, 150)):
        target = START + timedelta(days=index)
        monitor.record_forecast(issued(target, issuance_id=f"issue_{index}"))
        monitor.record_actual(actual(target, inflow=inflow, outflow=0))
    group = next(item for item in monitor.evaluate("shop_1").groups if item.direction == "inflow" and item.horizon == 1)
    assert group.metrics.evaluated_observations == 3
    assert group.metrics.mae_cents == pytest.approx(50 / 3)
    assert group.metrics.bias_cents == pytest.approx(-10 / 3)
    assert group.metrics.wape == pytest.approx(50 / 460)
    outflow = next(item for item in monitor.evaluate("shop_1").groups if item.direction == "outflow" and item.horizon == 1)
    assert outflow.metrics.wape is None
    assert outflow.metrics.wape_unavailable_reason == "zero_or_near_zero_actuals"


def test_duplicate_issuances_cannot_supply_sustained_deterioration(tmp_path):
    monitor = LocalForecastMonitor(tmp_path / "monitor")
    for index in range(12):
        monitor.record_forecast(issued(issuance_id=f"issue_{index}"))
    monitor.record_actual(actual(inflow=1000))
    report = monitor.evaluate("shop_1")
    group = next(item for item in report.groups if item.direction == "inflow" and item.horizon == 1)
    assert group.forecast_actual_pairs == 12 and group.unique_actual_dates == 1
    assert group.duplicate_target_pairs == 11
    assert group.independent_date_metrics.evaluated_observations == 1
    assert not report.material_deterioration and not group.recent_windows


def test_sustained_deterioration_needs_two_distinct_date_windows(tmp_path):
    monitor = LocalForecastMonitor(tmp_path / "monitor")
    for index in range(10):
        target = START + timedelta(days=index)
        monitor.record_forecast(issued(target, issuance_id=f"issue_{index}"))
        monitor.record_actual(actual(target, inflow=1000))
        if index < 9:
            assert not monitor.evaluate("shop_1").material_deterioration
    report = monitor.evaluate("shop_1")
    group = next(item for item in report.groups if item.direction == "inflow" and item.horizon == 1)
    assert group.material_deterioration and report.material_deterioration
    assert len(group.recent_windows) == 2
    assert all(window.observations == 5 and window.metrics.mae_cents == 850 for window in group.recent_windows)
    assert group.recent_windows[0].end_date < group.recent_windows[1].start_date
    assert all(window.validation_reference_mae_cents == 0 for window in group.recent_windows)


def test_single_deteriorated_window_is_not_sustained(tmp_path):
    monitor = LocalForecastMonitor(tmp_path / "monitor")
    for index in range(10):
        target = START + timedelta(days=index)
        monitor.record_forecast(issued(target, issuance_id=f"issue_{index}"))
        monitor.record_actual(actual(target, inflow=150 if index < 5 else 1000))
    group = next(item for item in monitor.evaluate("shop_1").groups if item.direction == "inflow" and item.horizon == 1)
    assert [window.material_deterioration for window in group.recent_windows] == [False, True]
    assert not group.material_deterioration


def test_deterioration_keeps_versions_separate_and_threshold_configurable(tmp_path):
    monitor = LocalForecastMonitor(tmp_path / "monitor")
    for index in range(6):
        target = START + timedelta(days=index)
        monitor.record_forecast(issued(target, issuance_id=f"issue_{index}", version="v1" if index < 3 else "v2"))
        monitor.record_actual(actual(target, inflow=1000))
    default = monitor.evaluate("shop_1")
    assert not default.material_deterioration
    assert {group.model_version for group in default.groups} == {"v1", "v2"}
    # Three dates per version are still insufficient for two minimum-size windows.
    report = monitor.evaluate("shop_1", config=MonitoringConfig(minimum_window_observations=3))
    assert not report.material_deterioration


def test_no_reference_comparison_for_category_residual_windows(tmp_path):
    monitor = LocalForecastMonitor(tmp_path / "monitor")
    for index in range(6):
        target = START + timedelta(days=index)
        monitor.record_forecast(issued(target, issuance_id=f"issue_{index}", known=True))
        monitor.record_actual(actual(target, inflow=10000))
    report = monitor.evaluate("shop_1", config=MonitoringConfig(minimum_window_observations=3))
    group = next(item for item in report.groups if item.direction == "inflow" and item.horizon == 1)
    assert len(group.recent_windows) == 2 and not group.material_deterioration
    assert all(not window.comparison_available for window in group.recent_windows)
    assert all(window.validation_reference_mae_cents is None for window in group.recent_windows)


def test_tampered_snapshot_business_and_version_fail_closed(tmp_path):
    monitor = LocalForecastMonitor(tmp_path / "monitor")
    monitor.record_forecast(issued())
    path = monitor.root / "shop_1" / "monitor.json"
    original = json.loads(path.read_text(encoding="utf-8"))
    for changes in ({"business_id": "shop_2"}, {"schema_version": 2}):
        path.write_text(json.dumps({**original, **changes}), encoding="utf-8")
        with pytest.raises(ValueError):
            monitor.evaluate("shop_1")


def test_huge_verified_actuals_keep_exact_errors_without_invented_finite_metrics(tmp_path):
    monitor = LocalForecastMonitor(tmp_path / "monitor")
    amount = 10**400 + 1
    for index in range(6):
        target = START + timedelta(days=index)
        monitor.record_forecast(issued(target, issuance_id=f"issue_{index}"))
        monitor.record_actual(actual(target, inflow=amount, outflow=50))
    report = monitor.evaluate("shop_1", config=MonitoringConfig(minimum_window_observations=3))
    group = next(item for item in report.groups if item.direction == "inflow" and item.horizon == 1)
    assert group.metrics.evaluated_observations == 6
    assert group.metrics.mae_cents is None and group.metrics.bias_cents is None
    assert group.metrics.wape_unavailable_reason == "numeric_range_exceeded"
    assert len(group.recent_windows) == 2
    assert all(not window.comparison_available and not window.material_deterioration for window in group.recent_windows)
    assert not group.material_deterioration and not report.material_deterioration
    assert all(item.error_cents == 150 - amount for item in report.errors if item.direction == "inflow")


@pytest.mark.parametrize("filename", [".monitor.lock", "monitor.json"])
def test_fifo_lock_and_snapshot_are_rejected_without_blocking(tmp_path, filename):
    monitor = LocalForecastMonitor(tmp_path / "monitor")
    tenant = monitor.root / "shop_1"
    tenant.mkdir()
    os.mkfifo(tenant / filename)
    with pytest.raises(ValueError, match="regular file"):
        monitor.evaluate("shop_1")


@pytest.mark.parametrize("filename", [".monitor.lock", "monitor.json"])
def test_directory_lock_and_snapshot_are_rejected(tmp_path, filename):
    monitor = LocalForecastMonitor(tmp_path / "monitor")
    tenant = monitor.root / "shop_1"
    tenant.mkdir()
    (tenant / filename).mkdir()
    with pytest.raises(ValueError, match="regular file"):
        monitor.evaluate("shop_1")


def test_oversized_snapshot_is_rejected_before_json_parsing(tmp_path):
    monitor = LocalForecastMonitor(tmp_path / "monitor")
    tenant = monitor.root / "shop_1"
    tenant.mkdir()
    with (tenant / "monitor.json").open("wb") as stream:
        stream.truncate(16 * 1024 * 1024 + 1)
    with pytest.raises(ValueError, match="16 MiB"):
        monitor.evaluate("shop_1")


def test_snapshot_size_limit_failure_preserves_previous_records(tmp_path, monkeypatch):
    from backend.app.forecast import monitoring as monitoring_module
    monitor = LocalForecastMonitor(tmp_path / "monitor")
    monitor.record_forecast(issued())
    path = monitor.root / "shop_1" / "monitor.json"
    original = path.read_bytes()
    monkeypatch.setattr(monitoring_module, "_MAX_SNAPSHOT_BYTES", len(original) + 1)
    with pytest.raises(ValueError, match="16 MiB"):
        monitor.record_actual(actual())
    assert path.read_bytes() == original


@pytest.mark.parametrize("direction", ["inflow", "outflow"])
@pytest.mark.parametrize("version", ["v2", None])
def test_stored_forecast_version_cannot_be_mislabelled_at_issuance(direction, version):
    original = issued()
    financial = original.forecast.model_copy(update={"model_version": "v1", "model_artifact_id": "stored_model_1"})
    data = original.model_dump()
    data["forecast"] = financial.model_dump()
    data[f"{direction}_model_version"] = version
    with pytest.raises(ValidationError, match="stored version"):
        IssuedCashForecast.model_validate(data)


def test_stored_forecast_direction_versions_match_and_round_trip():
    original = issued()
    financial = original.forecast.model_copy(update={"model_version": "v1", "model_artifact_id": "stored_model_1"})
    valid = IssuedCashForecast.model_validate({**original.model_dump(), "forecast": financial.model_dump()})
    assert valid.inflow_model_version == valid.outflow_model_version == valid.forecast.model_version
    assert IssuedCashForecast.model_validate_json(valid.model_dump_json()) == valid


@pytest.mark.parametrize("direction", ["inflow", "outflow"])
def test_unapplied_directions_cannot_carry_model_versions(direction):
    request = categorized_request().model_copy(update={"historical_transactions": None})
    financial = forecast_cash_flow(request)
    original = issued(version=None)
    data = {**original.model_dump(), "forecast": financial.model_dump(), f"{direction}_model_version": "v1"}
    with pytest.raises(ValidationError, match="unapplied statistical"):
        IssuedCashForecast.model_validate(data)


def test_stateless_and_legacy_applied_direction_labels_remain_valid():
    stateless = issued(version=None)
    assert stateless.forecast.model_version is None
    assert stateless.inflow_model_version is stateless.outflow_model_version is None
    legacy = issued(version="legacy_v1")
    assert legacy.forecast.model_version is None
    assert legacy.inflow_model_version == legacy.outflow_model_version == "legacy_v1"
