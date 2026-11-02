import json
from pathlib import Path
import unittest

from backend.app.payments.contracts import error_view, ledger_view
from backend.app.payments.errors import ConfigurationError
from backend.app.payments.runtime import PaymentRuntime
from backend.app.ledger.models import State
from backend.tests.payments import test_invoice_service as fixtures
from backend.app.payments.verification import VerificationService
from backend.tests.payments.fakes import response


class AdapterTests(unittest.TestCase):
    setUp = fixtures.InvoiceServiceTests.setUp
    approve = fixtures.InvoiceServiceTests.approve
    provider_invoice = fixtures.InvoiceServiceTests.provider_invoice
    draft = fixtures.InvoiceServiceTests.draft
    sent = fixtures.InvoiceServiceTests.sent

    def test_serializer_matches_contract_keys_and_uses_verified_totals(self):
        self.sent()
        self.fake.steps += [response(self.provider_invoice("PAID", paid="12.00"))]
        VerificationService(self.ledger, self.api).verify(self.entry.entry_id)
        value = ledger_view(self.ledger, is_demo_data=True)
        fixture = json.loads((Path(__file__).resolve().parents[3] / "contracts/payment-ledger.example.json").read_text(encoding="utf-8-sig"))
        self.assertIn("ledger_response", fixture, "Shared fixture does not match the Member 3 implementation contract.")
        self.assertEqual(set(value["entries"][0]), set(fixture["ledger_response"]["entries"][0]))
        self.assertEqual(value["recovered_cash"], [{"amount_cents": 1200, "currency": "USD"}])
        self.assertIsNotNone(value["entries"][0]["verified_at"])
        self.assertNotIn("recipient_fingerprint", json.dumps(value))

    def test_unexpected_error_message_is_not_exposed(self):
        value = error_view(RuntimeError("untrusted internal diagnostic"), "req_demo")
        self.assertNotIn("diagnostic", json.dumps(value))
        self.assertEqual(set(value["error"]), {"code", "message", "request_id"})

    def test_runtime_rejects_missing_sandbox_config_before_opening_database(self):
        with self.assertRaises(ConfigurationError):
            PaymentRuntime.from_env(lambda _: None, env={})

    def test_postman_export_has_only_sandbox_urls_and_empty_credentials(self):
        directory = Path(__file__).resolve().parents[2] / "app/payments/postman"
        collection = json.loads((directory / "paypal-sandbox.collection.json").read_text())
        environment = json.loads((directory / "sandbox.empty.environment.json").read_text())
        self.assertEqual(len(collection["item"]), 5)
        for item in collection["item"]:
            self.assertTrue(item["request"]["url"].startswith("https://api-m.sandbox.paypal.com/"))
        for variable in environment["values"]:
            if variable["key"] not in {"PAYPAL_MODE", "ledger_approval_confirmed"}:
                self.assertEqual(variable["value"], "")
        self.assertNotIn("pm.environment.set", json.dumps(collection))

    def test_late_operation_error_cannot_write_a_paid_event(self):
        self.sent()
        self.fake.steps += [response(self.provider_invoice("PAID", paid="12.00"))]
        VerificationService(self.ledger, self.api).verify(self.entry.entry_id)
        before = self.ledger.verify_integrity()
        self.ledger._store._operation_failure(self.entry.entry_id, "send", "PAYMENT_STATUS_UNAVAILABLE")
        self.assertEqual(self.ledger.verify_integrity(), before)
        for event in self.ledger.get(self.entry.entry_id).events:
            if event.to_state == State.VERIFIED_PAID:
                self.assertEqual(event.actor, "verification_service")
                self.assertEqual(event.reason, "PAYPAL_VERIFIED")
