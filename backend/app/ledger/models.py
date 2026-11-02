"""Immutable domain records. There is deliberately no payer personal data."""

from dataclasses import dataclass
from enum import StrEnum
import re

from .errors import InvalidInput


class State(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    INVOICE_DRAFTED = "INVOICE_DRAFTED"
    INVOICE_SENT = "INVOICE_SENT"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    AWAITING_VERIFICATION = "AWAITING_VERIFICATION"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    VERIFIED_PAID = "VERIFIED_PAID"
    OFFLINE_MARKED_PAID = "OFFLINE_MARKED_PAID"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    UNRESOLVED = "UNRESOLVED"
    REFUNDED = "REFUNDED"


def require_identifier(value: str) -> None:
    if type(value) is not str or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value) is None:
        raise InvalidInput("An opaque identifier is required.")


def require_amount(value: int) -> None:
    # bool is an int subclass, but is never valid money. SQLite uses signed int64.
    if type(value) is not int or not 0 < value <= 2**63 - 1:
        raise InvalidInput("Amount must be positive integer cents within storage limits.")


def require_currency(value: str) -> None:
    # USD is the deliberately restricted initial currency policy.
    if type(value) is not str or value != "USD":
        raise InvalidInput("Currency is not supported.")


def require_sequence(value: int) -> None:
    if type(value) is not int or value < 1:
        raise InvalidInput("Expected sequence must be a positive integer.")


def require_approver(value: str) -> None:
    require_identifier(value)
    if value.lower() in {"system", "verification_service", "webhook", "ai", "anonymous"}:
        raise InvalidInput("An authenticated human principal reference is required.")


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    entry_id: str
    correlation_key: str
    amount_cents: int
    currency: str
    provider: str
    created_at: str


@dataclass(frozen=True, slots=True)
class LedgerEvent:
    event_id: str
    entry_id: str
    seq: int
    global_seq: int
    from_state: State | None
    to_state: State
    provider_status: str | None
    provider_invoice_id: str | None
    paid_amount_cents: int | None
    actor: str
    reason: str
    occurred_at: str
    idempotency_key: str
    request_hash: str
    entry_hash: str
    prev_hash: str
    global_prev_hash: str
    event_hash: str
    details_json: str = "{}"


@dataclass(frozen=True, slots=True)
class LedgerSnapshot:
    entry: LedgerEntry
    events: tuple[LedgerEvent, ...]

    @property
    def state(self) -> State:
        return self.events[-1].to_state

    @property
    def sequence(self) -> int:
        return self.events[-1].seq


@dataclass(frozen=True, slots=True)
class IntegrityCheckpoint:
    """An optional trusted external checkpoint detects rollback/truncation."""

    global_seq: int
    event_hash: str
