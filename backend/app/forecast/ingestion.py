"""Strict, reproducible CSV ingestion and aggregation of settled transactions."""

import csv
import hashlib
import io
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated

from pydantic import Field, StrictInt, TypeAdapter, ValidationError

from .schemas import Currency, DailyCash, DailyHistory, IngestionResult, RowIssue, Transaction


ALIASES = {
    "date": {"date", "transaction_date", "posted_date"},
    "transaction_id": {"transaction_id", "id", "txn_id"},
    "amount_cents": {"amount_cents", "cents"},
    "amount": {"amount", "transaction_amount"},
    "direction": {"direction", "transaction_type", "type"},
    "currency": {"currency", "currency_code"},
    "category": {"category"},
    "description": {"description", "memo"},
    "payment_status": {"payment_status", "status"},
}
DIRECTIONS = {
    "inflow": "inflow", "income": "inflow", "receipt": "inflow", "credit": "inflow",
    "outflow": "outflow", "expense": "outflow", "payment": "outflow", "debit": "outflow",
}
STATUSES = {
    "settled": "settled", "paid": "settled", "completed": "settled", "received": "settled",
    "pending": "pending", "unverified": "pending", "pending_verification": "pending",
    "cancelled": "cancelled", "canceled": "cancelled", "failed": "failed",
}
CURRENCY_ADAPTER = TypeAdapter(Currency)
DEFAULT_MAX_BYTES = 5 * 1024 * 1024


class IngestionError(ValueError):
    """The entire import is rejected; issues use CSV record numbers, including header."""

    def __init__(self, issues: list[RowIssue]):
        self.issues = tuple(issues)
        super().__init__("; ".join(f"row {item.row}: {item.message}" for item in issues))


def _fail(code: str, message: str) -> None:
    raise IngestionError([RowIssue(row=None, code=code, message=message)])


def _iso_date(value: str) -> date:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("date must use YYYY-MM-DD; ambiguous dates are not inferred")
    return date.fromisoformat(value)


def _amount(value: str, *, cents: bool) -> int:
    pattern = r"\d+" if cents else r"\d+(?:\.\d{1,2})?"
    if not re.fullmatch(pattern, value):
        raise ValueError("amount must be nonnegative integer cents or a decimal with at most two places")
    if cents:
        return int(value)
    # Parsing the digit groups avoids floating-point or Decimal context rounding.
    whole, _, fraction = value.partition(".")
    return int(whole) * 100 + int(fraction.ljust(2, "0") or "0")


def read_csv(path: str | Path, *, currency: str | None = None, max_bytes: int = DEFAULT_MAX_BYTES) -> IngestionResult:
    """Read a source file without modifying it. An explicit currency can fill a missing column."""
    max_bytes = TypeAdapter(Annotated[StrictInt, Field(ge=1)]).validate_python(max_bytes)
    with Path(path).open("rb") as source:
        raw = source.read(max_bytes + 1)
    return ingest_csv(raw, currency=currency, max_bytes=max_bytes)


