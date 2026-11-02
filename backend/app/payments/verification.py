"""The only service that can mint a paid-state write after a fresh PayPal GET."""

from dataclasses import asdict
import json
from threading import Lock
import time
from types import MappingProxyType
from weakref import WeakKeyDictionary

from ..ledger.errors import IllegalTransition
from ..ledger.models import State
from ..ledger.state_machine import Origin, TRANSITIONS, validate_transition
from ..ledger.store import _digest
from .errors import MalformedResponse, RecoveryRequired

STATUS_MAP = MappingProxyType({
    "DRAFT": State.INVOICE_DRAFTED,
    "SENT": State.INVOICE_SENT, "UNPAID": State.INVOICE_SENT, "SCHEDULED": State.INVOICE_SENT,
    "PAYMENT_PENDING": State.PAYMENT_PENDING, "PARTIALLY_PAID": State.PARTIALLY_PAID,
    "PAID": State.VERIFIED_PAID, "MARKED_AS_PAID": State.OFFLINE_MARKED_PAID,
    "CANCELLED": State.CANCELLED,
    "REFUNDED": State.REFUNDED, "PARTIALLY_REFUNDED": State.REFUNDED, "MARKED_AS_REFUNDED": State.REFUNDED,
})
_SEAL = object()
_OBSERVATIONS = WeakKeyDictionary()
_OBSERVATION_LOCK = Lock()


class _Observation:
    __slots__ = ("__weakref__",)

    def __init__(self, seal):
        if seal is not _SEAL:
            raise IllegalTransition("Provider evidence cannot be supplied by a caller.")


def _consume_observation(proof):
    with _OBSERVATION_LOCK:
        if type(proof) is not _Observation or proof not in _OBSERVATIONS:
            raise IllegalTransition("A fresh single-use provider observation is required.")
        data, fetched_at = _OBSERVATIONS.pop(proof)
    if not 0 <= time.monotonic() - fetched_at <= 30:
        raise IllegalTransition("Provider observation expired; fetch again.")
    return data


def map_status(status):
    return STATUS_MAP.get(status, State.UNRESOLVED) if type(status) is str else State.UNRESOLVED


def _outcome(details, status, entry, history):
    if details.get("malformed"):
        return State.UNRESOLVED, "MALFORMED_PROVIDER_RESPONSE"
    creation = next(e for e in history if e.reason in {"INVOICE_CREATED", "INVOICE_RECOVERED"})
    original = json.loads(creation.details_json)
    if (details["invoice_id"] != creation.provider_invoice_id or details["currency"] != entry.currency
            or details["total_cents"] != entry.amount_cents or details["reference"] != entry.entry_id
            or details["invoice_number"] != original["invoice_number"]
            or details["recipient_fingerprint"] != original["recipient_fingerprint"]):
        return State.UNRESOLVED, "APPROVED_INVOICE_MISMATCH"
    target = map_status(status)
    if target == State.VERIFIED_PAID:
        if (details["paid_cents"] != entry.amount_cents or details["paypal_paid_cents"] != entry.amount_cents
                or details["due_cents"] != 0 or details["refund_cents"] != 0 or not details["transaction_ids"]):
            return State.UNRESOLVED, "PAYPAL_PAYMENT_EVIDENCE_MISMATCH"
        if any(e.to_state in {State.REFUNDED, State.CANCELLED, State.FAILED} for e in history):
            return State.UNRESOLVED, "TERMINAL_PAYMENT_REVIEW_REQUIRED"
    if target == State.PARTIALLY_PAID:
        if (not 0 < details["paypal_paid_cents"] < entry.amount_cents
                or details["paid_cents"] != details["paypal_paid_cents"] or not details["transaction_ids"]
                or details["due_cents"] != entry.amount_cents - details["paid_cents"] or details["refund_cents"] != 0):
            return State.UNRESOLVED, "PARTIAL_PAYMENT_EVIDENCE_MISMATCH"
    if target == State.REFUNDED and not any(e.to_state == State.VERIFIED_PAID for e in history):
        return State.UNRESOLVED, "NO_VERIFIED_PAYMENT_TO_REFUND"
    previous = history[-1].to_state
    if target != previous and target not in TRANSITIONS[previous]:
        return State.UNRESOLVED, "PROVIDER_STATE_REGRESSION"
    return target, "PROVIDER_OBSERVED" if target != State.UNRESOLVED else "UNKNOWN_PROVIDER_STATUS"


