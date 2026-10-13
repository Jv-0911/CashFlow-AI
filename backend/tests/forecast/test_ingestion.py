from datetime import date

import pytest

from backend.app.forecast import IngestionError, aggregate_daily, ingest_csv, read_csv


HEADER = "transaction_id,date,amount_cents,direction,currency"


def test_valid_aliases_normalization_and_source_preservation(tmp_path):
    source = "\ufeffID,Transaction Date,Amount,Transaction Type,Currency Code,occupancy,description\n b ,2026-10-12,12.34,CREDIT,usd,0.8,Booking\na,2026-10-11,0,debit,USD,,Fee\n"
    path = tmp_path / "synthetic.csv"
    path.write_text(source, encoding="utf-8")
    result = read_csv(path)
    assert [item.transaction_id for item in result.transactions] == ["a", "b"]
    assert result.transactions[1].amount_cents == 1234
    assert result.transactions[1].direction == "inflow"
    assert result.transactions[1].source_fields["occupancy"] == "0.8"
    assert path.read_text(encoding="utf-8") == source
    assert result == ingest_csv(path.read_bytes())
    assert result.model_dump_json() == read_csv(path).model_dump_json()


@pytest.mark.parametrize("source,code", [
    ("", "EMPTY_FILE"),
    ("  \n", "EMPTY_FILE"),
    (HEADER + "\n", "NO_TRANSACTIONS"),
    ("date,amount_cents,currency\n2026-10-12,1,USD", "MISSING_COLUMNS"),
    ("date,direction,currency\n2026-10-12,inflow,USD", "MISSING_COLUMNS"),
    ("date,amount_cents,direction\n2026-10-12,1,inflow", "MISSING_COLUMNS"),
    ("date,date,amount_cents,direction,currency", "INVALID_HEADERS"),
    ("date,transaction_date,amount_cents,direction,currency", "AMBIGUOUS_COLUMNS"),
    ("date,amount,amount_cents,direction,currency", "AMBIGUOUS_COLUMNS"),
    (HEADER + "\na,2026-10-12,1,inflow,USD,extra", "ROW_WIDTH"),
    (HEADER + '\n"unterminated', "INVALID_CSV"),
    (HEADER + "\na,2026-10-12,1,inflow,JPY", "INVALID_CURRENCY"),
    (HEADER + "\na,2026-10-12,1,inflow,USD\nb,2026-10-12,1,inflow,EUR", "MIXED_CURRENCY"),
    (HEADER + "\na,2026-10-12,1,inflow,USD\na,2026-10-12,2,inflow,USD", "INVALID_TRANSACTION"),
    (HEADER + "\n,2026-10-12,1,inflow,USD", "INVALID_TRANSACTION"),
    (HEADER + "\na,2026-10-12,1,mystery,USD", "INVALID_TRANSACTION"),
    (HEADER + "\na,2026-10-12,1,inflow,USD\x00", "INVALID_FILE"),
    (b"\xff", "ENCODING"),
])
def test_invalid_files_are_rejected(source, code):
    with pytest.raises(IngestionError) as error:
        ingest_csv(source)
    assert any(issue.code == code for issue in error.value.issues)


@pytest.mark.parametrize("value", ["", "-1", "1.5", "1e2", "NaN", "inf", "$2", "true"])
def test_invalid_cents(value):
    with pytest.raises(IngestionError):
        ingest_csv(HEADER + f"\na,2026-10-12,{value},inflow,USD")


@pytest.mark.parametrize("value", ["10/12/2026", "2026-02-30", "20261012", "2026-10-12T12:00:00Z", ""])
def test_invalid_dates(value):
    with pytest.raises(IngestionError) as error:
        ingest_csv(HEADER + f"\na,{value},100,inflow,USD")
    assert error.value.issues[0].row == 2


@pytest.mark.parametrize("value", ["1.001", "-1.00", "1e3", "", "NaN", "1,000.00"])
def test_invalid_decimal_amounts(value):
    with pytest.raises(IngestionError):
        ingest_csv(f'date,amount,direction,currency\n2026-10-12,"{value}",income,USD')


def test_large_amount_is_exact_and_not_removed_as_outlier():
    result = ingest_csv("date,amount,direction,currency\n2026-10-12,123456789012345678901234567890.12,income,USD")
    assert result.transactions[0].amount_cents == 12345678901234567890123456789012


def test_explicit_currency_and_generated_ids():
    source = "date,amount_cents,direction\n2026-10-12,100,inflow"
    first = ingest_csv(source, currency=" usd ")
    assert first.currency == "USD"
    assert first == ingest_csv(source, currency="USD")
    assert first.transactions[0].transaction_id.startswith("csv_")
    assert any(issue.code == "GENERATED_IDS" for issue in first.warnings)
    with pytest.raises(IngestionError):
        ingest_csv(source, currency="ZZZ")
    with pytest.raises(IngestionError):
        ingest_csv(HEADER + "\na,2026-10-12,1,inflow,USD", currency="EUR")


