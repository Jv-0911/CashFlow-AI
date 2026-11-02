"""Approved invoice creation/sending with durable at-most-once dispatch claims."""

import hashlib
import json

from ..ledger.errors import IllegalTransition, SequenceConflict
from ..ledger.models import State, require_identifier
from ..ledger.payment_events import approval_reference
from ..ledger.store import _digest
from .errors import ApprovalRequired, InvalidRequest, MalformedResponse, PaymentError, RecoveryRequired
from .money import cents_to_paypal, validate_money
from .schemas import recipient_fingerprint


def invoice_number(entry_id):
    return "CF" + hashlib.sha256(entry_id.encode("ascii")).hexdigest()[:23].upper()


class InvoiceService:
    def __init__(self, ledger, client, recipient_resolver):
        self.ledger, self.client = ledger, client
        # Server-owned reference lookup; do not bind this to client-supplied email.
        self._resolve_recipient = recipient_resolver

    def _approved(self, entry_id):
        snapshot = self.ledger.get(entry_id)
        reference = approval_reference(snapshot.events)
        if reference is None:
            raise ApprovalRequired()
        validate_money(snapshot.entry.amount_cents, snapshot.entry.currency,
                       maximum=self.client.config.max_invoice_cents)
        return snapshot, reference

    def create_draft(self, entry_id, *, idempotency_key):
        require_identifier(idempotency_key)
        snapshot, payload, fingerprint = self._prepare_create(entry_id)
        number = invoice_number(entry_id)
        operation = dict(kind="create", key=idempotency_key, payload_hash=_digest(payload), invoice_number=number)
        if self.ledger._store.operation_status(entry_id, **operation):
            binding = self.ledger._store.invoice_binding(entry_id)
            if binding:
                return self.ledger.get(entry_id)
            raise RecoveryRequired()
        dispatch = {}

        def before_dispatch():
            op, claimed = self.ledger._store._claim_operation(entry_id, **operation)
            if not claimed:
                raise RecoveryRequired()
            current = self.ledger.get(entry_id)
            if current.events[-1].event_id != op["event_id"]:
                raise SequenceConflict("Ledger changed before provider dispatch.")
            dispatch["sequence"] = current.sequence
            return op["request_id"]

        try:
            invoice = self.client.create_invoice(payload, before_dispatch=before_dispatch)
            if (invoice.status != "DRAFT" or invoice.reference != entry_id or invoice.invoice_number != number
                    or invoice.total_cents != snapshot.entry.amount_cents or invoice.currency != snapshot.entry.currency
                    or invoice.recipient_fingerprint != fingerprint):
                raise MalformedResponse()
        except PaymentError as error:
            if dispatch:
                self.ledger._store._operation_failure(entry_id, idempotency_key, error.code)
            raise
        self.ledger._store._complete_invoice(entry_id, idempotency_key, invoice, expected_sequence=dispatch["sequence"])
        return self.ledger.get(entry_id)

    def _prepare_create(self, entry_id):
        snapshot, payer_reference = self._approved(entry_id)
        try:
            email = self._resolve_recipient(payer_reference)
        except Exception:
            raise InvalidRequest() from None
        fingerprint = recipient_fingerprint(email)
        number = invoice_number(entry_id)
        payload = {
            "detail": {"invoice_number": number, "reference": entry_id, "currency_code": snapshot.entry.currency,
                       "payment_term": {"term_type": "DUE_ON_RECEIPT"}},
            "primary_recipients": [{"billing_info": {"email_address": email}}],
            "items": [{"name": "Approved recovery", "quantity": "1", "unit_amount": {
                "currency_code": snapshot.entry.currency,
                "value": cents_to_paypal(snapshot.entry.amount_cents, snapshot.entry.currency,
                                         maximum=self.client.config.max_invoice_cents)}}],
            "configuration": {"partial_payment": {"allow_partial_payment": False}, "allow_tip": False},
        }
        return snapshot, payload, fingerprint

    def send(self, entry_id, *, idempotency_key):
        require_identifier(idempotency_key)
        snapshot, _ = self._approved(entry_id)
        binding = self.ledger._store.invoice_binding(entry_id)
        if not binding:
            raise IllegalTransition("A bound draft invoice is required.")
        operation = dict(kind="send", key=idempotency_key,
                         payload_hash=_digest({"invoice_id": binding["provider_invoice_id"]}),
                         invoice_number=invoice_number(entry_id))
        if self.ledger._store.operation_status(entry_id, **operation):
            current = self.ledger.get(entry_id)
            if any(event.reason == "INVOICE_SEND_ACCEPTED" for event in current.events) or current.state in {
                State.INVOICE_SENT, State.PAYMENT_PENDING, State.PARTIALLY_PAID, State.VERIFIED_PAID,
                State.OFFLINE_MARKED_PAID, State.CANCELLED, State.REFUNDED}:
                return current
            raise RecoveryRequired()
        dispatch = {}

        def before_dispatch():
            op, claimed = self.ledger._store._claim_operation(entry_id, **operation)
            if not claimed:
                raise RecoveryRequired()
            current = self.ledger.get(entry_id)
            if current.events[-1].event_id != op["event_id"]:
                raise SequenceConflict("Ledger changed before provider dispatch.")
            dispatch["sequence"] = current.sequence
            return op["request_id"]

        created = next(event for event in snapshot.events if event.reason in {"INVOICE_CREATED", "INVOICE_RECOVERED"})
        original = json.loads(created.details_json)
        try:
            # Re-check draft identity/value/recipient after possible provider-side edits.
            invoice = self.client.get_invoice(binding["provider_invoice_id"])
            if (invoice.invoice_id != binding["provider_invoice_id"] or invoice.status != "DRAFT"
                    or invoice.total_cents != snapshot.entry.amount_cents or invoice.currency != snapshot.entry.currency
                    or invoice.reference != entry_id or invoice.invoice_number != original["invoice_number"]
                    or invoice.recipient_fingerprint != original["recipient_fingerprint"]):
                raise MalformedResponse()
            self.client.send_invoice(invoice.invoice_id, before_dispatch=before_dispatch)
        except PaymentError as error:
            if dispatch:
                self.ledger._store._operation_failure(entry_id, idempotency_key, error.code)
            raise
        self.ledger._store._complete_invoice(entry_id, idempotency_key, invoice,
                                            expected_sequence=dispatch["sequence"], sent=True)
        return self.ledger.get(entry_id)
