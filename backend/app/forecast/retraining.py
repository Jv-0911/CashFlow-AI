"""Explicit retraining with fresh final windows, frozen incumbents and safe promotion."""

from dataclasses import replace
from hashlib import sha256
from math import ceil, sqrt
from statistics import mean, stdev

from .baselines import METHODS, _predict, validate_history
from .evaluation import calculate_metrics
from .monitoring_schemas import MonitoringReport
from .persistence import LocalModelRegistry
from .retraining_schemas import DirectionPromotionEvidence, RetrainingDecision, RetrainingRequest
from .schemas import BaselineConfig, DailyHistory
from .trained import forecast_trained_model, history_fingerprint, train_forecast_model


def _prefix(history, index):
    return DailyHistory(currency=history.currency, days=history.days[:index + 1], complete_coverage=True,
        coverage_start=history.coverage_start, coverage_end=history.days[index].date, warnings=history.warnings)


def _metrics(rows, direction, config):
    return calculate_metrics([getattr(actual, direction + "_cents") for _, _, actual in rows],
        [getattr(predicted, "predicted_" + direction + "_cents") for _, predicted, _ in rows],
        wape_minimum_actual_cents=config.wape_minimum_actual_cents)


def _direction_gate(candidate_rows, incumbent_rows, baselines, direction, config, policy):
    candidate = _metrics(candidate_rows, direction, config)
    incumbent = _metrics(incumbent_rows, direction, config) if incumbent_rows else None
    baseline_metrics = {method: _metrics(rows, direction, config) for method, rows in baselines.items()}
    eligible = {method: metric for method, metric in baseline_metrics.items() if metric.mae_cents is not None}
    if not eligible or candidate.mae_cents is None or incumbent is not None and incumbent.mae_cents is None:
        baseline_method = METHODS[0]
        return DirectionPromotionEvidence(direction=direction, candidate=candidate, incumbent=incumbent,
            best_baseline_method=baseline_method, best_baseline=baseline_metrics[baseline_method], final_windows=0,
            improves_incumbent=False, no_material_regression=False, reason="Finite paired final metrics are unavailable.")
    baseline_method = min(eligible, key=lambda method: (eligible[method].mae_cents, METHODS.index(method)))
    baseline = eligible[baseline_method]
    reference = incumbent or baseline
    margin = max(policy.minimum_improvement_cents, policy.minimum_improvement_relative * reference.mae_cents)
    origins = sorted({origin for origin, _, _ in candidate_rows})
    safe = candidate.mae_cents <= baseline.mae_cents + max(policy.minimum_improvement_cents, policy.minimum_improvement_relative * baseline.mae_cents)
    for rows, comparison in ((baselines[baseline_method], baseline), (incumbent_rows, incumbent)):
        if comparison is None:
            continue
        tolerance = max(policy.minimum_improvement_cents, policy.minimum_improvement_relative * comparison.mae_cents)
        safe &= candidate.mae_cents <= comparison.mae_cents + tolerance
        safe &= abs(candidate.bias_cents) <= abs(comparison.bias_cents) + tolerance
        safe &= candidate.absolute_error_std_cents <= comparison.absolute_error_std_cents + tolerance
        for horizon in range(1, max(predicted.horizon for _, predicted, _ in candidate_rows) + 1):
            candidate_lead = _metrics([row for row in candidate_rows if row[1].horizon == horizon], direction, config)
            reference_lead = _metrics([row for row in rows if row[1].horizon == horizon], direction, config)
            safe &= candidate_lead.mae_cents <= reference_lead.mae_cents + tolerance
    gains = []
    reference_rows = incumbent_rows or baselines[baseline_method]
    for origin in origins:
        losses = []
        for rows in (reference_rows, candidate_rows):
            losses.append(mean(abs(getattr(predicted, "predicted_" + direction + "_cents") - getattr(actual, direction + "_cents"))
                for key, predicted, actual in rows if key == origin))
        gains.append(losses[0] - losses[1])
    gain = mean(gains)
    guard = max(margin, 2 * stdev(gains) / sqrt(len(gains)))
    improves = gain > guard and sum(value > 0 for value in gains) >= ceil(2 * len(gains) / 3)
    return DirectionPromotionEvidence(direction=direction, candidate=candidate, incumbent=incumbent,
        best_baseline_method=baseline_method, best_baseline=baseline, final_windows=len(origins),
        paired_mae_gain_cents=gain, required_gain_cents=guard, improves_incumbent=improves,
        no_material_regression=bool(safe), reason=(
            f"Fresh paired MAE gain {gain:.3f} cents; required gain {guard:.3f}. "
            f"Baseline, lead, bias and stability guards {'pass' if safe else 'fail'}."))


