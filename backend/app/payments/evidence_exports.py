"""Read-only adapters to the existing forecast and rescue input schemas.

These functions accept a trusted LedgerService, never caller-supplied snapshots
or payment statuses. They export the last stored observation, not a fresh PayPal
check or proof of bank settlement. Authentication belongs to the shared server.
"""
from datetime import date
import json

from ..ledger.models import State, require_identifier
from .errors import InvalidRequest, PaymentError


class EvidenceUnavailable(PaymentError):
    code = "PAYMENT_EVIDENCE_UNAVAILABLE"
    message = "Ledger evidence cannot be represented safely in this analysis."


_FORECAST_STATUSES = {
    State.INVOICE_SENT: "invoice_unpaid",
    State.PAYMENT_PENDING: "pending_verification",
    State.VERIFIED_PAID: "verified_completed",
    State.CANCELLED: "cancelled",
    State.FAILED: "failed",
}
_RESCUE_STATUSES = {
    State.INVOICE_SENT: "unpaid",
    State.PAYMENT_PENDING: "pending",
    State.VERIFIED_PAID: "paid",
}


def _calendar_date(value, *, required=False):
    if value is None and not required:
        return None
    # Reject datetime, timestamps and implicit coercion. Output is ISO calendar date.
    if type(value) is not date:
        raise InvalidRequest()
    return value.isoformat()


def _text(value):
    if value is None:
        return None
    if (type(value) is not str or not value.strip() or len(value) > 500
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise InvalidRequest()
    return value.strip()


def _evidence(ledger, entry_id, statuses):
    snapshot = ledger.get(entry_id)  # Integrity-checked, consistent history.
    if snapshot.state not in statuses:
        # No forced mapping of partial/offline/refunded/unresolved/proposed states.
        raise EvidenceUnavailable()
    latest = snapshot.events[-1]
    if snapshot.state in {State.INVOICE_SENT, State.PAYMENT_PENDING}:
        # A send acknowledgement alone says nothing about the outstanding balance.
        # Only an observed, wholly unpaid invoice fits the peers' current schemas.
        if latest.reason != "PAYPAL_VERIFIED":
            raise EvidenceUnavailable()
        details = json.loads(latest.details_json)
        if (details.get("paid_cents") != 0 or details.get("paypal_paid_cents") != 0
                or details.get("refund_cents") != 0
                or details.get("due_cents") != snapshot.entry.amount_cents):
            raise EvidenceUnavailable()
    return snapshot


def forecast_event(ledger, entry_id, *, expected_date=None, due_date=None,
                   projection_assumption=None, category=None,
                   historical_transaction_id=None):
    """Return Member 1's ScheduledCashEvent fields, with no forecast or DB writes.

    Dates/category/history linkage must come from authorized server records.
    No expected collection date is inferred from a due date. Missing timing or
    assumption stays null so the forecast engine excludes the unresolved event.
    """
    expected = _calendar_date(expected_date)
    due = _calendar_date(due_date)
    assumption = _text(projection_assumption)
    if category is not None:
        require_identifier(category)
    if historical_transaction_id is not None:
        require_identifier(historical_transaction_id)
    snapshot = _evidence(ledger, entry_id, _FORECAST_STATUSES)
    latest = snapshot.events[-1]
    return {
        "event_id": snapshot.entry.entry_id,
        "source_id": snapshot.entry.entry_id,
        "direction": "inflow",
        "amount_cents": snapshot.entry.amount_cents,
        "currency": snapshot.entry.currency,
        "status": _FORECAST_STATUSES[snapshot.state],
        "category": category,
        "expected_date": expected,
        "due_date": due,
        "projection_assumption": assumption,
        "historical_transaction_id": historical_transaction_id,
        "verification_evidence_id": latest.event_id if snapshot.state == State.VERIFIED_PAID else None,
    }


def rescue_invoice(ledger, entry_id, *, due_date):
    """Return Member 2's InvoiceEvidence fields; never invent a missing due date.

    The stable ledger entry ID is used for citations, not a recipient's identity.
    The ledger has no due-date field; obtain it from trusted invoice records.
    """
    due = _calendar_date(due_date, required=True)
    snapshot = _evidence(ledger, entry_id, _RESCUE_STATUSES)
    return {
        "invoice_id": snapshot.entry.entry_id,
        "currency": snapshot.entry.currency,
        "outstanding_amount_cents": 0 if snapshot.state == State.VERIFIED_PAID else snapshot.entry.amount_cents,
        "due_date": due,
        "status": _RESCUE_STATUSES[snapshot.state],
    }
