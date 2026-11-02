"""HTTP uncertainty must not manufacture a terminal financial outcome."""

import unittest

from backend.app.ledger.models import State
from backend.app.payments.errors import ProviderTimeout, ProviderUnavailable, RecoveryRequired
from backend.app.payments.paypal_client import Response
from backend.app.payments.verification import VerificationService
from backend.tests.payments import test_invoice_service as fixtures
from backend.tests.payments.fakes import oauth, response


class HttpOutcomeTests(unittest.TestCase):
    def fixture(self):
        fixture = fixtures.InvoiceServiceTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return fixture

    def test_ambiguous_create_http_outcomes_preserve_approval_and_block_repost(self):
        for status in (100, 200, 202, 204, 301, 302, 307, 308, 408, 409, 425, 503):
            with self.subTest(status=status):
                f = self.fixture()
                f.approve()
                f.fake.steps += [oauth(), Response(status, b"")]
                expected = ProviderTimeout if status == 408 else ProviderUnavailable
                with self.assertRaises(expected):
                    f.service.create_draft(f.entry.entry_id, idempotency_key="create")
                self.assertEqual(f.ledger.get(f.entry.entry_id).state, State.APPROVED)
                self.assertIsNone(f.ledger._store.invoice_binding(f.entry.entry_id))
                with self.assertRaises(RecoveryRequired):
                    f.service.create_draft(f.entry.entry_id, idempotency_key="create")
                self.assertEqual(len(f.fake.calls), 2)
                f.ledger.verify_integrity()

    def test_ambiguous_send_http_outcomes_preserve_draft_and_block_resend(self):
        for status in (201, 302, 307, 408, 409, 425, 503):
            with self.subTest(status=status):
                f = self.fixture()
                f.draft()
                f.fake.steps += [response(f.provider_invoice()), Response(status, b"")]
                expected = ProviderTimeout if status == 408 else ProviderUnavailable
                with self.assertRaises(expected):
                    f.service.send(f.entry.entry_id, idempotency_key="send")
                self.assertEqual(f.ledger.get(f.entry.entry_id).state, State.INVOICE_DRAFTED)
                with self.assertRaises(RecoveryRequired):
                    f.service.send(f.entry.entry_id, idempotency_key="send")
                self.assertEqual(sum(call[1].endswith("/send") for call in f.fake.calls), 1)
                f.ledger.verify_integrity()

    def test_http_uncertainty_does_not_change_unpaid_or_verified_history(self):
        for paid in (False, True):
            for status in (202, 302, 408, 409, 425, 503):
                with self.subTest(paid=paid, status=status):
                    f = self.fixture()
                    f.sent()
                    verifier = VerificationService(f.ledger, f.api)
                    if paid:
                        f.fake.steps += [response(f.provider_invoice("PAID", paid="12.00"))]
                        verifier.verify(f.entry.entry_id)
                    before = f.ledger.get(f.entry.entry_id)
                    f.fake.steps += [Response(status, b"")] * 3
                    expected = ProviderTimeout if status == 408 else ProviderUnavailable
                    with self.assertRaises(expected):
                        verifier.verify(f.entry.entry_id)
                    self.assertEqual(f.ledger.get(f.entry.entry_id), before)
                    self.assertEqual(f.ledger.recovered_cash(), {"USD": 1200 if paid else 0})
