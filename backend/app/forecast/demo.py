"""Executable synthetic end-to-end workflow and single-run laptop timings.

Run from the repository root: python -m backend.app.forecast.demo
All artifacts are temporary. No business records, network calls or payment actions.
"""

from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from .financial_schemas import CashForecastRequest, CategoryScheduleCoverage, ScheduledCashEvent, VerifiedOpeningBalance
from .interfaces import ForecastIssueRequest, PreparationRequest, issue_forecast, prepare_history
from .monitoring import LocalForecastMonitor
from .monitoring_schemas import ActualObservation
from .persistence import LocalModelRegistry
from .reconciliation import reconcile_history
from .retraining import retrain_model
from .retraining_schemas import RetrainingRequest
from .scenario_schemas import MoveEventOperation, ScenarioRequest
from .scenarios import simulate_scenario
from .schemas import DailyCash, DailyHistory, MLConfig
from .trained import train_forecast_model


def _activity(day, index):
    weekday_sales = (0, 3000, 6000, 2000, 8000, 18000, 12000)
    weekday_costs = (1000, 2000, 0, 3000, 1000, 4000, 2000)
    return 60000 + index * 120 + weekday_sales[day.weekday()], 22000 + index * 8 + weekday_costs[day.weekday()]


def run_synthetic_workflow(*, days=365, use_ml=True):
    if type(days) is not int or days < 30:
        raise ValueError("synthetic workflow needs at least 30 history days")
    start = date(2026, 10, 13)
    generated = datetime(2026, 10, 13, 14, tzinfo=timezone.utc)
    first = start - timedelta(days=days)
    rows = ["transaction_id,date,amount_cents,direction,currency,category,payment_status"]
    for index in range(days):
        day = first + timedelta(days=index)
        sales, operating = _activity(day, index)
        for prefix, amount, direction, category in (
            ("sale", sales, "inflow", "sales"), ("operating", operating, "outflow", "operations"),
            ("invoice", 5500, "inflow", "invoices"), ("supplier", 7500, "outflow", "suppliers"),
        ):
            rows.append(f"demo_{prefix}_{index},{day},{amount},{direction},USD,{category},settled")
    source_text = "\n".join(rows)
    timings = {}
    clock = perf_counter()
    prepared = prepare_history(PreparationRequest(csv_data=source_text, coverage_start=first,
        coverage_end=start - timedelta(days=1), complete_coverage=True))
    timings["data_preparation_seconds"] = perf_counter() - clock
    ml = MLConfig() if use_ml else None
    financial = CashForecastRequest(history=prepared.history, historical_transactions=prepared.source,
        opening_balance=VerifiedOpeningBalance(balance_cents=500000, currency="USD", balance_date=start, evidence_id="synthetic_bank"),
        forecast_start_date=start, safety_reserve_cents=200000, business_timezone="America/Chicago", ml_config=ml,
        known_events=(
            ScheduledCashEvent(event_id="future_invoice", source_id="invoice_future", direction="inflow", amount_cents=40000,
                currency="USD", status="invoice_unpaid", category="invoices", expected_date=start,
                projection_assumption="Synthetic customer collection assumption; not verified cash."),
            ScheduledCashEvent(event_id="future_bill", source_id="bill_future", direction="outflow", amount_cents=950000,
                currency="USD", status="scheduled_expense", category="suppliers", expected_date=start + timedelta(days=1)),
        ), category_coverage=tuple(CategoryScheduleCoverage(category=category, direction=direction,
            evidence_id=f"synthetic_complete_{category}", complete_for_forecast_window=True)
            for category, direction in (("invoices", "inflow"), ("suppliers", "outflow"))))
    residual, _ = reconcile_history(financial)
    clock = perf_counter()
    model = train_forecast_model(residual, business_id="synthetic_shop", model_version="v1", trained_at=generated, ml_config=ml)
    timings["model_training_selection_seconds"] = perf_counter() - clock
    with TemporaryDirectory(prefix="cashflow-synthetic-") as directory:
        root = Path(directory).resolve()
        registry = LocalModelRegistry(root / "models")
        clock = perf_counter()
        registry.save_candidate(model)
        loaded = registry.load("synthetic_shop", "v1", expected_metadata=model.metadata)
        registry.promote("synthetic_shop", "v1")
        timings["save_reload_seconds"] = perf_counter() - clock
        issuance_request = ForecastIssueRequest(issuance_id="synthetic_issue1", business_id="synthetic_shop",
            generated_at=generated, financial=financial)
        clock = perf_counter()
        issued = issue_forecast(issuance_request, trained_model=loaded)
        timings["financial_forecast_seconds"] = perf_counter() - clock
        assert issued.forecast.first_reserve_breach_date == start + timedelta(days=1)
        clock = perf_counter()
        comparison = simulate_scenario(financial, ScenarioRequest(scenario_id="synthetic_deferral",
            operations=(MoveEventOperation(operation_id="defer", event_id="future_bill", expected_date=start + timedelta(days=3),
                assumption="Synthetic supplier approval; payment is only hypothetically deferred."),)), baseline=issued.forecast)
        timings["scenario_simulation_seconds"] = perf_counter() - clock
        assert comparison.scenario.first_reserve_breach_date is None
        monitor = LocalForecastMonitor(root / "monitoring")
        monitor.record_forecast(issued)
        appended = []
        for index in range(14):
            day = start + timedelta(days=index)
            sales, operating = _activity(day, days + index)
            invoice = 40000 if index == 0 else 0
            bill = 950000 if index == 1 else 0
            monitor.record_actual(ActualObservation(business_id="synthetic_shop", observation_id=f"actual_{day}",
                currency="USD", date=day, inflow_cents=sales + invoice, outflow_cents=operating + bill,
                verified=True, complete=True, verification_evidence_id=f"synthetic_settlement_{day}",
                observed_at=generated + timedelta(days=index + 1)))
            appended.append(DailyCash(date=day, currency="USD", inflow_cents=sales, outflow_cents=operating,
                evidence_ids=(f"demo_sale_{days + index}", f"demo_operating_{days + index}")))
        report = monitor.evaluate("synthetic_shop")
        assert report.eligible_direction_errors == 4
        updated = DailyHistory(currency="USD", days=residual.days + tuple(appended), complete_coverage=True,
            coverage_start=residual.coverage_start, coverage_end=appended[-1].date)
        clock = perf_counter()
        decision = retrain_model(registry, RetrainingRequest(business_id="synthetic_shop", decision_id="synthetic_new14",
            candidate_version="v2", now=generated + timedelta(days=14), history=updated, verified=True,
            verification_evidence_id="synthetic_verified_residual_history"), monitoring=report)
        timings["retraining_evaluation_seconds"] = perf_counter() - clock
        assert decision.status in ("retained", "promoted")
        return {
            "is_synthetic": True, "history_days": days, "csv_rows": len(prepared.source.transactions),
            "csv_bytes": len(source_text.encode()), "currency": issued.forecast.currency,
            "selected_models": {"inflow": issued.forecast.selected_inflow_model, "outflow": issued.forecast.selected_outflow_model},
            "baseline_closing_cents": [day.projected_closing_balance_cents for day in issued.forecast.days],
            "scenario_closing_cents": [day.projected_closing_balance_cents for day in comparison.scenario.days],
            "baseline_first_breach": str(issued.forecast.first_reserve_breach_date),
            "baseline_maximum_shortfall_cents": issued.forecast.maximum_reserve_shortfall_cents,
            "scenario_first_breach": comparison.scenario.first_reserve_breach_date,
            "uncertainty_status": issued.forecast.uncertainty.status,
            "verified_actual_days": report.recorded_actual_days, "matched_direction_errors": report.eligible_direction_errors,
            "retraining_status": decision.status, "active_version": decision.active_version,
            "timings_seconds": {key: round(value, 6) for key, value in timings.items()},
            "measurement_scope": "One synthetic run on this host; warm imports; no real-business predictive accuracy or production throughput claim.",
        }


if __name__ == "__main__":
    print(json.dumps(run_synthetic_workflow(), indent=2))
