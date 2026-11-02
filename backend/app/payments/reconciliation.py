"""Read-only PayPal recovery: never redispatch an ambiguous create or send."""

from dataclasses import dataclass

from ..ledger.errors import LedgerError
from ..ledger.models import State
from ..ledger.store import _digest
from .errors import PaymentError, RecoveryRequired
from .verification import VerificationService


@dataclass(frozen=True, slots=True)
class SweepResult:
    entry_id: str
    status: str
    error_code: str | None


class ReconciliationService:
    def __init__(self, ledger, client, invoice_service):
        self.ledger, self.client, self.invoices = ledger, client, invoice_service
        self.verification = VerificationService(ledger, client)

    def reconcile(self, entry_id):
        if not self.ledger._store.invoice_binding(entry_id):
            operations = [op for op in self.ledger._store.operations() if op["entry_id"] == entry_id and op["kind"] == "create"]
            if len(operations) != 1:
                raise RecoveryRequired()
            op = operations[0]
            snapshot, payload, fingerprint = self.invoices._prepare_create(entry_id)
            if snapshot.state != State.APPROVED or _digest(payload) != op["payload_hash"]:
                raise RecoveryRequired()
            candidates = []
            for identity in self.client.search_invoice_ids(op["invoice_number"]):
                invoice = self.client.get_invoice(identity)
                if (invoice.invoice_id == identity and invoice.invoice_number == op["invoice_number"]
                        and invoice.reference == entry_id and invoice.total_cents == snapshot.entry.amount_cents
                        and invoice.currency == snapshot.entry.currency and invoice.recipient_fingerprint == fingerprint):
                    candidates.append(invoice)
            if len(candidates) != 1:
                raise RecoveryRequired()
            self.ledger._store._complete_invoice(entry_id, op["operation_key"], candidates[0],
                                                expected_sequence=snapshot.sequence, recovered=True)
        # Binding recovery is not payment evidence. Always make another fresh
        # authenticated GET through the only verification writer.
        return self.verification.verify(entry_id)

    def sweep(self):
        operation_entries = {op["entry_id"] for op in self.ledger._store.operations()}
        results = []
        for snapshot in self.ledger.list_entries():
            if snapshot.entry.entry_id not in operation_entries or snapshot.state in {State.FAILED, State.CANCELLED, State.REFUNDED}:
                continue
            try:
                current = self.reconcile(snapshot.entry.entry_id)
                results.append(SweepResult(snapshot.entry.entry_id, current.state.value, None))
            except (PaymentError, LedgerError) as error:
                results.append(SweepResult(snapshot.entry.entry_id, self.ledger.get(snapshot.entry.entry_id).state.value,
                                           getattr(error, "code", "LEDGER_REVIEW_REQUIRED")))
        return tuple(results)
