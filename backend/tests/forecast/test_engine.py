from datetime import date, datetime

import pytest
from pydantic import ValidationError

from backend.app.forecast import DailyCash, aggregate_daily, calculate_balances, read_csv


START = date(2026, 10, 10)


def calculate(days=(), **overrides):
    kwargs = dict(start_date=START, horizon_days=3, opening_balance_cents=1000,
                  safety_reserve_cents=500, currency="USD")
    kwargs.update(overrides)
    return calculate_balances(days, **kwargs)


def test_balances_breach_equality_and_no_mutation():
    inputs = [DailyCash(date=START, currency="USD", inflow_cents=100, outflow_cents=600, evidence_ids=("a",)),
              DailyCash(date=date(2026, 10, 12), currency="USD", outflow_cents=501, evidence_ids=("b",))]
    before = [day.model_dump() for day in inputs]
    result = calculate(inputs)
    assert [day.closing_balance_cents for day in result.days] == [500, 500, -1]
    assert [day.opening_balance_cents for day in result.days] == [1000, 500, 500]
    assert [day.below_safety_reserve for day in result.days] == [False, False, True]
    assert result.first_reserve_breach_date == date(2026, 10, 12)
    assert result.days[2].shortfall_cents == 501
    assert result.days[1].evidence_ids == ()
    assert before == [day.model_dump() for day in inputs]
    assert result == calculate(inputs)
    assert result.uncertainty == "not_estimated"


def test_no_transactions_and_no_breach():
    result = calculate()
    assert len(result.days) == 3
    assert all(day.closing_balance_cents == 1000 for day in result.days)
    assert result.first_reserve_breach_date is None
    assert all(day.shortfall_cents == 0 for day in result.days)


def test_initial_negative_balance_and_zero_reserve():
    result = calculate(opening_balance_cents=-1, safety_reserve_cents=0)
    assert result.first_reserve_breach_date == START
    assert result.days[0].shortfall_cents == 1


def test_large_integer_money_is_exact():
    amount = 10**40 + 1
    cash = DailyCash(date=START, currency="USD", inflow_cents=amount)
    assert calculate([cash]).days[0].closing_balance_cents == amount + 1000


@pytest.mark.parametrize("overrides", [
    {"horizon_days": 0}, {"horizon_days": 31}, {"horizon_days": True}, {"horizon_days": 2.0},
    {"opening_balance_cents": 1.5}, {"opening_balance_cents": True},
    {"safety_reserve_cents": -1}, {"safety_reserve_cents": "500"},
    {"currency": "ZZZ"}, {"start_date": "2026-10-10"},
    {"start_date": date.max, "horizon_days": 2},
])
def test_invalid_calculation_inputs(overrides):
    with pytest.raises((ValueError, ValidationError)):
        calculate(**overrides)


@pytest.mark.parametrize("value", [-1, 0.5, True, "1"])
def test_invalid_daily_amount(value):
    with pytest.raises(ValidationError):
        DailyCash(date=START, currency="USD", inflow_cents=value)


def test_duplicate_days_rejected():
    cash = DailyCash(date=START, currency="USD", inflow_cents=100)
    with pytest.raises(ValueError, match="duplicate daily"):
        calculate([cash, cash])


def test_duplicate_receipt_evidence_rejected():
    with pytest.raises(ValueError, match="evidence"):
        calculate([DailyCash(date=START, currency="USD", evidence_ids=("invoice_1",)),
                   DailyCash(date=date(2026, 10, 11), currency="USD", evidence_ids=("invoice_1",))])


def test_currency_and_out_of_window_rejected():
    with pytest.raises(ValueError, match="currency"):
        calculate([DailyCash(date=START, currency="EUR")])
    with pytest.raises(ValueError, match="outside"):
        calculate([DailyCash(date=date(2026, 10, 9), currency="USD")])


def test_complete_csv_to_balance_workflow():
    from pathlib import Path

    data = read_csv(Path(__file__).parent / "fixtures" / "demo_history.csv")
    history = aggregate_daily(data, coverage_start=START, coverage_end=date(2026, 10, 12), complete_coverage=True)
    result = calculate(history.days)
    assert [day.closing_balance_cents for day in result.days] == [1500, 1500, 400]
    assert result.first_reserve_breach_date == date(2026, 10, 12)
    assert result.days[-1].shortfall_cents == 100


@pytest.mark.parametrize("value", [True, 1791586800, datetime(2026, 10, 10), "10/10/2026"])
def test_daily_dates_reject_implicit_timestamp_conversion(value):
    with pytest.raises(ValidationError):
        DailyCash(date=value, currency="USD")


def test_daily_date_iso_json_and_maximum_horizon():
    cash = DailyCash.model_validate({"date": "2026-10-10", "currency": "USD"})
    assert cash.date == START
    assert len(calculate([cash], horizon_days=30).days) == 30
