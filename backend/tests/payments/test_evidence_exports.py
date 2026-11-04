from datetime import date, datetime
import json
from unittest.mock import patch
import unittest

from backend.app.ledger.errors import IntegrityViolation
from backend.app.payments.errors import InvalidRequest, ProviderRejected
from backend.app.payments.evidence_exports import (
    EvidenceUnavailable, forecast_event, rescue_invoice,
)
from backend.app.payments.verification import VerificationService
from backend.tests.payments import test_invoice_service as fixtures
from backend.tests.payments.fakes import oauth, response


class EvidenceExportTests(unittest.TestCase):
    setUp = fixtures.InvoiceServiceTests.setUp
    approve = fixtures.InvoiceServiceTests.approve
    provider_invoice = fixtures.InvoiceServiceTests.provider_invoice
    draft = fixtures.InvoiceServiceTests.draft
    sent = fixtures.InvoiceServiceTests.sent
    due = date(2026, 10, 15)

    def observe(self, status='SENT', **kwargs):
        value = self.provider_invoice(status, **kwargs)
        if status in {'SENT', 'PAYMENT_PENDING'} and 'paid' not in kwargs:
            value['due_amount'] = {'currency_code': 'USD', 'value': '12.00'}
        self.fake.steps.append(response(value))
        return VerificationService(self.ledger, self.api).verify(self.entry.entry_id)

    def exports(self):
        return (forecast_event(self.ledger, self.entry.entry_id),
                rescue_invoice(self.ledger, self.entry.entry_id, due_date=self.due))

    def test_proposal_approval_and_draft_are_not_invoice_balance_evidence(self):
        def rejected():
            for export in (lambda: forecast_event(self.ledger, self.entry.entry_id),
                           lambda: rescue_invoice(self.ledger, self.entry.entry_id, due_date=self.due)):
                with self.assertRaises(EvidenceUnavailable):
                    export()
        rejected()
        self.approve()
        rejected()
        self.fake.steps += [oauth(), response(self.provider_invoice(), 201)]
        self.service.create_draft(self.entry.entry_id, idempotency_key='create')
        rejected()

    def test_send_ack_requires_an_observed_outstanding_balance(self):
        self.sent()
        with self.assertRaises(EvidenceUnavailable):
            self.exports()
        self.observe()
        before, calls = self.ledger.verify_integrity(), len(self.fake.calls)
        event, invoice = self.exports()
        self.assertEqual(event['status'], 'invoice_unpaid')
        self.assertIsNone(event['expected_date'])
        self.assertIsNone(event['verification_evidence_id'])
        self.assertEqual(invoice['status'], 'unpaid')
        self.assertEqual(invoice['outstanding_amount_cents'], 1200)
        self.assertEqual(event['event_id'], invoice['invoice_id'])
        self.assertEqual(event['source_id'], self.entry.entry_id)
        self.assertEqual(self.ledger.recovered_cash(), {'USD': 0})
        self.assertEqual(self.ledger.verify_integrity(), before)
        self.assertEqual(len(self.fake.calls), calls)
        self.assertNotIn('email', json.dumps([event, invoice]))
        self.assertNotIn('recipient', json.dumps([event, invoice]))

    def test_due_date_is_not_assumed_to_be_collection_date(self):
        self.sent()
        self.observe()
        event = forecast_event(self.ledger, self.entry.entry_id, due_date=self.due)
        self.assertEqual(event['due_date'], '2026-10-15')
        self.assertIsNone(event['expected_date'])
        self.assertIsNone(event['projection_assumption'])
        event = forecast_event(self.ledger, self.entry.entry_id, expected_date=self.due,
                               projection_assumption='Assume collection on the planned date.')
        self.assertEqual(event['expected_date'], '2026-10-15')
        self.assertEqual(self.ledger.recovered_cash(), {'USD': 0})

    def test_pending_is_only_projected_and_paid_has_ledger_verification_evidence(self):
        self.sent()
        self.observe('PAYMENT_PENDING')
        event, invoice = self.exports()
        self.assertEqual((event['status'], invoice['status']), ('pending_verification', 'pending'))
        self.assertEqual(self.ledger.recovered_cash(), {'USD': 0})
        paid = self.observe('PAID', paid='12.00')
        event, invoice = self.exports()
        self.assertEqual((event['status'], invoice['status']), ('verified_completed', 'paid'))
        self.assertEqual(event['verification_evidence_id'], paid.events[-1].event_id)
        self.assertEqual(invoice['outstanding_amount_cents'], 0)
        self.assertEqual(self.ledger.recovered_cash(), {'USD': 1200})

    def test_partial_offline_unknown_and_refund_are_not_forced_into_peer_states(self):
        self.sent()
        for status, kwargs in [('PARTIALLY_PAID', {'paid': '6.00'}),
                               ('MARKED_AS_PAID', {}), ('FUTURE_STATUS', {}),
                               ('PAID', {'paid': '12.00'}), ('REFUNDED', {})]:
            self.observe(status, **kwargs)
            if status == 'PAID':
                continue
            for export in (lambda: forecast_event(self.ledger, self.entry.entry_id),
                           lambda: rescue_invoice(self.ledger, self.entry.entry_id, due_date=self.due)):
                with self.assertRaises(EvidenceUnavailable):
                    export()

    def test_missing_or_partial_outstanding_evidence_is_not_assumed_fully_unpaid(self):
        self.sent()
        for value in (self.provider_invoice('SENT'), self.provider_invoice('PAYMENT_PENDING', paid='6.00')):
            self.fake.steps.append(response(value))
            VerificationService(self.ledger, self.api).verify(self.entry.entry_id)
            with self.assertRaises(EvidenceUnavailable):
                self.exports()

    def test_cancelled_forecast_is_excluded_without_inventing_rescue_balance(self):
        self.sent()
        self.observe('CANCELLED')
        self.assertEqual(forecast_event(self.ledger, self.entry.entry_id)['status'], 'cancelled')
        with self.assertRaises(EvidenceUnavailable):
            rescue_invoice(self.ledger, self.entry.entry_id, due_date=self.due)

    def test_definite_creation_failure_is_excluded_from_future_cash(self):
        self.approve()
        self.fake.steps += [oauth(), response({}, 422)]
        with self.assertRaises(ProviderRejected):
            self.service.create_draft(self.entry.entry_id, idempotency_key='create')
        before = self.ledger.verify_integrity()
        self.assertEqual(forecast_event(self.ledger, self.entry.entry_id)['status'], 'failed')
        with self.assertRaises(EvidenceUnavailable):
            rescue_invoice(self.ledger, self.entry.entry_id, due_date=self.due)
        self.assertEqual(self.ledger.verify_integrity(), before)

    def test_invalid_dates_and_assumptions_are_rejected_without_writes(self):
        before = self.ledger.verify_integrity()
        for value in (None, '2026-10-15', datetime(2026, 10, 15), 123):
            with self.assertRaises(InvalidRequest):
                rescue_invoice(self.ledger, self.entry.entry_id, due_date=value)
        for value in ('', 'x' * 501, 'injected\ntext', 100):
            with self.assertRaises(InvalidRequest):
                forecast_event(self.ledger, self.entry.entry_id, projection_assumption=value)
        self.assertEqual(self.ledger.verify_integrity(), before)

    def test_corruption_blocks_both_exports(self):
        with patch.object(self.ledger, 'get', side_effect=IntegrityViolation('Ledger integrity check failed.')):
            for export in (lambda: forecast_event(self.ledger, self.entry.entry_id),
                           lambda: rescue_invoice(self.ledger, self.entry.entry_id, due_date=self.due)):
                with self.assertRaises(IntegrityViolation):
                    export()

    def test_callers_cannot_supply_status_amount_or_verification_evidence(self):
        before = self.ledger.verify_integrity()
        for fields in ({'status': 'VERIFIED_PAID'}, {'amount_cents': 1200},
                       {'verification_evidence_id': 'ai_claim'}):
            with self.assertRaises(TypeError):
                forecast_event(self.ledger, self.entry.entry_id, **fields)
        self.assertEqual(self.ledger.verify_integrity(), before)
