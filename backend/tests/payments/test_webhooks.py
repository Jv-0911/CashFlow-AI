import json
import unittest
from uuid import uuid4

from backend.app.ledger.models import State
from backend.app.payments.errors import InvalidWebhook, ProviderTimeout
from backend.app.payments.webhooks import WebhookHandler
from backend.tests.payments import test_invoice_service as fixtures
from backend.tests.payments.fakes import INVOICE_ID, response


class WebhookTests(unittest.TestCase):
    setUp = fixtures.InvoiceServiceTests.setUp
    approve = fixtures.InvoiceServiceTests.approve
    provider_invoice = fixtures.InvoiceServiceTests.provider_invoice
    draft = fixtures.InvoiceServiceTests.draft
    sent = fixtures.InvoiceServiceTests.sent

    def headers(self):
        return {"PAYPAL-AUTH-ALGO": "SHA256withRSA", "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/v1/notifications/certs/CERT-DEMO",
                "PAYPAL-TRANSMISSION-ID": "transmission-demo", "PAYPAL-TRANSMISSION-SIG": uuid4().hex,
                "PAYPAL-TRANSMISSION-TIME": "2026-10-13T00:00:00Z"}

    def body(self, event_id="event_demo", identity=INVOICE_ID, status="PAID"):
        return json.dumps({"id": event_id, "event_type": "INVOICING.INVOICE.PAID",
                           "resource": {"id": identity, "status": status, "paid_amount_cents": 999999}}).encode()

    def handler(self):
        return WebhookHandler(self.ledger, self.api)

    def test_invalid_signature_has_no_ledger_effect(self):
        self.sent()
        before = self.ledger.verify_integrity()
        self.fake.steps += [response({"verification_status": "FAILURE"})]
        with self.assertRaises(InvalidWebhook):
            self.handler().handle(self.body(), self.headers())
        self.assertEqual(self.ledger.verify_integrity(), before)

    def test_missing_signature_headers_or_live_certificate_rejected_before_network(self):
        self.sent()
        before = len(self.fake.calls)
        for headers in ({}, self.headers() | {"PAYPAL-CERT-URL": "https://api.paypal.com/v1/notifications/certs/CERT-DEMO"}):
            with self.assertRaises(InvalidWebhook):
                self.handler().handle(self.body(), headers)
        self.assertEqual(len(self.fake.calls), before)

    def test_valid_signed_paid_body_is_only_a_hint(self):
        self.sent()
        self.fake.steps += [response({"verification_status": "SUCCESS"}), response(self.provider_invoice("PAYMENT_PENDING"))]
        self.assertEqual(self.handler().handle(self.body(), self.headers()), "processed")
        self.assertEqual(self.ledger.get(self.entry.entry_id).state, State.PAYMENT_PENDING)
        self.assertEqual(self.ledger.recovered_cash(), {"USD": 0})

    def test_duplicate_is_signature_checked_then_deduplicated(self):
        self.sent()
        self.fake.steps += [response({"verification_status": "SUCCESS"}), response(self.provider_invoice("PAID", paid="12.00"))]
        self.handler().handle(self.body(), self.headers())
        before = self.ledger.verify_integrity()
        self.fake.steps += [response({"verification_status": "SUCCESS"})]
        self.assertEqual(self.handler().handle(self.body(), self.headers()), "duplicate")
        self.assertEqual(self.ledger.verify_integrity(), before)
        self.assertEqual(self.ledger.recovered_cash(), {"USD": 1200})

    def test_out_of_order_body_cannot_downgrade_current_paid_invoice(self):
        self.sent()
        for event_id, body_status in (("new", "PAID"), ("old", "SENT")):
            self.fake.steps += [response({"verification_status": "SUCCESS"}), response(self.provider_invoice("PAID", paid="12.00"))]
            self.handler().handle(self.body(event_id=event_id, status=body_status), self.headers())
        self.assertEqual(self.ledger.get(self.entry.entry_id).state, State.VERIFIED_PAID)
        self.assertEqual(self.ledger.recovered_cash(), {"USD": 1200})
        self.ledger.verify_integrity()

    def test_unknown_invoice_acknowledged_without_write(self):
        self.sent()
        before = self.ledger.verify_integrity()
        self.fake.steps += [response({"verification_status": "SUCCESS"})]
        self.assertEqual(self.handler().handle(self.body(identity="INV2-DEMO-0000-0000-9999"), self.headers()), "unknown_invoice")
        self.assertEqual(self.ledger.verify_integrity(), before)

    def test_valid_signature_with_mismatched_fresh_amount_never_completes(self):
        self.sent()
        self.fake.steps += [response({"verification_status": "SUCCESS"}), response(self.provider_invoice("PAID", value="13.00", paid="13.00"))]
        self.handler().handle(self.body(), self.headers())
        self.assertEqual(self.ledger.get(self.entry.entry_id).state, State.UNRESOLVED)
        self.assertEqual(self.ledger.recovered_cash(), {"USD": 0})

    def test_provider_outage_after_dedup_keeps_state_for_reconciliation(self):
        self.sent()
        self.fake.steps += [response({"verification_status": "SUCCESS"}), ProviderTimeout(), ProviderTimeout(), ProviderTimeout()]
        with self.assertRaises(ProviderTimeout):
            self.handler().handle(self.body(), self.headers())
        self.assertEqual(self.ledger.get(self.entry.entry_id).state, State.INVOICE_SENT)
        self.fake.steps += [response({"verification_status": "SUCCESS"})]
        self.assertEqual(self.handler().handle(self.body(), self.headers()), "duplicate")

    def test_oversize_body_and_duplicate_headers_are_rejected_before_network(self):
        self.sent()
        before = len(self.fake.calls)
        for body, headers in ((b"x" * 262145, self.headers()),
                              (self.body(), self.headers() | {"paypal-auth-algo": "SHA256withRSA"})):
            with self.assertRaises(InvalidWebhook):
                self.handler().handle(body, headers)
        self.assertEqual(len(self.fake.calls), before)

    def test_signature_service_outage_has_no_receipt_or_financial_effect(self):
        self.sent()
        checkpoint = self.ledger.verify_integrity()
        self.fake.steps += [ProviderTimeout(), ProviderTimeout(), ProviderTimeout()]
        with self.assertRaises(ProviderTimeout):
            self.handler().handle(self.body(), self.headers())
        self.assertEqual(self.ledger.verify_integrity(), checkpoint)
        # Same event is still eligible after authenticity can be established.
        self.fake.steps += [response({"verification_status": "SUCCESS"}), response(self.provider_invoice("SENT"))]
        self.assertEqual(self.handler().handle(self.body(), self.headers()), "processed")
