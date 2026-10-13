from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from backend.app.forecast import (
    ActualObservation, CashForecastRequest, DailyCash, DailyHistory, ForecastIssueRequest,
    LocalForecastMonitor, LocalModelRegistry, MLConfig, RetrainingPolicy, RetrainingRequest,
    VerifiedOpeningBalance, forecast_trained_model, issue_forecast, retrain_model, train_forecast_model,
)
import backend.app.forecast.retraining as implementation


NOW = datetime(2026, 10, 13, 14, tzinfo=timezone.utc)


def history(count, *, trend=False):
    first = date(2026, 5, 1)
    days = tuple(DailyCash(date=first + timedelta(days=i), currency="USD",
        inflow_cents=100 + (20 * i if trend else 0), outflow_cents=20, evidence_ids=(f"day_{i}",)) for i in range(count))
    return DailyHistory(currency="USD", days=days, complete_coverage=True,
        coverage_start=first, coverage_end=days[-1].date)


def registry_with_active(tmp_path, *, count=60, trend=False):
    registry = LocalModelRegistry(tmp_path / "models")
    bundle = train_forecast_model(history(count, trend=trend), business_id="shop", model_version="v1", trained_at=NOW - timedelta(days=8))
    registry.save_candidate(bundle)
    registry.promote("shop", "v1")
    return registry


def request(count, *, trend=False, **updates):
    data = dict(business_id="shop", decision_id="decision1", candidate_version="v2", now=NOW,
        history=history(count, trend=trend), verification_evidence_id="ledger_complete", verified=True)
    data.update(updates)
    return RetrainingRequest(**data)


def test_small_verified_append_does_not_retrain(tmp_path, monkeypatch):
    registry = registry_with_active(tmp_path)
    monkeypatch.setattr(implementation, "train_forecast_model", lambda *a, **k: pytest.fail("unnecessary training"))
    decision = retrain_model(registry, request(64))
    assert decision.status == "not_triggered" and decision.new_verified_observations == 4
    assert decision.active_version == "v1" and not decision.evaluation


def test_triggered_age_without_fresh_windows_keeps_active(tmp_path):
    registry = registry_with_active(tmp_path)
    decision = retrain_model(registry, request(60, now=NOW + timedelta(days=30)))
    assert decision.status == "insufficient_evidence"
    assert "training_age" in decision.triggers and decision.active_version == "v1"


def test_equal_candidate_is_retained_and_decision_replays(tmp_path):
    registry = registry_with_active(tmp_path)
    req = request(84)
    decision = retrain_model(registry, req)
    assert decision.status == "retained" and decision.active_version == "v1"
    assert len(decision.final_origins) == 6
    assert all(item.no_material_regression and not item.improves_incumbent for item in decision.evaluation)
    assert retrain_model(registry, req) == decision
    assert len(registry.get_decisions("shop")) == 2  # Reservation and final decision.
    assert "day_0" not in str(registry.get_decisions("shop"))  # Hashes, not uploaded records.


def test_changed_request_cannot_reuse_decision_identity(tmp_path):
    registry = registry_with_active(tmp_path)
    retrain_model(registry, request(84))
    with pytest.raises(ValueError, match="different retraining"):
        retrain_model(registry, request(86))


def test_consumed_holdout_is_not_reused_by_another_attempt(tmp_path, monkeypatch):
    registry = registry_with_active(tmp_path)
    decision = retrain_model(registry, request(84))
    monkeypatch.setattr(implementation, "train_forecast_model", lambda *a, **k: pytest.fail("reused final outcomes"))
    again = retrain_model(registry, request(84, decision_id="decision2", candidate_version="v3"))
    assert again.status == "insufficient_evidence"
    assert decision.evaluated_through == history(84).days[-1].date


def test_candidate_training_failure_preserves_active_and_reserves_windows(tmp_path, monkeypatch):
    registry = registry_with_active(tmp_path)
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic training failure")
    monkeypatch.setattr(implementation, "train_forecast_model", fail)
    decision = retrain_model(registry, request(84))
    assert decision.status == "failed" and decision.active_version == "v1"
    assert "v2" in registry.get_status("shop").failed_versions
    assert registry.load("shop", "v1").metadata.model_version == "v1"
    again = retrain_model(registry, request(84, decision_id="decision2", candidate_version="v3"))
    assert again.status == "insufficient_evidence"


