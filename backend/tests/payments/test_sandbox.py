"""Explicit integration tests: skipped by default; never automate payer payment."""
import os
from pathlib import Path
import unittest
from uuid import uuid4

from backend.app.payments.config import PaymentConfig
from backend.app.payments.paypal_client import PayPalClient
from backend.app.payments.runtime import PaymentRuntime
from backend.app.ledger.models import State

try:
    import pytest
except ImportError:
    pytestmark = []
else:
    pytestmark = pytest.mark.sandbox


@unittest.skipUnless(os.environ.get("RUN_PAYPAL_SANDBOX_TESTS") == "1", "Sandbox integration is opt-in")
class SandboxTests(unittest.TestCase):
    sandbox = True

    def test_fetch_existing_sandbox_invoice(self):
        identity = os.environ.get("PAYPAL_SANDBOX_INVOICE_ID")
        if not identity:
            self.skipTest("Set an existing Sandbox invoice ID for a read-only check")
        result = PayPalClient(PaymentConfig.from_env()).get_invoice(identity)
        self.assertEqual(result.invoice_id, identity)

    def test_create_and_send_one_cent_approved_invoice(self):
        if os.environ.get("PAYPAL_SANDBOX_ALLOW_SEND") != "I_APPROVE_A_ONE_CENT_SANDBOX_INVOICE":
            self.skipTest("Explicit human approval is required to create and send")
        email = os.environ.get("PAYPAL_SANDBOX_PAYER_EMAIL")
        if not email:
            self.skipTest("Configure a Sandbox personal-account recipient locally")
        # Persistent path is mandatory: even integration runs retain the ledger.
        runtime = PaymentRuntime.from_env(lambda reference: email)
        nonce = uuid4().hex
        entry = runtime.ledger.propose(idempotency_key="sandbox_proposal_" + nonce, amount_cents=1, currency="USD")
        runtime.ledger.approve(entry.entry_id, idempotency_key="sandbox_approval_" + nonce,
                               expected_sequence=1, approved_by="sandbox_test_operator", payer_reference="sandbox_payer")
        runtime.invoices.create_draft(entry.entry_id, idempotency_key="sandbox_create_" + nonce)
        self.assertEqual(runtime.invoices.send(entry.entry_id, idempotency_key="sandbox_send_" + nonce).state, State.INVOICE_SENT)
        self.assertNotEqual(runtime.verification.verify(entry.entry_id).state, State.VERIFIED_PAID)

    def test_verify_operator_paid_existing_entry(self):
        entry_id = os.environ.get("PAYPAL_SANDBOX_PAID_ENTRY_ID")
        if not entry_id:
            self.skipTest("Pay the Sandbox invoice manually and configure its existing ledger entry ID")
        runtime = PaymentRuntime.from_env(lambda reference: None)
        self.assertEqual(runtime.verification.verify(entry_id).state, State.VERIFIED_PAID)
        runtime.ledger.verify_integrity()
