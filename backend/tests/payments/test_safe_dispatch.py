"""Only pre-dispatch failures are freely retryable; ambiguous writes stay claimed."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import unittest
from unittest.mock import patch

from backend.app.ledger.errors import SequenceConflict
from backend.app.ledger.models import State
from backend.app.payments.errors import AuthError, MalformedResponse, ProviderTimeout, RateLimited, RecoveryRequired
from backend.app.payments.invoice_service import InvoiceService
from backend.app.payments.paypal_client import Response
from backend.tests.payments import test_invoice_service as fixtures
from backend.tests.payments.fakes import client, oauth, response


class SafeDispatchTests(unittest.TestCase):
    setUp = fixtures.InvoiceServiceTests.setUp
    approve = fixtures.InvoiceServiceTests.approve
    provider_invoice = fixtures.InvoiceServiceTests.provider_invoice
    draft = fixtures.InvoiceServiceTests.draft
    sent = fixtures.InvoiceServiceTests.sent

    def test_create_auth_failure_is_retryable_without_claim_or_ledger_write(self):
        self.approve()
        checkpoint = self.ledger.verify_integrity()
        for failure in (Response(401, b""), response({})):
            self.fake.steps += [failure]
            with self.assertRaises(AuthError):
                self.service.create_draft(self.entry.entry_id, idempotency_key="create")
            self.assertEqual(self.ledger.verify_integrity(), checkpoint)
            self.assertEqual(self.ledger._store.operations(), ())
        self.fake.steps += [oauth(), response(self.provider_invoice(), 201)]
        self.assertEqual(self.service.create_draft(self.entry.entry_id, idempotency_key="create").state, State.INVOICE_DRAFTED)
        self.assertEqual(sum(call[1] == "/v2/invoicing/invoices" for call in self.fake.calls), 1)

    def test_oauth_timeout_and_rate_limit_keep_claim_available(self):
        self.approve()
        checkpoint = self.ledger.verify_integrity()
        for failure, error in ((ProviderTimeout(), ProviderTimeout), (Response(429, b""), RateLimited)):
            self.fake.steps += [failure] * 3
            with self.assertRaises(error):
                self.service.create_draft(self.entry.entry_id, idempotency_key="create")
            self.assertEqual(self.ledger.verify_integrity(), checkpoint)
            self.assertEqual(self.ledger._store.operations(), ())
        self.fake.steps += [oauth(), response(self.provider_invoice(), 201)]
        self.service.create_draft(self.entry.entry_id, idempotency_key="create")

    def test_send_preflight_timeout_is_retryable_with_same_key(self):
        self.draft()
        checkpoint = self.ledger.verify_integrity()
        self.fake.steps += [ProviderTimeout()] * 3
        with self.assertRaises(ProviderTimeout):
            self.service.send(self.entry.entry_id, idempotency_key="send")
        self.assertEqual(self.ledger.verify_integrity(), checkpoint)
        self.assertEqual([op["kind"] for op in self.ledger._store.operations()], ["create"])
        self.fake.steps += [response(self.provider_invoice()), Response(202, b"")]
        self.assertEqual(self.service.send(self.entry.entry_id, idempotency_key="send").state, State.INVOICE_SENT)
        self.assertEqual(sum(call[1].endswith("/send") for call in self.fake.calls), 1)

    def test_send_preflight_mismatch_does_not_consume_claim(self):
        self.draft()
        checkpoint = self.ledger.verify_integrity()
        self.fake.steps += [response(self.provider_invoice(value="13.00"))]
        with self.assertRaises(MalformedResponse):
            self.service.send(self.entry.entry_id, idempotency_key="send")
        self.assertEqual(self.ledger.verify_integrity(), checkpoint)
        self.fake.steps += [response(self.provider_invoice()), Response(202, b"")]
        self.assertEqual(self.service.send(self.entry.entry_id, idempotency_key="send").state, State.INVOICE_SENT)

    def test_auth_failure_between_preflight_and_send_keeps_claim_available(self):
        self.draft()
        checkpoint = self.ledger.verify_integrity()

        def draft_then_expire(*args):
            self.api._token = None
            return response(self.provider_invoice())

        self.fake.steps += [draft_then_expire, Response(401, b"")]
        with self.assertRaises(AuthError):
            self.service.send(self.entry.entry_id, idempotency_key="send")
        self.assertEqual(self.ledger.verify_integrity(), checkpoint)
        self.fake.steps += [oauth(), response(self.provider_invoice()), Response(202, b"")]
        self.service.send(self.entry.entry_id, idempotency_key="send")
        self.assertEqual(sum(call[1].endswith("/send") for call in self.fake.calls), 1)

    def test_post_dispatch_auth_failure_does_not_authorize_another_attempt(self):
        self.approve()
        self.fake.steps += [oauth(), Response(401, b""), Response(401, b"")]
        with self.assertRaises(AuthError):
            self.service.create_draft(self.entry.entry_id, idempotency_key="create")
        before = len(self.fake.calls)
        with self.assertRaises(RecoveryRequired):
            self.service.create_draft(self.entry.entry_id, idempotency_key="create")
        self.assertEqual(len(self.fake.calls), before)
        self.assertEqual(len(self.ledger._store.operations()), 1)

    def test_committed_claim_exists_before_outbound_write(self):
        self.approve()

        def check_claim(method, path, headers, body):
            operations = self.ledger._store.operations()
            self.assertEqual(len(operations), 1)
            self.assertEqual(headers["PayPal-Request-Id"], operations[0]["request_id"])
            self.ledger.verify_integrity()
            return response(self.provider_invoice(), 201)

        self.fake.steps += [oauth(), check_claim]
        self.service.create_draft(self.entry.entry_id, idempotency_key="create")

    def test_claim_failure_prevents_outbound_write(self):
        self.approve()
        checkpoint = self.ledger.verify_integrity()
        self.fake.steps += [oauth()]
        with patch.object(self.ledger._store, "_claim_operation", side_effect=SequenceConflict("Ledger changed.")):
            with self.assertRaises(SequenceConflict):
                self.service.create_draft(self.entry.entry_id, idempotency_key="create")
        self.assertEqual([call[1] for call in self.fake.calls], ["/v1/oauth2/token"])
        self.assertEqual(self.ledger.verify_integrity(), checkpoint)

    def test_crash_after_claim_preserves_uncertainty_instead_of_reclaiming(self):
        self.approve()
        self.fake.steps += [oauth()]
        original = self.ledger._store._claim_operation

        def claim_then_crash(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("Simulated process interruption")

        with patch.object(self.ledger._store, "_claim_operation", side_effect=claim_then_crash):
            with self.assertRaises(RuntimeError):
                self.service.create_draft(self.entry.entry_id, idempotency_key="create")
        before = len(self.fake.calls)
        with self.assertRaises(RecoveryRequired):
            self.service.create_draft(self.entry.entry_id, idempotency_key="create")
        self.assertEqual(len(self.fake.calls), before)
        self.assertEqual(len(self.ledger._store.operations()), 1)
        self.ledger.verify_integrity()

    def test_401_refresh_uses_one_claim_and_the_same_request_id(self):
        self.approve()
        self.fake.steps += [oauth(), Response(401, b""), oauth(), response(self.provider_invoice(), 201)]
        self.service.create_draft(self.entry.entry_id, idempotency_key="create")
        writes = [call for call in self.fake.calls if call[1] == "/v2/invoicing/invoices"]
        self.assertEqual(len(writes), 2)
        self.assertEqual(writes[0][2]["PayPal-Request-Id"], writes[1][2]["PayPal-Request-Id"])
        self.assertEqual(len(self.ledger._store.operations()), 1)
        events = self.ledger.get(self.entry.entry_id).events
        self.assertEqual(sum(event.reason == "OPERATION_REQUESTED" for event in events), 1)

    def test_independent_clients_racing_after_oauth_dispatch_once(self):
        self.approve()
        barrier = Barrier(2)
        workers = []
        for _ in range(2):
            def auth(*args):
                barrier.wait()
                return oauth()
            api, fake = client(auth, response(self.provider_invoice(), 201))
            workers.append((InvoiceService(self.ledger, api, lambda _: "demo-payer@example.test"), fake))

        def create(worker):
            try:
                worker[0].create_draft(self.entry.entry_id, idempotency_key="create")
            except RecoveryRequired:
                pass

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(create, workers))
        self.assertEqual(sum(call[1] == "/v2/invoicing/invoices" for _, fake in workers for call in fake.calls), 1)
        self.assertEqual(self.ledger.get(self.entry.entry_id).state, State.INVOICE_DRAFTED)