def ingest_csv(source: bytes | str, *, currency: str | None = None, max_bytes: int = DEFAULT_MAX_BYTES) -> IngestionResult:
    """Reject imports containing invalid rows; deduplicate only explicit, matching IDs."""
    max_bytes = TypeAdapter(Annotated[StrictInt, Field(ge=1)]).validate_python(max_bytes)
    if not isinstance(source, (bytes, str)):
        _fail("INVALID_FILE", "CSV input must be bytes or text")
    raw = source.encode("utf-8") if isinstance(source, str) else source
    if len(raw) > max_bytes:
        _fail("FILE_TOO_LARGE", f"CSV exceeds the configured {max_bytes}-byte limit")
    source_hash = hashlib.sha256(raw).hexdigest()
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        _fail("ENCODING", "CSV must be UTF-8")
    if not content.strip():
        _fail("EMPTY_FILE", "CSV is empty")
    if "\x00" in content:
        _fail("INVALID_FILE", "CSV contains null bytes")
    try:
        records = list(csv.reader(io.StringIO(content, newline=""), strict=True))
    except csv.Error as exc:
        _fail("INVALID_CSV", str(exc))
    headers = records[0]
    normalized = [header.strip().lower().replace(" ", "_") for header in headers]
    if any(not name for name in normalized) or len(set(normalized)) != len(normalized):
        _fail("INVALID_HEADERS", "headers must be nonblank and unique after normalization")
    columns: dict[str, int] = {}
    for canonical, aliases in ALIASES.items():
        matches = [i for i, name in enumerate(normalized) if name in aliases]
        if len(matches) > 1:
            _fail("AMBIGUOUS_COLUMNS", f"multiple columns represent {canonical}")
        if matches:
            columns[canonical] = matches[0]
    if "amount" in columns and "amount_cents" in columns:
        _fail("AMBIGUOUS_COLUMNS", "provide amount or amount_cents, not both")
    missing = {"date", "direction"} - columns.keys()
    if not ({"amount", "amount_cents"} & columns.keys()):
        missing.add("amount_cents or amount")
    if "currency" not in columns and currency is None:
        missing.add("currency (or explicit currency argument)")
    if missing:
        _fail("MISSING_COLUMNS", "missing required columns: " + ", ".join(sorted(missing)))
    expected_currency = None
    if currency is not None:
        try:
            expected_currency = CURRENCY_ADAPTER.validate_python(currency.strip().upper())
        except ValidationError:
            _fail("INVALID_CURRENCY", "unsupported explicit currency")
    issues: list[RowIssue] = []
    warnings: list[RowIssue] = []
    transactions: list[Transaction] = []
    seen_ids: dict[str, dict] = {}
    unidentified: set[tuple] = set()
    duplicates = 0
    row_count = 0
    if "payment_status" not in columns:
        warnings.append(RowIssue(row=None, code="STATUS_ASSUMED", message="Historical export is assumed to contain settled transactions; this is not provider verification."))
    if "transaction_id" not in columns:
        warnings.append(RowIssue(row=None, code="GENERATED_IDS", message="IDs are source-hash and row based; they are not stable across changed exports."))
    for row_number, values in enumerate(records[1:], start=2):
        if not values or all(not value.strip() for value in values):
            warnings.append(RowIssue(row=row_number, code="BLANK_ROW", message="Blank record skipped."))
            continue
        row_count += 1
        if len(values) != len(headers):
            issues.append(RowIssue(row=row_number, code="ROW_WIDTH", message="Column count does not match header."))
            continue
        fields = {name: values[index].strip() for name, index in columns.items()}
        try:
            row_currency = CURRENCY_ADAPTER.validate_python(fields.get("currency", expected_currency).upper())
        except ValidationError:
            issues.append(RowIssue(row=row_number, code="INVALID_CURRENCY", message="Missing or unsupported currency."))
            continue
        if expected_currency is None:
            expected_currency = row_currency
        if row_currency != expected_currency:
            issues.append(RowIssue(row=row_number, code="MIXED_CURRENCY", message="All rows must have the same currency."))
            continue
        try:
            direction = DIRECTIONS.get(fields["direction"].lower())
            status = STATUSES.get(fields["payment_status"].lower()) if "payment_status" in columns else "settled"
            if direction is None:
                raise ValueError("unknown transaction direction")
            if status is None:
                raise ValueError("missing or unknown payment_status")
            explicit_id = fields.get("transaction_id")
            if "transaction_id" in columns and not explicit_id:
                raise ValueError("transaction_id must not be missing when its column is supplied")
            parsed = {
                "date": _iso_date(fields["date"]),
                "amount_cents": _amount(fields.get("amount_cents", fields.get("amount", "")), cents="amount_cents" in columns),
                "direction": direction, "currency": row_currency,
                "category": fields.get("category") or None,
                "description": fields.get("description") or None, "payment_status": status,
            }
            # Keep optional covariates and original values when comparing duplicates.
            extra = tuple((headers[i], values[i].strip()) for i in range(len(headers)) if i not in columns.values())
            signature = {**parsed, "extra": extra}
            if explicit_id:
                if explicit_id in seen_ids:
                    if seen_ids[explicit_id] != signature:
                        raise ValueError("conflicting duplicate transaction_id")
                    duplicates += 1
                    warnings.append(RowIssue(row=row_number, code="DUPLICATE", message=f"Matching duplicate ID {explicit_id} skipped."))
                    continue
                seen_ids[explicit_id] = signature
            else:
                fingerprint = tuple(parsed.values()) + (extra,)
                if fingerprint in unidentified:
                    raise ValueError("identical rows without transaction IDs are ambiguous; supply distinct IDs or remove duplicate")
                unidentified.add(fingerprint)
            transactions.append(Transaction(
                **parsed, transaction_id=explicit_id or f"csv_{source_hash}_{row_number}",
                source_row=row_number, source_fields=dict(zip(headers, values)),
            ))
            if status != "settled":
                warnings.append(RowIssue(row=row_number, code="NOT_SETTLED", message="Record retained but excluded from actual daily cash totals."))
        except (ValueError, ValidationError) as exc:
            issues.append(RowIssue(row=row_number, code="INVALID_TRANSACTION", message=str(exc)))
    if issues:
        raise IngestionError(issues)
    if not transactions:
        _fail("NO_TRANSACTIONS", "CSV contains no transactions")
    return IngestionResult(
        source_sha256=source_hash, currency=expected_currency,
        transactions=tuple(sorted(transactions, key=lambda item: (item.date, item.transaction_id))),
        warnings=tuple(warnings), source_row_count=row_count, duplicate_row_count=duplicates,
    )


