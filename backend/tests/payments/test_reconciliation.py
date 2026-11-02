import unittest
from unittest.mock import patch

from backend.app.ledger.models import State
from backend.app.payments.errors import ProviderTimeout, RecoveryRequired
from backend.app.payments.reconciliation import ReconciliationService
from backend.tests.payments import test_invoice_service as fixtures
from backend.tests.payments.fakes import INVOICE_ID, oauth, response


class ReconciliationTests(unittest.TestCase):
    setUp = fixtures.InvoiceServiceTests.setUp
    approve = fixtures.InvoiceServiceTests.approve
    provider_invoice = fixtures.InvoiceServiceTests.provider_invoice
    draft = fixtures.InvoiceServiceTests.draft
    sent = fixtures.InvoiceServiceTests.sent

    def reconciler(self):
        return ReconciliationService(self.ledger, self.api, self.service)

    def uncertain_create(self):
        self.approve()
        self.fake.steps += [oauth(), ProviderTimeout()]
        with self.assertRaises(ProviderTimeout):
            self.service.create_draft(self.entry.entry_id, idempotency_key="create")

    def test_create_timeout_is_recovered_without_second_post(self):
        self.uncertain_create()
        self.fake.steps += [response({"items": [{"id": INVOICE_ID}]}),
                            response(self.provider_invoice()), response(self.provider_invoice())]
        self.assertEqual(self.reconciler().reconcile(self.entry.entry_id).state, State.INVOICE_DRAFTED)
        self.assertEqual(sum(call[1] == "/v2/invoicing/invoices" for call in self.fake.calls), 1)
        self.ledger.verify_integrity()

    def test_crash_after_paypal_success_recovers_paid_invoice_with_fresh_verification(self):
        self.approve()
        self.fake.steps += [oauth(), response(self.provider_invoice(), 201)]
        with patch.object(self.ledger._store, "_complete_invoice", side_effect=RuntimeError("simulated crash")):
            with self.assertRaises(RuntimeError):
                self.service.create_draft(self.entry.entry_id, idempotency_key="create")
        self.fake.steps += [response({"items": [{"id": INVOICE_ID}]}),
                            response(self.provider_invoice("PAID", paid="12.00")),
                            response(self.provider_invoice("PAID", paid="12.00"))]
        result = self.reconciler().reconcile(self.entry.entry_id)
        self.assertEqual(result.state, State.VERIFIED_PAID)
        self.assertEqual(self.ledger.recovered_cash(), {"USD": 1200})
        self.assertEqual(result.events[-2].to_state, State.APPROVED)

    def test_not_found_remains_uncertain_and_never_reposts(self):
        self.uncertain_create()
        before = self.ledger.verify_integrity()
        self.fake.steps += [response({"items": []})]
        with self.assertRaises(RecoveryRequired):
            self.reconciler().reconcile(self.entry.entry_id)
        self.assertEqual(self.ledger.verify_integrity(), before)
        self.assertEqual(sum(call[1] == "/v2/invoicing/invoices" for call in self.fake.calls), 1)

    def test_duplicate_search_matches_are_not_bound(self):
        self.uncertain_create()
        self.fake.steps += [response({"items": [{"id": INVOICE_ID}, {"id": INVOICE_ID}]}),
                            response(self.provider_invoice()), response(self.provider_invoice())]
        with self.assertRaises(RecoveryRequired):
            self.reconciler().reconcile(self.entry.entry_id)
        self.assertIsNone(self.ledger._store.invoice_binding(self.entry.entry_id))

    def test_sweep_reports_outage_without_state_change(self):
        self.sent()
        checkpoint = self.ledger.verify_integrity()
        self.fake.steps += [ProviderTimeout(), ProviderTimeout(), ProviderTimeout()]
        result = self.reconciler().sweep()
        self.assertEqual(result[0].error_code, "PAYMENT_STATUS_UNAVAILABLE")
        self.assertEqual(self.ledger.verify_integrity(), checkpoint)

    def test_verified_entries_are_swept_to_detect_refunds(self):
        self.sent()
        self.fake.steps += [response(self.provider_invoice("PAID", paid="12.00"))]
        self.reconciler().reconcile(self.entry.entry_id)
        self.fake.steps += [response(self.provider_invoice("REFUNDED", paid="12.00"))]
        self.assertEqual(self.reconciler().sweep()[0].status, "REFUNDED")
        self.assertEqual(self.ledger.recovered_cash(), {"USD": 0})
