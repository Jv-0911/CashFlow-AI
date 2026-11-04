"""Member 3 implementation serializers; these do not create HTTP routes."""

import json

from ..ledger import errors as ledger_errors
from ..ledger.models import State, require_identifier
from ..ledger.service import _verified_recovered_cash
from .errors import PaymentError


def entry_view(snapshot):
    latest = snapshot.events[-1]
    invoice_url = next((json.loads(event.details_json).get("invoice_url") for event in reversed(snapshot.events)
                        if json.loads(event.details_json).get("invoice_url")), None)
    return {"entry_id": snapshot.entry.entry_id, "amount_cents": snapshot.entry.amount_cents,
            "currency": snapshot.entry.currency, "provider": snapshot.entry.provider,
            "status": snapshot.state.value, "provider_status": latest.provider_status,
            "provider_invoice_id": latest.provider_invoice_id, "invoice_url": invoice_url,
            "paid_amount_cents": latest.paid_amount_cents or 0, "sequence": snapshot.sequence,
            "created_at": snapshot.entry.created_at, "updated_at": latest.occurred_at,
            "verified_at": latest.occurred_at if snapshot.state == State.VERIFIED_PAID else None}


def ledger_view(ledger, *, is_demo_data=False):
    snapshots = ledger.list_entries()  # One consistent, integrity-checked read.
    totals = _verified_recovered_cash(snapshots)
    return {"is_demo_data": is_demo_data, "entries": [entry_view(snapshot) for snapshot in snapshots],
            "recovered_cash": [{"amount_cents": amount, "currency": currency} for currency, amount in sorted(totals.items())]}


def error_view(error, request_id):
    require_identifier(request_id)
    if isinstance(error, PaymentError):
        code, message = error.code, error.message
    else:
        code, message = {
            ledger_errors.IdempotencyConflict: ("PAYMENT_IDEMPOTENCY_CONFLICT", "The request key was used with different input."),
            ledger_errors.SequenceConflict: ("LEDGER_SEQUENCE_CONFLICT", "Read the latest entry before retrying."),
            ledger_errors.IllegalTransition: ("PAYMENT_TRANSITION_INVALID", "This operation is not allowed in the current state."),
            ledger_errors.InvalidInput: ("PAYMENT_REQUEST_INVALID", "Payment request is invalid."),
            ledger_errors.EntryNotFound: ("LEDGER_ENTRY_NOT_FOUND", "Ledger entry does not exist."),
            ledger_errors.IntegrityViolation: ("LEDGER_INTEGRITY_FAILED", "Ledger integrity check failed."),
        }.get(type(error), ("PAYMENT_STATUS_UNAVAILABLE", "Payment status could not be verified."))
    return {"error": {"code": code, "message": message, "request_id": request_id}}