def aggregate_daily(
    data: IngestionResult, *, coverage_start: date | None = None,
    coverage_end: date | None = None, complete_coverage: bool = False,
) -> DailyHistory:
    """Zero-fill only a caller-confirmed complete export, never inferred missing days."""
    if type(complete_coverage) is not bool:
        raise ValueError("complete_coverage must be a boolean")
    if any(value is not None and type(value) is not date for value in (coverage_start, coverage_end)):
        raise ValueError("coverage bounds must be dates without time")
    if complete_coverage != (coverage_start is not None and coverage_end is not None):
        raise ValueError("complete coverage requires both dates; dates require explicit complete_coverage=True")
    if not complete_coverage and (coverage_start is not None or coverage_end is not None):
        raise ValueError("coverage dates must be supplied together")
    if complete_coverage and coverage_start > coverage_end:
        raise ValueError("coverage_start must be on or before coverage_end")
    totals: dict[date, dict] = {}
    seen: set[str] = set()
    for transaction in data.transactions:
        if transaction.transaction_id in seen:
            raise ValueError("duplicate transaction_id in ingestion result")
        seen.add(transaction.transaction_id)
        if transaction.currency != data.currency:
            raise ValueError("transaction currency does not match import")
        if complete_coverage and not coverage_start <= transaction.date <= coverage_end:
            raise ValueError("transaction lies outside declared coverage")
        if transaction.payment_status != "settled":
            continue
        bucket = totals.setdefault(transaction.date, {"inflow_cents": 0, "outflow_cents": 0, "evidence_ids": []})
        bucket[f"{transaction.direction}_cents"] += transaction.amount_cents
        bucket["evidence_ids"].append(transaction.transaction_id)
    if complete_coverage:
        current = coverage_start
        while current <= coverage_end:
            totals.setdefault(current, {"inflow_cents": 0, "outflow_cents": 0, "evidence_ids": []})
            if current == coverage_end:
                break
            current += timedelta(days=1)
    return DailyHistory(
        currency=data.currency,
        days=tuple(DailyCash(date=day, currency=data.currency, **totals[day]) for day in sorted(totals)),
        coverage_start=coverage_start, coverage_end=coverage_end, complete_coverage=complete_coverage,
        warnings=() if complete_coverage else ("Only observed settled transaction dates are included; missing days are unknown.",),
    )