def test_worse_candidate_cannot_replace_active(tmp_path, monkeypatch):
    registry = registry_with_active(tmp_path)
    original = implementation.forecast_trained_model
    def worse(bundle, **kwargs):
        result = original(bundle, **kwargs)
        if bundle.metadata.model_version == "v2":
            result = result.model_copy(update={"days": tuple(day.model_copy(update={"predicted_inflow_cents": 10000}) for day in result.days)})
        return result
    monkeypatch.setattr(implementation, "forecast_trained_model", worse)
    decision = retrain_model(registry, request(84))
    assert decision.status == "retained" and decision.active_version == "v1"
    assert not decision.evaluation[0].no_material_regression


def test_real_ridge_candidate_beats_frozen_baseline_on_new_final_paths(tmp_path):
    registry = registry_with_active(tmp_path, trend=True)
    decision = retrain_model(registry, request(100, trend=True, ml_config=MLConfig(tree_minimum_days=1000)))
    assert decision.status == "promoted" and decision.active_version == "v2"
    assert decision.evaluation[0].improves_incumbent
    assert all(item.no_material_regression for item in decision.evaluation)
    candidate = registry.load("shop", "v2")
    assert candidate.metadata.inflow.method == "ridge"
    assert candidate.metadata.training_end == decision.selection_training_end < decision.final_origins[0] + timedelta(days=1)
    assert decision.final_origins[0] == decision.selection_training_end
    assert candidate.metadata.training_end < decision.evaluated_through
    assert candidate.metadata.promotion_evidence["independent_of_selection"] is True
    assert forecast_trained_model(candidate, history=history(100, trend=True)).days
    assert registry.rollback("shop").model_version == "v1"


def test_initial_model_can_pass_fresh_gate(tmp_path):
    registry = LocalModelRegistry(tmp_path / "models")
    result = retrain_model(registry, request(60))
    assert result.status == "promoted" and result.previous_active_version is None
    assert registry.get_status("shop").active_version == "v2"


def test_reservation_failure_cannot_deploy_candidate(tmp_path, monkeypatch):
    registry = registry_with_active(tmp_path)
    def fail(*args):
        raise OSError("decision storage unavailable")
    monkeypatch.setattr(registry, "record_decision", fail)
    with pytest.raises(OSError):
        retrain_model(registry, request(84))
    assert registry.get_status("shop").active_version == "v1"


def test_post_promotion_log_failure_does_not_mark_active_as_failed(tmp_path, monkeypatch):
    registry = registry_with_active(tmp_path, trend=True)
    original = registry.record_decision
    def fail_final(business_id, payload):
        if "result" in payload:
            raise OSError("final log unavailable")
        original(business_id, payload)
    monkeypatch.setattr(registry, "record_decision", fail_final)
    with pytest.raises(RuntimeError, match="promotion succeeded"):
        retrain_model(registry, request(100, trend=True, ml_config=MLConfig(tree_minimum_days=1000)))
    state = registry.get_status("shop")
    assert state.active_version == "v2" and "v2" not in state.failed_versions
    assert registry.get_decisions("shop")[0]["reserved_through"] == history(100).days[-1].date.isoformat()


def test_historical_corrections_and_horizon_changes_require_explicit_new_contract(tmp_path):
    registry = registry_with_active(tmp_path)
    updated = history(84)
    days = (updated.days[0].model_copy(update={"inflow_cents": 200}),) + updated.days[1:]
    with pytest.raises(ValueError, match="historical prefix"):
        retrain_model(registry, request(84, history=updated.model_copy(update={"days": days})))
    with pytest.raises(ValueError, match="configured horizon"):
        retrain_model(registry, request(84, horizon_days=3))