def test_matching_explicit_duplicates_count_once():
    row = "a,2026-10-12,100,inflow,USD"
    result = ingest_csv(HEADER + f"\n{row}\n{row}\n")
    assert result.source_row_count == 2
    assert result.duplicate_row_count == 1
    assert aggregate_daily(result).days[0].inflow_cents == 100
    assert any(issue.code == "DUPLICATE" and issue.row == 3 for issue in result.warnings)


def test_identical_without_ids_are_ambiguous_but_distinct_ids_are_valid():
    row = "2026-10-12,100,inflow,USD"
    with pytest.raises(IngestionError, match="ambiguous"):
        ingest_csv("date,amount_cents,direction,currency\n" + row + "\n" + row)
    result = ingest_csv(HEADER + "\na," + row + "\nb," + row)
    assert aggregate_daily(result).days[0].inflow_cents == 200


def test_duplicate_covariate_conflict_is_rejected():
    with pytest.raises(IngestionError, match="conflicting"):
        ingest_csv(HEADER + ",orders\na,2026-10-12,100,inflow,USD,2\na,2026-10-12,100,inflow,USD,3")


def test_import_rejects_all_when_any_row_invalid_and_reports_all_errors():
    with pytest.raises(IngestionError) as error:
        ingest_csv(HEADER + "\na,2026-10-12,100,inflow,USD\nb,invalid,100,inflow,USD\nc,2026-10-12,,outflow,USD")
    assert [issue.row for issue in error.value.issues] == [3, 4]


def test_unsettled_records_retained_but_excluded_from_actual_cash():
    result = ingest_csv(HEADER + ",payment_status\na,2026-10-12,100,inflow,USD,paid\nb,2026-10-13,200,inflow,USD,pending\nc,2026-10-12,300,outflow,USD,failed\nd,2026-10-12,400,outflow,USD,cancelled")
    assert len(result.transactions) == 4
    history = aggregate_daily(result)
    assert len(history.days) == 1
    assert history.days[0].inflow_cents == 100
    assert history.days[0].outflow_cents == 0
    assert history.days[0].evidence_ids == ("a",)
    assert sum(issue.code == "NOT_SETTLED" for issue in result.warnings) == 3


@pytest.mark.parametrize("status", ["", "unknown"])
def test_missing_or_unknown_supplied_status_is_rejected(status):
    with pytest.raises(IngestionError):
        ingest_csv(HEADER + f",payment_status\na,2026-10-12,100,inflow,USD,{status}")


def test_daily_aggregation_and_confirmed_coverage():
    result = ingest_csv(HEADER + "\na,2026-10-10,100,inflow,USD\nb,2026-10-12,30,outflow,USD\nc,2026-10-10,40,inflow,USD\n\n")
    observed = aggregate_daily(result)
    assert len(observed.days) == 2
    assert observed.days[0].inflow_cents == 140
    assert observed.days[0].evidence_ids == ("a", "c")
    assert not observed.complete_coverage
    assert observed.warnings
    complete = aggregate_daily(result, coverage_start=date(2026, 10, 10), coverage_end=date(2026, 10, 12), complete_coverage=True)
    assert len(complete.days) == 3
    assert complete.days[1].inflow_cents == complete.days[1].outflow_cents == 0
    assert complete.complete_coverage
    assert any(issue.code == "BLANK_ROW" for issue in result.warnings)


@pytest.mark.parametrize("kwargs", [
    {"complete_coverage": True},
    {"coverage_start": date(2026, 10, 10)},
    {"coverage_start": date(2026, 10, 10), "coverage_end": date(2026, 10, 12)},
    {"coverage_start": date(2026, 10, 12), "coverage_end": date(2026, 10, 10), "complete_coverage": True},
    {"coverage_start": date(2026, 10, 11), "coverage_end": date(2026, 10, 12), "complete_coverage": True},
])
def test_invalid_coverage(kwargs):
    data = ingest_csv(HEADER + "\na,2026-10-10,100,inflow,USD")
    with pytest.raises(ValueError):
        aggregate_daily(data, **kwargs)


def test_all_pending_history_is_empty_unless_complete_coverage_confirmed():
    data = ingest_csv(HEADER + ",status\na,2026-10-10,100,inflow,USD,pending")
    assert aggregate_daily(data).days == ()
    history = aggregate_daily(data, coverage_start=date(2026, 10, 10),
                              coverage_end=date(2026, 10, 11), complete_coverage=True)
    assert len(history.days) == 2
    assert all(day.inflow_cents == day.outflow_cents == 0 for day in history.days)


def test_explicit_currency_does_not_impute_blank_currency_cells():
    with pytest.raises(IngestionError):
        ingest_csv(HEADER + "\na,2026-10-10,100,inflow,", currency="USD")


def test_aggregation_guards_manual_duplicate_and_mixed_currency_records():
    data = ingest_csv(HEADER + "\na,2026-10-10,100,inflow,USD")
    transaction = data.transactions[0]
    duplicate = data.model_copy(update={"transactions": (transaction, transaction)})
    with pytest.raises(ValueError, match="duplicate"):
        aggregate_daily(duplicate)
    mixed = data.model_copy(update={"transactions": (transaction.model_copy(update={"currency": "EUR"}),)})
    with pytest.raises(ValueError, match="currency"):
        aggregate_daily(mixed)