def retrain_model(registry: LocalModelRegistry, request: RetrainingRequest, *, monitoring: MonitoringReport | None = None) -> RetrainingDecision:
    """A synchronous, bounded operation; no scheduling or deployment side effects outside registry."""
    request = RetrainingRequest.model_validate(request.model_dump())
    if monitoring is not None:
        monitoring = MonitoringReport.model_validate(monitoring.model_dump())
    with registry.retraining_lock(request.business_id):
        return _retrain_locked(registry, request, monitoring=monitoring)


def _retrain_locked(registry, request, *, monitoring=None):
    history = validate_history(request.history)
    prior_decisions = registry.get_decisions(request.business_id)
    fingerprint = history_fingerprint(history)
    request_fingerprint = sha256((request.model_dump_json() + (monitoring.model_dump_json() if monitoring is not None else "")).encode()).hexdigest()
    for item in prior_decisions:
        if item.get("decision_id") == request.decision_id:
            if item.get("request_fingerprint") != request_fingerprint:
                raise ValueError("decision_id already describes a different retraining request")
            return RetrainingDecision.model_validate(item["result"])
    state = registry.get_status(request.business_id)
    active_version = state.active_version
    active = registry.load(request.business_id, active_version, expected_currency=history.currency) if active_version else None
    if active is not None:
        original = active.history.days
        if history.days[:len(original)] != original or len(history.days) < len(original):
            raise ValueError("verified retraining history must preserve the incumbent's historical prefix")
        if request.now < active.metadata.trained_at:
            raise ValueError("retraining decision time precedes active model training")
        if request.horizon_days != active.metadata.horizon_days:
            raise ValueError("retraining compares the incumbent's configured horizon; changing horizon requires a separately reviewed model")
    new_count = len(history.days) - (active.metadata.training_observations if active else 0)
    config = request.baseline_config or (active.metadata.baseline_config if active else BaselineConfig())
    ml_config = request.ml_config if request.ml_config is not None else (active.metadata.ml_config if active else None)
    triggers = []
    if active is None:
        triggers.append("no_active_model")
    if new_count >= request.policy.minimum_new_observations:
        triggers.append("new_verified_observations")
    if active is not None and (request.now - active.metadata.trained_at).days >= request.policy.maximum_training_age_days:
        triggers.append("training_age")
    if active is not None and (config != active.metadata.baseline_config or ml_config != active.metadata.ml_config or request.horizon_days != active.metadata.horizon_days):
        triggers.append("configuration_changed")
    if monitoring is not None:
        if monitoring.business_id != request.business_id or monitoring.currency not in (None, history.currency):
            raise ValueError("monitoring evidence belongs to a different business or currency")
        if any(error.generated_at > request.now or error.actual_observed_at > request.now or error.target_date > history.days[-1].date for error in monitoring.errors):
            raise ValueError("monitoring evidence includes future or unavailable observations")
        if monitoring.material_deterioration:
            # Deterioration evidence must refer to the active version, not a superseded model.
            if any(group.material_deterioration and group.model_version == active_version for group in monitoring.groups):
                triggers.append("sustained_deterioration")

    def finish(status, reason, *, candidate=None, origins=(), through=None, evaluation=()):
        result = RetrainingDecision(decision_id=request.decision_id, business_id=request.business_id,
            candidate_version=request.candidate_version, status=status, decided_at=request.now,
            previous_active_version=active_version, active_version=registry.get_status(request.business_id).active_version,
            triggers=tuple(triggers), new_verified_observations=new_count,
            selection_training_end=candidate.metadata.training_end if candidate else None,
            final_origins=tuple(history.days[index].date for index in origins), evaluated_through=through,
            evaluation=evaluation, reason=reason)
        registry.record_decision(request.business_id, {"decision_id": request.decision_id,
            "request_fingerprint": request_fingerprint, "dataset_fingerprint": fingerprint,
            "result": result.model_dump(mode="json")})
        return result

    if not triggers:
        return finish("not_triggered", "No configured new-data, age, configuration, or sustained-error trigger.")
    # Do not reuse any final outcome already consumed by a previous decision.
    consumed = [item.get("result", {}).get("evaluated_through") or item.get("reserved_through") for item in prior_decisions]
    if active is not None:
        consumed.append(active.metadata.promotion_evidence.get("evaluated_through"))
    watermark = max([active.metadata.training_end] if active and active.metadata.training_end else [history.days[0].date])
    from datetime import date
    watermark = max([watermark] + [date.fromisoformat(value) for value in consumed if value])
    minimum = max(config.minimum_history_days, config.moving_average_window, config.weekday_samples * 7)
    first_origin = max(minimum - 1, next((index for index, day in enumerate(history.days) if day.date >= watermark), len(history.days)))
    origins = tuple(range(first_origin, len(history.days) - request.horizon_days, request.horizon_days))[-request.policy.maximum_final_windows:]
    if len(origins) < request.policy.minimum_final_windows:
        return finish("insufficient_evidence", "Insufficient fresh, complete, disjoint final windows; active model retained.")
    if request.candidate_version in state.previous_versions or request.candidate_version in state.candidate_versions or request.candidate_version in state.failed_versions or request.candidate_version == active_version:
        raise ValueError("candidate version must be new and immutable")
    through = history.days[origins[-1] + request.horizon_days].date
    # Reserve outcomes before training/evaluation. Failure cannot make this holdout reusable.
    registry.record_decision(request.business_id, {"reservation_id": request.decision_id,
        "reserved_through": through.isoformat(), "reserved_origins": [history.days[index].date.isoformat() for index in origins],
        "request_fingerprint": request_fingerprint})
    candidate = None
    last_evaluated_target = None
    try:
        training = _prefix(history, origins[0])
        candidate = train_forecast_model(training, business_id=request.business_id, model_version=request.candidate_version,
            trained_at=request.now, horizon_days=request.horizon_days, config=config, ml_config=ml_config)
        if not candidate.metadata.inflow.eligible or not candidate.metadata.outflow.eligible:
            return finish("retained", "Candidate selection lacks adequate chronological evidence; no promotion.",
                candidate=candidate)
        candidate_rows, incumbent_rows, baseline_rows = [], [], {method: [] for method in METHODS}
        for index in origins:
            current = _prefix(history, index)
            origin = current.days[-1].date
            candidate_prediction = forecast_trained_model(candidate, history=current, horizon_days=request.horizon_days)
            incumbent_prediction = forecast_trained_model(active, history=current, horizon_days=request.horizon_days) if active else None
            for prediction, rows in ((candidate_prediction, candidate_rows), (incumbent_prediction, incumbent_rows)):
                if prediction is None:
                    continue
                if len(prediction.days) != request.horizon_days:
                    raise ValueError("candidate or incumbent failed to produce a complete final path")
                rows.extend((origin, day, history.days[index + day.horizon]) for day in prediction.days)
                last_evaluated_target = history.days[index + request.horizon_days].date
            for method in METHODS:
                predicted = _predict(current, request.horizon_days, origin, method, config, ()).days
                if any(day.effective_method != method for day in predicted):
                    raise ValueError("a comparison baseline requires fallback on the final windows")
                baseline_rows[method].extend((origin, day, history.days[index + day.horizon]) for day in predicted)
        evaluation = tuple(_direction_gate(candidate_rows, incumbent_rows, baseline_rows, direction, config, request.policy)
            for direction in ("inflow", "outflow"))
        promote = all(item.no_material_regression for item in evaluation) and (active is None or any(item.improves_incumbent for item in evaluation))
        evidence = {"final_origins": [history.days[index].date.isoformat() for index in origins],
            "evaluated_through": through.isoformat(), "independent_of_selection": True,
            "directions": [item.model_dump(mode="json") for item in evaluation], "verification_evidence_id": request.verification_evidence_id}
        candidate = replace(candidate, metadata=candidate.metadata.model_copy(update={"promotion_evidence": evidence}))
        registry.save_candidate(candidate)
        if promote:
            registry.promote(request.business_id, request.candidate_version, expected_active_version=active_version)
            return finish("promoted", "Fresh final gate passed; exact pre-holdout candidate promoted.", candidate=candidate,
                origins=origins, through=through, evaluation=evaluation)
        return finish("retained", "Candidate did not establish safe improvement over incumbent and baselines; active model retained.",
            candidate=candidate, origins=origins, through=through, evaluation=evaluation)
    except (ValueError, RuntimeError, ArithmeticError, OSError) as exc:
        if registry.get_status(request.business_id).active_version == request.candidate_version:
            raise RuntimeError("Model promotion succeeded but final decision logging failed; reserved evaluation windows remain consumed.") from exc
        registry.mark_failed(request.business_id, request.candidate_version, str(exc))
        return finish("failed", f"Candidate operation failed: {exc}; previous active model retained.",
            candidate=candidate, origins=origins if last_evaluated_target else (), through=last_evaluated_target)
