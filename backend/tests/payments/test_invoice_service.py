from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
import unittest

from backend.app.ledger.errors import IdempotencyConflict
from backend.app.ledger.models import State
from backend.app.ledger.service import LedgerService
from backend.app.payments.errors import ApprovalRequired, MalformedResponse, ProviderRejected, ProviderTimeout, RecoveryRequired
from backend.app.payments.invoice_service import InvoiceService, invoice_number
from backend.app.payments.paypal_client import Response
from backend.tests.payments.fakes import INVOICE_ID, client, invoice, oauth, response


class InvoiceServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ledger = LedgerService(Path(self.temp.name) / "ledger.db")
        self.entry = self.ledger.propose(idempotency_key="proposal", amount_cents=1200, currency="USD")
        self.api, self.fake = client()
        self.service = InvoiceService(self.ledger, self.api, lambda ref: "demo-payer@example.test")

    def approve(self):
        return self.ledger.approve(self.entry.entry_id, idempotency_key="approval", expected_sequence=1,
                                   approved_by="user_demo", payer_reference="payer_demo")

    def provider_invoice(self, status="DRAFT", **kwargs):
        return invoice(status, reference=self.entry.entry_id, number=invoice_number(self.entry.entry_id), **kwargs)

    def draft(self):
        self.approve()
        self.fake.steps += [oauth(), response(self.provider_invoice(), 201)]
        return self.service.create_draft(self.entry.entry_id, idempotency_key="create")

    def sent(self):
        self.draft()
        self.fake.steps += [response(self.provider_invoice()), Response(202, b"")]
        return self.service.send(self.entry.entry_id, idempotency_key="send")

    def test_create_and_send_are_idempotent_and_keep_cash_zero(self):
        drafted = self.draft()
        self.assertEqual(drafted.state, State.INVOICE_DRAFTED)
        self.assertEqual(self.service.create_draft(self.entry.entry_id, idempotency_key="create"), drafted)
        self.assertEqual(len(self.fake.calls), 2)
        self.fake.steps += [response(self.provider_invoice()), Response(202, b"")]
        sent = self.service.send(self.entry.entry_id, idempotency_key="send")
        self.assertEqual(sent.state, State.INVOICE_SENT)
        self.assertIsNone(sent.events[-1].provider_status)  # Ack does not fabricate a status.
        self.assertEqual(self.service.send(self.entry.entry_id, idempotency_key="send"), sent)
        self.assertEqual(len(self.fake.calls), 4)
        self.assertEqual(self.ledger.recovered_cash(), {"USD": 0})
        self.assertEqual(self.ledger._store.invoice_binding(self.entry.entry_id)["provider_invoice_id"], INVOICE_ID)
        for call in (self.fake.calls[1], self.fake.calls[3]):
            self.assertIn("PayPal-Request-Id", call[2])
        self.ledger.verify_integrity()

    def test_human_approval_and_payer_binding_are_required_before_network(self):
        with self.assertRaises(ApprovalRequired):
            self.service.create_draft(self.entry.entry_id, idempotency_key="create")
        self.ledger.approve(self.entry.entry_id, idempotency_key="old_approval", expected_sequence=1, approved_by="user_demo")
        with self.assertRaises(ApprovalRequired):
            self.service.create_draft(self.entry.entry_id, idempotency_key="create")
        self.assertEqual(self.fake.calls, [])

    def test_reusing_entry_with_new_create_key_never_duplicates_invoice(self):
        self.draft()
        with self.assertRaises(IdempotencyConflict):
            self.service.create_draft(self.entry.entry_id, idempotency_key="create_again")
        self.assertEqual(len(self.fake.calls), 2)

    def test_timeout_keeps_state_and_replay_requires_reconciliation(self):
        self.approve()
        self.fake.steps += [oauth(), ProviderTimeout()]
        with self.assertRaises(ProviderTimeout):
            self.service.create_draft(self.entry.entry_id, idempotency_key="create")
        self.assertEqual(self.ledger.get(self.entry.entry_id).state, State.APPROVED)
        with self.assertRaises(RecoveryRequired):
            self.service.create_draft(self.entry.entry_id, idempotency_key="create")
        self.assertEqual(len(self.fake.calls), 2)
        self.ledger.verify_integrity()

    def test_creation_rejection_records_failed_without_provider_diagnostic(self):
        self.approve()
        self.fake.steps += [oauth(), Response(422, b"provider body must never persist")]
        with self.assertRaises(ProviderRejected):
            self.service.create_draft(self.entry.entry_id, idempotency_key="create")
        snapshot = self.ledger.get(self.entry.entry_id)
        self.assertEqual(snapshot.state, State.FAILED)
        self.assertNotIn("provider body", repr(snapshot))

    def test_mismatched_draft_does_not_bind_invoice(self):
        self.approve()
        self.fake.steps += [oauth(), response(self.provider_invoice(value="13.00"), 201)]
        with self.assertRaises(MalformedResponse):
            self.service.create_draft(self.entry.entry_id, idempotency_key="create")
        self.assertIsNone(self.ledger._store.invoice_binding(self.entry.entry_id))
        self.assertEqual(self.ledger.get(self.entry.entry_id).state, State.APPROVED)

    def test_provider_edited_recipient_is_not_sent(self):
        self.draft()
        value = self.provider_invoice()
        value["primary_recipients"][0]["billing_info"]["email_address"] = "changed@example.test"
        self.fake.steps += [response(value)]
        with self.assertRaises(MalformedResponse):
            self.service.send(self.entry.entry_id, idempotency_key="send")
        self.assertEqual(self.ledger.get(self.entry.entry_id).state, State.INVOICE_DRAFTED)
        self.assertFalse(any(call[1].endswith("/send") for call in self.fake.calls))

    def test_send_timeout_keeps_draft_and_blocks_repeat_dispatch(self):
        self.draft()
        self.fake.steps += [response(self.provider_invoice()), ProviderTimeout()]
        with self.assertRaises(ProviderTimeout):
            self.service.send(self.entry.entry_id, idempotency_key="send")
        with self.assertRaises(RecoveryRequired):
            self.service.send(self.entry.entry_id, idempotency_key="send")
        self.assertEqual(self.ledger.get(self.entry.entry_id).state, State.INVOICE_DRAFTED)
        self.assertEqual(sum(call[1].endswith("/send") for call in self.fake.calls), 1)

    def test_concurrent_creates_dispatch_once(self):
        self.approve()
        self.fake.steps += [oauth(), response(self.provider_invoice(), 201)]
        barrier = Barrier(4)
        def worker(_):
            barrier.wait()
            try:
                return self.service.create_draft(self.entry.entry_id, idempotency_key="create")
            except RecoveryRequired:
                return None
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(worker, range(4)))
        self.assertEqual(sum(call[1] == "/v2/invoicing/invoices" for call in self.fake.calls), 1)
        self.assertEqual(self.ledger.get(self.entry.entry_id).state, State.INVOICE_DRAFTED)

    def test_payer_email_is_not_stored_in_ledger(self):
        self.draft()
        snapshots = repr(self.ledger.list_entries())
        self.assertNotIn("demo-payer", snapshots)
        self.assertNotIn("example.test", snapshots)
        details = json.loads(self.ledger.get(self.entry.entry_id).events[1].details_json)
        self.assertEqual(details, {"payer_reference": "payer_demo"})

    def test_concurrent_sends_dispatch_once(self):
        self.draft()
        # Multiple contenders may perform a read-only preflight before the
        # atomic dispatch claim. All reads return the same immutable draft.
        def provider(method, path, headers, body):
            return response(self.provider_invoice()) if method == "GET" else Response(202, b"")
        self.fake.steps += [provider] * 5
        barrier = Barrier(4)

        def worker(_):
            barrier.wait()
            try:
                return self.service.send(self.entry.entry_id, idempotency_key="send")
            except RecoveryRequired:
                return None

        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(worker, range(4)))
        self.assertEqual(sum(call[1].endswith("/send") for call in self.fake.calls), 1)
        self.assertEqual(self.ledger.get(self.entry.entry_id).state, State.INVOICE_SENT)
