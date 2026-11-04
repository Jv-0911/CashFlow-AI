from datetime import date, timedelta

import pytest

from backend.app.forecast import DailyCash, DailyHistory, IngestionError, calculate_metrics, forecast_baselines, ingest_csv, read_csv
from backend.app.forecast.models import prediction_cents


def test_ml_half_up_does_not_add_a_cent_at_float64_boundary():
    assert prediction_cents(float(2**53 - 1)) == 2**53 - 1
    assert prediction_cents(float(2**52 + 1)) == 2**52 + 1
    assert prediction_cents(12.5) == 13


def test_reused_historical_transaction_identity_is_rejected():
    days = tuple(DailyCash(date=date(2026, 10, 1) + timedelta(days=i), currency="USD",
        inflow_cents=100, evidence_ids=("same_receipt",)) for i in range(2))
    with pytest.raises(ValueError, match="evidence IDs"):
        forecast_baselines(DailyHistory(currency="USD", days=days))


def test_large_representable_error_dispersion_does_not_overflow_squares():
    metrics = calculate_metrics([0, 0], [10**200, 0])
    assert metrics.mae_cents == pytest.approx(5e199)
    assert metrics.absolute_error_std_cents == pytest.approx(5e199)


def test_unrepresentable_metrics_are_unavailable_not_infinite():
    metrics = calculate_metrics([0], [10**400])
    assert metrics.mae_cents is metrics.bias_cents is metrics.wape is None
    assert metrics.wape_unavailable_reason == "numeric_range_exceeded"


def test_huge_integer_history_preserves_forecast_even_without_finite_error_metrics():
    first = date(2026, 1, 1)
    days = tuple(DailyCash(date=first + timedelta(days=i), currency="USD", inflow_cents=(10**400 if i % 2 else 0)) for i in range(25))
    result = forecast_baselines(DailyHistory(currency="USD", days=days, complete_coverage=True,
        coverage_start=first, coverage_end=days[-1].date))
    assert result.days[0].predicted_inflow_cents == 0
    assert result.reliability == "insufficient_evidence"


def test_csv_limits_apply_before_parse_to_bytes_text_and_file(tmp_path):
    source = "date,amount_cents,direction,currency\n2026-10-01,100,inflow,USD\n"
    path = tmp_path / "upload.csv"
    path.write_text(source)
    for operation in (lambda: ingest_csv(source, max_bytes=10), lambda: ingest_csv(source.encode(), max_bytes=10), lambda: read_csv(path, max_bytes=10)):
        with pytest.raises(IngestionError) as error:
            operation()
        assert error.value.issues[0].code == "FILE_TOO_LARGE"
    assert ingest_csv(source, max_bytes=len(source)).transactions[0].amount_cents == 100


@pytest.mark.parametrize("limit", [0, -1, True, "10"])
def test_csv_limits_require_positive_strict_integer(limit):
    with pytest.raises(ValueError):
        ingest_csv("x", max_bytes=limit)