def validate_recorded_observation(event, entry, history):
    """Recheck financial invariants during every database integrity scan."""
    details = json.loads(event.details_json)
    if event.actor != "verification_service" or not any(e.reason in {"INVOICE_CREATED", "INVOICE_RECOVERED"} for e in history):
        raise ValueError
    if details.get("malformed") is True:
        if set(details) != {"malformed", "outcome_reason"} or event.provider_status is not None:
            raise ValueError
    else:
        expected_fields = {"invoice_id", "currency", "total_cents", "paid_cents", "paypal_paid_cents",
                           "due_cents", "refund_cents", "invoice_number", "reference", "invoice_url",
                           "transaction_ids", "recipient_fingerprint", "outcome_reason"}
        if set(details) != expected_fields:
            raise ValueError
        for key in ("total_cents", "paid_cents", "paypal_paid_cents", "refund_cents"):
            if type(details[key]) is not int or details[key] < 0:
                raise ValueError
        if details["due_cents"] is not None and (type(details["due_cents"]) is not int or details["due_cents"] < 0):
            raise ValueError
        ids = details["transaction_ids"]
        if type(ids) is not list or len(ids) != len(set(ids)):
            raise ValueError
    target, reason = _outcome(details, event.provider_status, entry, history)
    creation = next(e for e in history if e.reason in {"INVOICE_CREATED", "INVOICE_RECOVERED"})
    if (event.to_state != target or details["outcome_reason"] != reason
            or event.provider_invoice_id != creation.provider_invoice_id):
        raise ValueError
    expected_paid = details["paypal_paid_cents"] if target in {State.VERIFIED_PAID, State.PARTIALLY_PAID} else None
    if event.paid_amount_cents != expected_paid:
        raise ValueError
    validate_transition(event.from_state, event.to_state, origin=Origin.VERIFICATION,
                        has_approval=True, provider_status=event.provider_status)


class VerificationService:
    def __init__(self, ledger, client):
        self.ledger, self.client = ledger, client

    def verify(self, entry_id):
        snapshot = self.ledger.get(entry_id)
        binding = self.ledger._store.invoice_binding(entry_id)
        if binding is None:
            raise IllegalTransition("A bound invoice is required for verification.")
        status = None
        try:
            invoice = self.client.get_invoice(binding["provider_invoice_id"])
            details = asdict(invoice)
            status = details.pop("status")
            details["transaction_ids"] = list(details["transaction_ids"])
        except MalformedResponse:
            details = {"malformed": True}
        # Network/auth/rate-limit failures propagate and write nothing.
        fetched_at = time.monotonic()
        target, reason = _outcome(details, status, snapshot.entry, snapshot.events)
        if (snapshot.state in {State.CANCELLED, State.FAILED, State.REFUNDED}
                and target != snapshot.state):
            # Keep terminal history intact. Unknown responses still map to
            # UNRESOLVED, but the existing transition policy requires review
            # instead of reopening a terminal recovery item.
            raise RecoveryRequired()
        details["outcome_reason"] = reason
        proof = _Observation(_SEAL)
        data = {"entry_id": entry_id, "expected_sequence": snapshot.sequence, "target": target,
                "details": details, "status": status, "invoice_id": binding["provider_invoice_id"],
                "paid_cents": details["paypal_paid_cents"] if target in {State.VERIFIED_PAID, State.PARTIALLY_PAID} else None,
                "key": "verify_" + _digest({"entry_id": entry_id, "sequence": snapshot.sequence, "details": details, "status": status})}
        with _OBSERVATION_LOCK:
            _OBSERVATIONS[proof] = (data, fetched_at)
        self.ledger._store._commit_verification(proof)
        return self.ledger.get(entry_id)
