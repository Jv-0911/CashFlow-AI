"""Opt-in offline tests against installed, unchanged Member 1 and 2 modules.

Run in the assembled Linux checkout with its declared dependencies:
python -B -m backend.tests.payments.team_compatibility
Not part of standalone discovery: Member 3 has no forecast/AI dependencies.
"""
from datetime import date, timedelta
import unittest

from backend.app.forecast import (
    CashForecastRequest, DailyHistory, ScheduledCashEvent,
    VerifiedOpeningBalance, forecast_cash_flow,
)
from backend.app.rescue_ai.fallback import analyze_fallback
from backend.app.rescue_ai.schemas import InvoiceEvidence, RescueAnalysisRequest
from backend.app.payments.evidence_exports import forecast_event, rescue_invoice
from backend.tests.payments import test_evidence_exports as fixtures
from backend.tests.payments.run_tests import test_environment


class TeamCompatibilityTests(unittest.TestCase):
    setUp = fixtures.EvidenceExportTests.setUp
    approve = fixtures.EvidenceExportTests.approve
    provider_invoice = fixtures.EvidenceExportTests.provider_invoice
    draft = fixtures.EvidenceExportTests.draft
    sent = fixtures.EvidenceExportTests.sent
    observe = fixtures.EvidenceExportTests.observe
    start = date(2026, 10, 15)

    def forecast(self, *events):
        return forecast_cash_flow(CashForecastRequest(
            history=DailyHistory(currency='USD', days=()),
            opening_balance=VerifiedOpeningBalance(balance_cents=1000, currency='USD',
                balance_date=self.start, evidence_id='synthetic_bank_snapshot'),
            forecast_start_date=self.start, forecast_horizon_days=2,
            safety_reserve_cents=5000,
            known_events=tuple(ScheduledCashEvent.model_validate(item) for item in events),
        ))

    def rescue(self, forecast):
        # The forecast-to-AI mapping is a test fixture, not a new shared API.
        invoice = InvoiceEvidence.model_validate(rescue_invoice(
            self.ledger, self.entry.entry_id, due_date=self.start - timedelta(days=1)))
        request = RescueAnalysisRequest.model_validate({
            'as_of_date': self.start, 'forecast_id': forecast.forecast_id,
            'forecast': {'currency': forecast.currency,
                'safety_reserve_cents': forecast.safety_reserve_cents,
                'first_reserve_breach_date': forecast.first_reserve_breach_date,
                'days': [{'date': day.date, 'opening_balance_cents': day.opening_balance_cents,
                          'receipts_cents': day.projected_receipts_cents,
                          'expenses_cents': day.projected_payments_cents,
                          'closing_balance_cents': day.projected_closing_balance_cents}
                         for day in forecast.days],
                'is_demo': True},
            'invoices': [invoice.model_dump()],
        })
        return analyze_fallback(request)

    def event(self):
        return forecast_event(self.ledger, self.entry.entry_id, expected_date=self.start,
                              projection_assumption='Assume collection on the planned date.')

    def test_unpaid_invoice_can_be_projected_and_recommended_without_recovered_cash(self):
        self.sent()
        self.observe()
        checkpoint, calls = self.ledger.verify_integrity(), len(self.fake.calls)
        forecast = self.forecast(self.event())
        self.assertEqual(forecast.days[0].projected_receipts_cents, 1200)
        self.assertFalse(forecast.risk_assessment_complete)
        result = self.rescue(forecast)
        self.assertTrue(result.recommended_actions)
        self.assertTrue(all(action.requires_approval for action in result.recommended_actions))
        self.assertIn(self.entry.entry_id, result.evidence_ids)
        self.assertEqual(self.ledger.recovered_cash(), {'USD': 0})
        self.assertEqual(self.ledger.verify_integrity(), checkpoint)
        self.assertEqual(len(self.fake.calls), calls)

    def test_missing_collection_plan_is_excluded_by_actual_forecast_engine(self):
        self.sent()
        self.observe()
        event = forecast_event(self.ledger, self.entry.entry_id, due_date=self.start)
        result = self.forecast(event)
        self.assertTrue(all(day.projected_receipts_cents == 0 for day in result.days))
        self.assertFalse(result.reconciliation.event_dispositions[0].included)

    def test_paid_invoice_is_not_added_again_or_recommended_for_collection(self):
        self.sent()
        self.observe('PAID', paid='12.00')
        checkpoint = self.ledger.verify_integrity()
        result = self.forecast(self.event())
        self.assertTrue(all(day.projected_receipts_cents == 0 for day in result.days))
        self.assertTrue(all(day.projected_closing_balance_cents == 1000 for day in result.days))
        self.assertFalse(result.reconciliation.event_dispositions[0].included)
        self.assertFalse(self.rescue(result).recommended_actions)
        self.assertEqual(self.ledger.recovered_cash(), {'USD': 1200})
        self.assertEqual(self.ledger.verify_integrity(), checkpoint)

    def test_pending_remains_conditional_and_does_not_become_a_collection_action(self):
        self.sent()
        self.observe('PAYMENT_PENDING')
        result = self.forecast(self.event())
        self.assertEqual(result.days[0].projected_receipts_cents, 1200)
        self.assertFalse(self.rescue(result).recommended_actions)
        self.assertEqual(self.ledger.recovered_cash(), {'USD': 0})

    def test_duplicate_invoice_event_is_rejected_by_actual_forecast_engine(self):
        self.sent()
        self.observe()
        before = self.ledger.verify_integrity()
        with self.assertRaises(ValueError):
            self.forecast(self.event(), self.event())
        self.assertEqual(self.ledger.verify_integrity(), before)


if __name__ == '__main__':
    with test_environment(sandbox=False):
        unittest.main(verbosity=2)
