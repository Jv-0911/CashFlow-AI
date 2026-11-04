from datetime import timedelta

import pytest
from pydantic import ValidationError

from backend.app.forecast import BaselineConfig, UncertaintyConfig, forecast_cash_flow
from backend.app.forecast.financial_schemas import EmpiricalRange
from backend.app.forecast.reconciliation import reconcile_history
from backend.app.forecast.uncertainty import estimate_cash_uncertainty
from backend.tests.forecast.test_reconciliation import START, categorized_request


def test_sufficient_samples_produce_conditional_empirical_ranges_only():
    result = forecast_cash_flow(categorized_request())
    assert result.uncertainty.status == "approximate_empirical_ranges"
    assert result.uncertainty.intervals_available
    assert result.uncertainty.calibrated_coverage is None
    assert not result.uncertainty.known_event_uncertainty_included
    assert result.uncertainty.conditional_on_event_assumptions
    for row, day in zip(result.uncertainty.horizons, result.days):
        assert row.residual_inflow.validation_samples >= 8
        assert row.projected_closing_balance.validation_samples >= 8
        assert row.residual_inflow.lower_cents == row.residual_inflow.upper_cents == 100
        assert row.projected_closing_balance.lower_cents == row.projected_closing_balance.upper_cents == day.projected_closing_balance_cents
    assert any("zero historical spread" in warning for warning in result.uncertainty.warnings)


@pytest.mark.parametrize("count", [1, 14, 16])
def test_insufficient_training_or_residual_samples_do_not_invent_bounds(count):
    result = forecast_cash_flow(categorized_request(count=count))
    assert result.uncertainty.status == "unavailable"
    for row in result.uncertainty.horizons:
        for interval in (row.residual_inflow, row.residual_outflow, row.projected_closing_balance):
            assert interval.lower_cents is interval.upper_cents is None
            assert interval.status == "unavailable"


def test_sample_threshold_is_configurable_and_counts_are_reported():
    request = categorized_request().model_copy(update={"uncertainty_config": UncertaintyConfig(minimum_samples=1000)})
    result = forecast_cash_flow(request)
    assert result.uncertainty.status == "unavailable"
    assert result.uncertainty.horizons[0].residual_inflow.validation_samples > 0
    assert "1000" in result.uncertainty.horizons[0].residual_inflow.reason


def test_complete_paths_preserve_cross_day_error_cancellation():
    request = categorized_request(count=60, alternating=True).model_copy(update={
        "baseline_config": BaselineConfig(moving_average_window=2, origin_step=3)})
    result = forecast_cash_flow(request)
    assert result.selected_inflow_model == "moving_average"
    first, second = result.uncertainty.horizons
    assert first.residual_inflow.lower_cents == second.residual_inflow.lower_cents == 0
    assert first.residual_inflow.upper_cents == second.residual_inflow.upper_cents == 200
    assert first.projected_closing_balance.upper_cents - first.projected_closing_balance.lower_cents == 200
    # Day 1 and day 2 errors cancel within every path: summing separate marginal bounds would be wrong.
    assert second.projected_closing_balance.lower_cents == second.projected_closing_balance.upper_cents == result.days[1].projected_closing_balance_cents
    assert second.projected_closing_balance.validation_samples >= 8


def test_long_horizon_reports_short_lead_ranges_and_insufficient_complete_paths():
    request = categorized_request(count=60).model_copy(update={"forecast_horizon_days": 30})
    result = forecast_cash_flow(request)
    assert result.uncertainty.status == "partially_available"
    assert result.uncertainty.horizons[0].projected_closing_balance.status == "approximate_empirical_range"
    last = result.uncertainty.horizons[-1]
    assert last.projected_closing_balance.status == "unavailable"
    assert last.projected_closing_balance.validation_samples < 8
    assert last.projected_closing_balance.lower_cents is None


def test_unknown_event_dates_block_cumulative_ranges_without_blocking_known_residual_ranges():
    request = categorized_request()
    invoice = request.known_events[0].model_copy(update={"expected_date": None})
    request = request.model_copy(update={"known_events": (invoice, request.known_events[1])})
    result = forecast_cash_flow(request)
    assert not result.reconciliation.fully_reconciled
    assert all(row.projected_closing_balance.status == "unavailable" for row in result.uncertainty.horizons)
    assert result.uncertainty.horizons[0].residual_inflow.status == "approximate_empirical_range"


def test_stale_history_does_not_reuse_ordinary_lead_calibration():
    request = categorized_request()
    new_start = START + timedelta(days=3)
    request = request.model_copy(update={"forecast_start_date": new_start,
        "opening_balance": request.opening_balance.model_copy(update={"balance_date": new_start})})
    result = forecast_cash_flow(request)
    assert result.uncertainty.status == "unavailable"
    assert result.days[0].date == new_start


def test_one_unknown_overlap_direction_blocks_balance_uncertainty():
    request = categorized_request()
    invoice = request.known_events[0].model_copy(update={"category": None})
    request = request.model_copy(update={"known_events": (invoice, request.known_events[1])})
    result = forecast_cash_flow(request)
    assert result.uncertainty.status == "partially_available"
    assert all(row.residual_inflow.status == row.projected_closing_balance.status == "unavailable" for row in result.uncertainty.horizons)
    assert result.uncertainty.horizons[0].residual_outflow.status == "approximate_empirical_range"


@pytest.mark.parametrize("change", ["future_actual", "duplicate_origin", "wrong_horizon_date"])
def test_invalid_backtest_paths_are_rejected(change):
    request = categorized_request()
    result = forecast_cash_flow(request)
    model = result.model_forecast
    evaluation = model.backtest.methods[0]
    point = evaluation.points[0]
    if change == "future_actual":
        point = point.model_copy(update={"origin": model.as_of, "date": model.as_of + timedelta(days=point.horizon)})
        points = (point,) + evaluation.points[1:]
    elif change == "duplicate_origin":
        points = evaluation.points + evaluation.points[:1]
    else:
        point = point.model_copy(update={"date": point.date + timedelta(days=1)})
        points = (point,) + evaluation.points[1:]
    evaluation = evaluation.model_copy(update={"points": points})
    backtest = model.backtest.model_copy(update={"methods": (evaluation,) + model.backtest.methods[1:]})
    model = model.model_copy(update={"backtest": backtest})
    residual, report = reconcile_history(request)
    with pytest.raises(ValueError):
        estimate_cash_uncertainty(model, residual, report, result.days, request.uncertainty_config)


def test_unavailable_range_contract_rejects_fabricated_bounds():
    with pytest.raises(ValidationError):
        EmpiricalRange(status="unavailable", lower_cents=0, upper_cents=100)
