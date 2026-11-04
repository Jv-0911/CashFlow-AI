"""Composition root for Member 4's authenticated application startup."""

from dataclasses import dataclass

from ..ledger.service import LedgerService
from .config import PaymentConfig
from .invoice_service import InvoiceService
from .paypal_client import PayPalClient
from .reconciliation import ReconciliationService
from .verification import VerificationService
from .webhooks import WebhookHandler


@dataclass(frozen=True, slots=True)
class PaymentRuntime:
    ledger: LedgerService
    invoices: InvoiceService
    verification: VerificationService
    reconciliation: ReconciliationService
    webhooks: WebhookHandler

    @classmethod
    def from_env(cls, recipient_resolver, *, env=None):
        config = PaymentConfig.from_env(env)
        ledger = LedgerService(config.db_path)
        client = PayPalClient(config)
        invoices = InvoiceService(ledger, client, recipient_resolver)
        return cls(ledger, invoices, VerificationService(ledger, client),
                   ReconciliationService(ledger, client, invoices), WebhookHandler(ledger, client))
