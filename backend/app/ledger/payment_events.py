"""Internal, narrowly scoped payment writes and their replay validation.

No public status setter exists. Paid-state writes require a one-use observation
minted by the fresh-fetch verification service. Trusted Python code and database
administrators are outside the hostile-request trust boundary.
"""

from dataclasses import asdict
import json
from uuid import uuid4

from .errors import IdempotencyConflict, IllegalTransition, SequenceConflict
from .models import LedgerEvent, State, require_identifier
from .state_machine import Origin, validate_transition

PAYMENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS payment_operations (
    operation_key TEXT PRIMARY KEY,
    entry_id TEXT NOT NULL REFERENCES ledger_entries(entry_id),
    kind TEXT NOT NULL CHECK (kind IN ('create', 'send')),
    payload_hash TEXT NOT NULL,
    request_id TEXT UNIQUE NOT NULL,
    invoice_number TEXT NOT NULL,
    event_id TEXT UNIQUE NOT NULL REFERENCES ledger_events(event_id),
    UNIQUE (entry_id, kind)
) STRICT;
CREATE TABLE IF NOT EXISTS processed_webhook_events (
    provider_event_id TEXT PRIMARY KEY,
    entry_id TEXT NOT NULL REFERENCES ledger_entries(entry_id),
    ledger_event_id TEXT NOT NULL REFERENCES ledger_events(event_id),
    seq INTEGER UNIQUE NOT NULL CHECK (seq > 0),
    received_at TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    event_hash TEXT UNIQUE NOT NULL
) STRICT;
"""
_VERIFIED_GATE = object()


def approval_reference(events):
    for event in events:
        if event.reason == "HUMAN_APPROVED":
            return json.loads(event.details_json).get("payer_reference")
    return None


def invoice_details(invoice):
    return {"invoice_number": invoice.invoice_number, "reference": invoice.reference,
            "currency": invoice.currency, "total_cents": invoice.total_cents,
            "invoice_url": invoice.invoice_url, "recipient_fingerprint": invoice.recipient_fingerprint}


class PaymentWrites:
    def _history(self, connection, entry_id):
        from .store import _event_from_row
        return tuple(_event_from_row(row) for row in connection.execute(
            "SELECT * FROM ledger_events WHERE entry_id = ? ORDER BY seq", (entry_id,)))

    def _append_payment_event(self, connection, entry, *, target, reason, details, key,
                              provider_status=None, provider_invoice_id=None,
                              paid_amount_cents=None, gate=None):
        from .store import _digest, _utcnow
        history = self._history(connection, entry.entry_id)
        previous = history[-1]
        verification = reason == "PAYPAL_VERIFIED"
        if verification and gate is not _VERIFIED_GATE:
            raise IllegalTransition("Fresh provider verification is required.")
        if target in {State.VERIFIED_PAID, State.PARTIALLY_PAID, State.REFUNDED} and gate is not _VERIFIED_GATE:
            raise IllegalTransition("Only verification can record payment outcomes.")
        if target != previous.to_state or verification:
            validate_transition(previous.to_state, target,
                                origin=Origin.VERIFICATION if verification else Origin.WORKFLOW,
                                has_approval=approval_reference(history) is not None,
                                provider_status=provider_status)
        elif reason != "INVOICE_RECOVERED":
            provider_status = previous.provider_status
            provider_invoice_id = previous.provider_invoice_id
            paid_amount_cents = previous.paid_amount_cents
        head = connection.execute("SELECT global_seq, event_hash FROM ledger_events ORDER BY global_seq DESC LIMIT 1").fetchone()
        data = dict(event_id="evt_" + uuid4().hex, entry_id=entry.entry_id,
                    seq=previous.seq + 1, global_seq=head["global_seq"] + 1,
                    from_state=previous.to_state, to_state=target, provider_status=provider_status,
                    provider_invoice_id=provider_invoice_id, paid_amount_cents=paid_amount_cents,
                    actor="verification_service" if verification else "system", reason=reason,
                    occurred_at=_utcnow(), idempotency_key=key, request_hash=_digest(details),
                    entry_hash=_digest(asdict(entry)), prev_hash=previous.event_hash,
                    global_prev_hash=head["event_hash"],
                    details_json=json.dumps(details, sort_keys=True, separators=(",", ":")))
        data["event_hash"] = _digest(data)
        event = LedgerEvent(**data)
        self._validate_payment_event(event, entry, history)
        columns = ",".join(data)
        connection.execute(f"INSERT INTO ledger_events ({columns}) VALUES ({','.join('?' for _ in data)})", tuple(data.values()))
        return event

    def _check_operation(self, connection, entry_id, *, kind, key, payload_hash, invoice_number):
        """Read-only eligibility check; the dispatch claim repeats it atomically."""
        from ..payments.errors import ApprovalRequired
        require_identifier(entry_id)
        require_identifier(key)
        existing = connection.execute("SELECT * FROM payment_operations WHERE operation_key = ? OR (entry_id = ? AND kind = ?)", (key, entry_id, kind)).fetchone()
        if existing:
            value = dict(existing)
            if (value["entry_id"] != entry_id or value["kind"] != kind or value["operation_key"] != key
                    or value["payload_hash"] != payload_hash or value["invoice_number"] != invoice_number):
                raise IdempotencyConflict("An invoice operation already exists with different input.")
            return value
        self._entry(connection, entry_id)
        history = self._history(connection, entry_id)
        if not approval_reference(history):
            raise ApprovalRequired()
        expected = State.APPROVED if kind == "create" else State.INVOICE_DRAFTED
        if kind not in {"create", "send"} or history[-1].to_state != expected:
            raise IllegalTransition("Invoice operation is not allowed in this state.")
        return None

    def operation_status(self, entry_id, *, kind, key, payload_hash, invoice_number):
        with self._transaction() as connection:
            return self._check_operation(connection, entry_id, kind=kind, key=key,
                                         payload_hash=payload_hash, invoice_number=invoice_number)

    def _claim_operation(self, entry_id, *, kind, key, payload_hash, invoice_number):
        from .store import _digest
        with self._transaction(write=True) as connection:
            existing = self._check_operation(connection, entry_id, kind=kind, key=key,
                                             payload_hash=payload_hash, invoice_number=invoice_number)
            if existing:
                return existing, False
            entry = self._entry(connection, entry_id)
            expected = State.APPROVED if kind == "create" else State.INVOICE_DRAFTED
            details = dict(operation_key=key, kind=kind, payload_hash=payload_hash,
                           request_id=str(uuid4()), invoice_number=invoice_number)
            event = self._append_payment_event(connection, entry, target=expected,
                       reason="OPERATION_REQUESTED", details=details,
                       key="operation_" + _digest({"key": key}))
            record = details | {"entry_id": entry_id, "event_id": event.event_id}
            connection.execute("INSERT INTO payment_operations (operation_key, entry_id, kind, payload_hash, request_id, invoice_number, event_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                               tuple(record[name] for name in ("operation_key", "entry_id", "kind", "payload_hash", "request_id", "invoice_number", "event_id")))
            return record, True

    def _operation_failure(self, entry_id, operation_key, code):
        from .store import _digest
        with self._transaction(write=True) as connection:
            entry = self._entry(connection, entry_id)
            details = {"operation_key": operation_key, "error_code": code}
            key = "failure_" + _digest(details)
            existing = self._existing(connection, key, _digest(details))
            if existing:
                return existing
            history = self._history(connection, entry_id)
            # Even definite errors do not reinterpret prior verified outcomes.
            if history[-1].to_state in {State.VERIFIED_PAID, State.PARTIALLY_PAID, State.REFUNDED}:
                return None
            target = State.FAILED if code == "PAYMENT_PROVIDER_REJECTED" and history[-1].to_state in {State.APPROVED, State.INVOICE_DRAFTED} else history[-1].to_state
            return self._append_payment_event(connection, entry, target=target,
                       reason="OPERATION_ERROR", details=details, key=key)

    def _complete_invoice(self, entry_id, operation_key, invoice, *, expected_sequence, sent=False, recovered=False):
        from .store import _digest
        with self._transaction(write=True) as connection:
            entry = self._entry(connection, entry_id)
            op = connection.execute("SELECT * FROM payment_operations WHERE operation_key = ? AND entry_id = ?", (operation_key, entry_id)).fetchone()
            if op is None or op["kind"] != ("send" if sent else "create"):
                raise IllegalTransition("Invoice operation does not exist.")
            details = invoice_details(invoice) | {"operation_key": operation_key}
            key = "result_" + _digest({"operation_key": operation_key})
            existing = self._existing(connection, key, _digest(details))
            if existing:
                return existing
            history = self._history(connection, entry_id)
            if history[-1].seq != expected_sequence:
                raise SequenceConflict("Ledger changed during the provider request.")
            if (invoice.total_cents != entry.amount_cents or invoice.currency != entry.currency
                    or invoice.reference != entry_id or invoice.invoice_number != op["invoice_number"]
                    or (not sent and not recovered and invoice.status != "DRAFT")):
                raise IllegalTransition("Provider invoice does not match the approved action.")
            if sent:
                binding = connection.execute("SELECT provider_invoice_id FROM invoice_bindings WHERE entry_id = ?", (entry_id,)).fetchone()
                if binding is None or binding[0] != invoice.invoice_id:
                    raise IllegalTransition("Provider invoice identity does not match.")
            event = self._append_payment_event(connection, entry,
                        target=history[-1].to_state if recovered else (State.INVOICE_SENT if sent else State.INVOICE_DRAFTED),
                        reason="INVOICE_RECOVERED" if recovered else ("INVOICE_SEND_ACCEPTED" if sent else "INVOICE_CREATED"), details=details, key=key,
                        provider_status=None if sent else invoice.status, provider_invoice_id=invoice.invoice_id)
            if not sent:
                connection.execute("INSERT INTO invoice_bindings VALUES (?, ?, ?)", (entry_id, invoice.invoice_id, event.event_id))
            return event

    def invoice_binding(self, entry_id):
        with self._transaction() as connection:
            row = connection.execute("SELECT * FROM invoice_bindings WHERE entry_id = ?", (entry_id,)).fetchone()
            return dict(row) if row else None

    def operations(self):
        with self._transaction() as connection:
            return tuple(dict(row) for row in connection.execute("SELECT * FROM payment_operations ORDER BY event_id"))

    def _claim_webhook(self, provider_event_id, provider_invoice_id):
        from .store import _digest, _utcnow, GENESIS_HASH
        require_identifier(provider_event_id)
        with self._transaction(write=True) as connection:
            if connection.execute("SELECT 1 FROM processed_webhook_events WHERE provider_event_id = ?", (provider_event_id,)).fetchone():
                return None, "duplicate"
            binding = connection.execute("SELECT entry_id FROM invoice_bindings WHERE provider_invoice_id = ?", (provider_invoice_id,)).fetchone()
            if binding is None:
                return None, "unknown_invoice"
            entry = self._entry(connection, binding[0])
            current = self._history(connection, entry.entry_id)[-1]
            head = connection.execute("SELECT seq, event_hash FROM processed_webhook_events ORDER BY seq DESC LIMIT 1").fetchone()
            details = {"provider_event_id": provider_event_id, "entry_id": entry.entry_id,
                       "ledger_event_id": current.event_id, "seq": head["seq"] + 1 if head else 1,
                       "received_at": _utcnow(), "prev_hash": head["event_hash"] if head else GENESIS_HASH}
            details["event_hash"] = _digest(details)
            connection.execute("INSERT INTO processed_webhook_events VALUES (?, ?, ?, ?, ?, ?, ?)", tuple(details.values()))
            return entry.entry_id, "claimed"

    def _commit_verification(self, proof):
        from ..payments.verification import _consume_observation
        with self._transaction(write=True) as connection:
            # Check age after acquiring the write lock and scanning integrity;
            # neither lock contention nor a large ledger may extend freshness.
            observation = _consume_observation(proof)
            entry = self._entry(connection, observation["entry_id"])
            history = self._history(connection, entry.entry_id)
            # Every caller still fetched fresh PayPal truth, but an unchanged
            # observation does not manufacture another financial event.
            last_observation = next((e for e in reversed(history) if e.reason == "PAYPAL_VERIFIED"), None)
            if (last_observation and history[-1].to_state == observation["target"]
                    and last_observation.provider_status == observation["status"]
                    and json.loads(last_observation.details_json) == observation["details"]):
                return last_observation
            if history[-1].seq != observation["expected_sequence"]:
                raise SequenceConflict("Ledger changed during verification; fetch provider status again.")
            return self._append_payment_event(connection, entry,
                        target=observation["target"], reason="PAYPAL_VERIFIED",
                        details=observation["details"], key=observation["key"],
                        provider_status=observation["status"], provider_invoice_id=observation["invoice_id"],
                        paid_amount_cents=observation["paid_cents"], gate=_VERIFIED_GATE)

    @staticmethod
    def _validate_payment_event(event, entry, history):
        from .store import _digest
        from ..payments.schemas import invoice_id, safe_invoice_url
        details = json.loads(event.details_json)
        if not history or event.request_hash != _digest(details):
            raise ValueError
        previous = history[-1]
        approval = approval_reference(history)
        if not approval:
            raise ValueError
        if event.reason == "PAYPAL_VERIFIED":
            from ..payments.verification import validate_recorded_observation
            validate_recorded_observation(event, entry, history)
            return
        if event.actor != "system":
            raise ValueError
        if event.reason == "OPERATION_REQUESTED":
            if set(details) != {"operation_key", "kind", "payload_hash", "request_id", "invoice_number"}:
                raise ValueError
            require_identifier(details["operation_key"])
            if details["kind"] not in {"create", "send"}:
                raise ValueError
            expected = State.APPROVED if details["kind"] == "create" else State.INVOICE_DRAFTED
            if event.to_state != expected:
                raise ValueError
        elif event.reason == "OPERATION_ERROR":
            if set(details) != {"operation_key", "error_code"} or details["error_code"] not in {
                "PAYMENT_AUTH_FAILED", "PAYMENT_RATE_LIMITED", "PAYMENT_STATUS_UNAVAILABLE",
                "PAYMENT_PROVIDER_REJECTED", "PAYMENT_RESPONSE_INVALID", "PAYMENT_REQUEST_INVALID"}:
                raise ValueError
            if not any(e.reason == "OPERATION_REQUESTED" and json.loads(e.details_json)["operation_key"] == details["operation_key"] for e in history):
                raise ValueError
            if event.to_state == State.FAILED and event.from_state != State.FAILED:
                if details["error_code"] != "PAYMENT_PROVIDER_REJECTED":
                    raise ValueError
                validate_transition(event.from_state, event.to_state)
                return
        elif event.reason in {"INVOICE_CREATED", "INVOICE_RECOVERED", "INVOICE_SEND_ACCEPTED"}:
            if set(details) != {"operation_key", "invoice_number", "reference", "currency", "total_cents", "invoice_url", "recipient_fingerprint"}:
                raise ValueError
            kind = "send" if event.reason == "INVOICE_SEND_ACCEPTED" else "create"
            operation_events = [e for e in history if e.reason == "OPERATION_REQUESTED"
                                and json.loads(e.details_json)["operation_key"] == details["operation_key"]]
            if len(operation_events) != 1 or json.loads(operation_events[0].details_json)["kind"] != kind:
                raise ValueError
            if (details["total_cents"] != entry.amount_cents or details["currency"] != entry.currency
                    or details["reference"] != entry.entry_id or not details["recipient_fingerprint"]):
                raise ValueError
            invoice_id(event.provider_invoice_id)
            safe_invoice_url(details["invoice_url"])
            if event.reason == "INVOICE_RECOVERED":
                if event.from_state != State.APPROVED or event.to_state != State.APPROVED or event.paid_amount_cents is not None:
                    raise ValueError
                return
            expected = State.INVOICE_DRAFTED if kind == "create" else State.INVOICE_SENT
            if event.to_state != expected or event.provider_status != ("DRAFT" if kind == "create" else None) or event.paid_amount_cents is not None:
                raise ValueError
            validate_transition(event.from_state, event.to_state, has_approval=True)
            return
        else:
            raise ValueError
        # Nonfinancial audit events cannot change financial state or evidence.
        if (event.from_state != event.to_state or event.provider_status != previous.provider_status
                or event.provider_invoice_id != previous.provider_invoice_id
                or event.paid_amount_cents != previous.paid_amount_cents):
            raise ValueError

    @staticmethod
    def _validate_payment_tables(connection, events):
        operations = {row["event_id"]: dict(row) for row in connection.execute("SELECT * FROM payment_operations")}
        bindings = {row["event_id"]: dict(row) for row in connection.execute("SELECT * FROM invoice_bindings")}
        for event in events.values():
            if event.reason == "OPERATION_REQUESTED":
                expected = json.loads(event.details_json) | {"entry_id": event.entry_id, "event_id": event.event_id}
                if operations.pop(event.event_id, None) != expected:
                    raise ValueError
            if event.reason in {"INVOICE_CREATED", "INVOICE_RECOVERED"}:
                expected = {"entry_id": event.entry_id, "provider_invoice_id": event.provider_invoice_id, "event_id": event.event_id}
                if bindings.pop(event.event_id, None) != expected:
                    raise ValueError
        if operations or bindings:
            raise ValueError
        from .store import _digest, GENESIS_HASH, LedgerStore
        seq, previous_hash = 0, GENESIS_HASH
        for row in connection.execute("SELECT * FROM processed_webhook_events ORDER BY seq"):
            receipt = dict(row)
            recorded_hash = receipt.pop("event_hash")
            require_identifier(receipt["provider_event_id"])
            LedgerStore._validate_time(receipt["received_at"])
            if (receipt["seq"] != seq + 1 or receipt["prev_hash"] != previous_hash
                    or _digest(receipt) != recorded_hash
                    or events[receipt["ledger_event_id"]].entry_id != receipt["entry_id"]):
                raise ValueError
            seq, previous_hash = receipt["seq"], recorded_hash
