import copy
from contextlib import contextmanager
import json
import unittest
from unittest.mock import patch

from backend.app.ledger.errors import IllegalTransition, SequenceConflict
from backend.app.ledger.models import State
from backend.app.payments.errors import AuthError, ProviderTimeout, RecoveryRequired
from backend.app.payments.paypal_client import Response
from backend.app.payments.verification import VerificationService, STATUS_MAP, map_status
from backend.tests.payments import test_invoice_service as fixtures
from backend.tests.payments.fakes import response


class VerificationTests(unittest.TestCase):
    setUp = fixtures.InvoiceServiceTests.setUp
    approve = fixtures.InvoiceServiceTests.approve
    provider_invoice = fixtures.InvoiceServiceTests.provider_invoice
    draft = fixtures.InvoiceServiceTests.draft
    sent = fixtures.InvoiceServiceTests.sent

    def verify(self, value):
        self.fake.steps += [response(value)]
        return VerificationService(self.ledger, self.api).verify(self.entry.entry_id)

    def test_all_statuses_are_explicit_and_unknown_values_never_succeed(self):
        expected = {"DRAFT": State.INVOICE_DRAFTED, "SENT": State.INVOICE_SENT,
                    "UNPAID": State.INVOICE_SENT, "SCHEDULED": State.INVOICE_SENT,
                    "PAYMENT_PENDING": State.PAYMENT_PENDING, "PARTIALLY_PAID": State.PARTIALLY_PAID,
                    "PAID": State.VERIFIED_PAID, "MARKED_AS_PAID": State.OFFLINE_MARKED_PAID,
                    "CANCELLED": State.CANCELLED, "REFUNDED": State.REFUNDED,
                    "PARTIALLY_REFUNDED": State.REFUNDED, "MARKED_AS_REFUNDED": State.REFUNDED}
        self.assertEqual(dict(STATUS_MAP), expected)
        for value in (None, {}, [], True, "", "paid", "COMPLETED", "FAILED", "FUTURE_STATUS"):
            self.assertEqual(map_status(value), State.UNRESOLVED)

    def test_verified_cash_requires_fresh_get_and_is_not_double_counted(self):
        self.sent()
        result = self.verify(self.provider_invoice("PAID", paid="12.00"))
        self.assertEqual(result.state, State.VERIFIED_PAID)
        self.assertEqual(self.fake.calls[-1][0], "GET")
        self.assertEqual(self.ledger.recovered_cash(), {"USD": 1200})
        again = self.verify(self.provider_invoice("PAID", paid="12.00"))
        self.assertEqual(again.sequence, result.sequence)
        self.assertEqual(self.ledger.recovered_cash(), {"USD": 1200})
        self.ledger.verify_integrity()

    def test_pending_and_partial_payments_do_not_count(self):
        self.sent()
        self.assertEqual(self.verify(self.provider_invoice("PAYMENT_PENDING")).state, State.PAYMENT_PENDING)
        result = self.verify(self.provider_invoice("PARTIALLY_PAID", paid="6.00"))
        self.assertEqual(result.state, State.PARTIALLY_PAID)
        self.assertEqual(result.events[-1].paid_amount_cents, 600)
        self.assertEqual(self.ledger.recovered_cash(), {"USD": 0})
        self.assertEqual(self.verify(self.provider_invoice("PAID", paid="12.00")).state, State.VERIFIED_PAID)

    def test_offline_marked_paid_never_counts(self):
        self.sent()
        result = self.verify(self.provider_invoice("MARKED_AS_PAID", paid="12.00", payment_type="EXTERNAL"))
        self.assertEqual(result.state, State.OFFLINE_MARKED_PAID)
        self.assertEqual(result.events[-1].provider_status, "MARKED_AS_PAID")
        self.assertEqual(self.ledger.recovered_cash(), {"USD": 0})

    def test_cancelled_is_not_recovered(self):
        self.sent()
        self.assertEqual(self.verify(self.provider_invoice("CANCELLED")).state, State.CANCELLED)
        self.assertEqual(self.ledger.recovered_cash(), {"USD": 0})

    def test_paid_status_without_paypal_processed_transactions_is_unresolved(self):
        self.sent()
        result = self.verify(self.provider_invoice("PAID", paid="12.00", payment_type="EXTERNAL"))
        self.assertEqual(result.state, State.UNRESOLVED)
        self.assertEqual(self.ledger.recovered_cash(), {"USD": 0})

    def test_identity_currency_amount_recipient_and_missing_evidence_mismatches(self):
        self.sent()
        original = self.provider_invoice("PAID", paid="12.00")
        cases = []
        value = copy.deepcopy(original); value["id"] = "INV2-DEMO-0000-0000-9999"; cases.append(value)
        value = copy.deepcopy(original); value["amount"]["value"] = "13.00"; cases.append(value)
        value = copy.deepcopy(original); value["amount"]["currency_code"] = "EUR"; cases.append(value)
        value = copy.deepcopy(original); value["primary_recipients"][0]["billing_info"]["email_address"] = "changed@example.test"; cases.append(value)
        value = copy.deepcopy(original); value["payments"].pop("transactions"); cases.append(value)
        value = copy.deepcopy(original); value.pop("due_amount"); cases.append(value)
        value = copy.deepcopy(original); value["detail"]["reference"] = "entry_wrong"; cases.append(value)
        value = copy.deepcopy(original); value["due_amount"]["value"] = "1.00"; cases.append(value)
        for index, value in enumerate(cases):
            with self.subTest(case=index):
                self.assertEqual(self.verify(value).state, State.UNRESOLVED)
                self.assertEqual(self.ledger.recovered_cash(), {"USD": 0})

    def test_unknown_and_malformed_statuses_map_to_unresolved(self):
        self.sent()
        for status in ("FUTURE_STATUS", None, {}, []):
            with self.subTest(status=status):
                self.assertEqual(self.verify(self.provider_invoice(status)).state, State.UNRESOLVED)
                self.assertEqual(self.ledger.recovered_cash(), {"USD": 0})

    def test_timeout_preserves_unverified_and_verified_state_without_any_write(self):
        self.sent()
        verifier = VerificationService(self.ledger, self.api)
        for paid in (False, True):
            if paid:
                self.verify(self.provider_invoice("PAID", paid="12.00"))
            before = self.ledger.verify_integrity()
            self.fake.steps += [ProviderTimeout(), ProviderTimeout(), ProviderTimeout()]
            with self.assertRaises(ProviderTimeout):
                verifier.verify(self.entry.entry_id)
            self.assertEqual(self.ledger.verify_integrity(), before)
            self.assertEqual(self.ledger.recovered_cash(), {"USD": 1200 if paid else 0})

    def test_refund_removes_entry_from_total_without_double_subtraction(self):
        self.sent()
        self.verify(self.provider_invoice("PAID", paid="12.00"))
        value = self.provider_invoice("REFUNDED", paid="12.00")
        value["refunds"] = {"refund_amount": {"currency_code": "USD", "value": "12.00"}}
        result = self.verify(value)
        self.assertEqual(result.state, State.REFUNDED)
        self.assertEqual(self.ledger.recovered_cash(), {"USD": 0})
        self.assertEqual(self.verify(value).sequence, result.sequence)

    def test_no_false_completed_status_from_untrusted_inputs_or_forged_proof(self):
        self.sent()
        verifier = VerificationService(self.ledger, self.api)
        checkpoint = self.ledger.verify_integrity()
        for source in ("redirect", "client", "ai", "webhook"):
            with self.subTest(source=source), self.assertRaises(TypeError):
                verifier.verify(self.entry.entry_id, status="PAID", source=source)
        for proof in ({"actor": "verification_service", "status": "PAID"}, object(), None):
            with self.assertRaises(IllegalTransition):
                self.ledger._store._commit_verification(proof)
        self.assertEqual(self.ledger.verify_integrity(), checkpoint)

    def test_observation_is_single_use_and_expires(self):
        self.sent()
        captured = []
        with patch.object(self.ledger._store, "_commit_verification", side_effect=captured.append):
            self.verify(self.provider_invoice("PAID", paid="12.00"))
        self.ledger._store._commit_verification(captured[0])
        with self.assertRaises(IllegalTransition):
            self.ledger._store._commit_verification(captured[0])
        with patch.object(self.ledger._store, "_commit_verification", side_effect=captured.append):
            self.verify(self.provider_invoice("PAID", paid="12.00"))
        with patch("backend.app.payments.verification.time.monotonic", return_value=10**12):
            with self.assertRaises(IllegalTransition):
                self.ledger._store._commit_verification(captured[-1])

    def test_stale_observation_cannot_overwrite_newer_verified_payment(self):
        self.sent()
        captured = []
        with patch.object(self.ledger._store, "_commit_verification", side_effect=captured.append):
            self.verify(self.provider_invoice("PAYMENT_PENDING"))
            self.verify(self.provider_invoice("PAID", paid="12.00"))
        self.ledger._store._commit_verification(captured[1])
        checkpoint = self.ledger.verify_integrity()
        with self.assertRaises(SequenceConflict):
            self.ledger._store._commit_verification(captured[0])
        self.assertEqual(self.ledger.verify_integrity(), checkpoint)
        self.assertEqual(self.ledger.recovered_cash(), {"USD": 1200})

    def test_malformed_oauth_is_not_an_invoice_observation(self):
        self.sent()
        self.verify(self.provider_invoice("PAID", paid="12.00"))
        checkpoint = self.ledger.verify_integrity()
        for body in (b"broken", b"{}", b'{"token_type":"Bearer","expires_in":3600}', b"x" * 1_048_577):
            self.api._token = None
            self.fake.steps += [Response(200, body)]
            before = len(self.fake.calls)
            with self.assertRaises(AuthError):
                VerificationService(self.ledger, self.api).verify(self.entry.entry_id)
            self.assertEqual(len(self.fake.calls), before + 1)
            self.assertEqual(self.fake.calls[-1][1], "/v1/oauth2/token")
            self.assertEqual(self.ledger.verify_integrity(), checkpoint)
            self.assertEqual(self.ledger.recovered_cash(), {"USD": 1200})

    def test_terminal_inconsistency_requires_review_without_reopening(self):
        self.sent()
        self.verify(self.provider_invoice("CANCELLED"))
        checkpoint = self.ledger.verify_integrity()
        for value in (self.provider_invoice("FUTURE_STATUS"), self.provider_invoice(None),
                      self.provider_invoice("PAID", paid="12.00")):
            with self.assertRaises(RecoveryRequired):
                self.verify(value)
            self.assertEqual(self.ledger.verify_integrity(), checkpoint)
            self.assertEqual(self.ledger.get(self.entry.entry_id).state, State.CANCELLED)
        self.assertEqual(self.ledger.recovered_cash(), {"USD": 0})

    def test_refunded_entry_cannot_be_reopened_by_paid_response(self):
        self.sent()
        self.verify(self.provider_invoice("PAID", paid="12.00"))
        self.verify(self.provider_invoice("REFUNDED", paid="12.00"))
        checkpoint = self.ledger.verify_integrity()
        with self.assertRaises(RecoveryRequired):
            self.verify(self.provider_invoice("PAID", paid="12.00"))
        self.assertEqual(self.ledger.verify_integrity(), checkpoint)
        self.assertEqual(self.ledger.recovered_cash(), {"USD": 0})

    def test_freshness_is_checked_after_transaction_wait(self):
        self.sent()
        captured = []
        clock_path = "backend.app.payments.verification.time.monotonic"
        with patch(clock_path, return_value=100), patch.object(self.ledger._store, "_commit_verification", side_effect=captured.append):
            self.verify(self.provider_invoice("PAID", paid="12.00"))
        checkpoint = self.ledger.verify_integrity()
        original = self.ledger._store._transaction

        @contextmanager
        def delayed_transaction(**kwargs):
            with original(**kwargs) as connection, patch(clock_path, return_value=131):
                yield connection

        with patch(clock_path, return_value=100), patch.object(self.ledger._store, "_transaction", delayed_transaction):
            with self.assertRaises(IllegalTransition):
                self.ledger._store._commit_verification(captured[0])
        self.assertEqual(self.ledger.verify_integrity(), checkpoint)