def deterioration_evidence(tmp_path):
    """Previously issued, versioned forecasts scored against later complete actuals."""
    original = history(60)
    updated = history(72)
    updated = updated.model_copy(update={"days": tuple(
        day.model_copy(update={"inflow_cents": 100 + 100 * (index - 59)}) if index >= 60 else day
        for index, day in enumerate(updated.days))})
    registry = LocalModelRegistry(tmp_path / "models")
    trained_at = datetime.combine(updated.days[60].date, datetime.min.time(), timezone.utc)
    bundle = train_forecast_model(original, business_id="shop", model_version="v1", trained_at=trained_at)
    registry.save_candidate(bundle)
    registry.promote("shop", "v1")
    monitor = LocalForecastMonitor(tmp_path / "monitor")
    for index in range(60, 70):
        day = updated.days[index]
        prefix = updated.model_copy(update={"days": updated.days[:index], "coverage_end": updated.days[index - 1].date})
        financial = CashForecastRequest(history=prefix, forecast_start_date=day.date,
            opening_balance=VerifiedOpeningBalance(balance_cents=1000, currency="USD",
                balance_date=day.date, evidence_id=f"opening_{index}"), safety_reserve_cents=0,
            business_timezone="America/Chicago")
        issued = issue_forecast(ForecastIssueRequest(issuance_id=f"issued_{index}", business_id="shop",
            generated_at=datetime.combine(day.date, datetime.min.time(), timezone.utc) + timedelta(hours=12),
            financial=financial), trained_model=bundle)
        monitor.record_forecast(issued)
        monitor.record_actual(ActualObservation(business_id="shop", observation_id=f"actual_{index}",
            currency="USD", date=day.date, inflow_cents=day.inflow_cents, outflow_cents=day.outflow_cents,
            verified=True, complete=True, verification_evidence_id=f"ledger_{index}",
            observed_at=issued.generated_at + timedelta(days=1)))
    report = monitor.evaluate("shop")
    assert report.material_deterioration
    assert any(group.material_deterioration and group.direction == "inflow" and group.horizon == 1 for group in report.groups)
    req = request(72, history=updated, policy=RetrainingPolicy(minimum_new_observations=1000, maximum_training_age_days=1000))
    return registry, req, report


def test_real_sustained_actual_errors_trigger_evaluation_without_forcing_promotion(tmp_path):
    registry, req, report = deterioration_evidence(tmp_path)
    decision = retrain_model(registry, req, monitoring=report)
    assert decision.triggers == ("sustained_deterioration",)
    assert decision.status == "retained" and decision.active_version == "v1"
    assert decision.evaluation and not any(item.improves_incumbent for item in decision.evaluation)


def test_superseded_model_deterioration_does_not_trigger_retraining(tmp_path, monkeypatch):
    registry, req, report = deterioration_evidence(tmp_path)
    report = report.model_copy(update={"groups": tuple(group.model_copy(update={"model_version": "old"}) for group in report.groups)})
    monkeypatch.setattr(implementation, "train_forecast_model", lambda *a, **k: pytest.fail("obsolete model triggered training"))
    decision = retrain_model(registry, req, monitoring=report)
    assert decision.status == "not_triggered" and decision.active_version == "v1"


@pytest.mark.parametrize("change", ["business", "currency", "future_actual"])
def test_retraining_rejects_unavailable_or_foreign_monitoring_evidence(tmp_path, change):
    registry, req, report = deterioration_evidence(tmp_path)
    if change == "future_actual":
        error = report.errors[0].model_copy(update={"actual_observed_at": req.now + timedelta(days=1)})
        report = report.model_copy(update={"errors": (error,) + report.errors[1:]})
    else:
        report = report.model_copy(update={"business_id" if change == "business" else "currency": "other" if change == "business" else "EUR"})
    with pytest.raises(ValueError, match="different business or currency|future or unavailable"):
        retrain_model(registry, req, monitoring=report)
    assert registry.get_status("shop").active_version == "v1"


@pytest.mark.parametrize("change", [{"verified": False}, {"verified": 1}, {"verified": "true"},
    {"candidate_version": "../v2"}, {"history": history(10).model_copy(update={"complete_coverage": False, "coverage_start": None, "coverage_end": None})}])
def test_unverified_or_unsafe_requests_rejected(change):
    data = request(84).model_dump()
    data.update(change)
    with pytest.raises(ValidationError):
        RetrainingRequest.model_validate(data)


@pytest.mark.parametrize("change", [{"minimum_final_windows": 2}, {"maximum_final_windows": 11},
    {"minimum_final_windows": 5, "maximum_final_windows": 3}, {"minimum_new_observations": True}])
def test_invalid_retraining_policy(change):
    with pytest.raises(ValidationError):
        RetrainingPolicy(**change)
