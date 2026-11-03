"""Loopback-only browser fixture. Fake provider exists only in the test package."""
import argparse
import json
import os
from pathlib import Path
import socket
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--authenticated', action='store_true')
    args = parser.parse_args()
    # Ignore real credentials and integrations in the developer's shell.
    for name in tuple(os.environ):
        if name.startswith(('PAYPAL_', 'AI_', 'CASHFLOW_')):
            os.environ.pop(name)
    from backend.app.api.app import create_app
    from backend.app.api.security import Settings
    from backend.app.ledger.service import LedgerService
    from backend.app.payments.config import PaymentConfig
    from backend.app.payments.paypal_client import PayPalClient, Response
    from backend.app.payments.invoice_service import InvoiceService
    from backend.app.payments.runtime import PaymentRuntime
    from backend.app.payments.verification import VerificationService
    from backend.app.payments.reconciliation import ReconciliationService
    from backend.app.payments.webhooks import WebhookHandler
    from backend.tests.payments.fakes import invoice, oauth, response
    import uvicorn

    class BrowserTransport:
        def __init__(self):
            self.detail = None
            self.state = 'DRAFT'
            self.observations = 0

        def request(self, method, path, headers, body, timeout_seconds):
            if path == '/v1/oauth2/token':
                return oauth()
            if method == 'POST' and path == '/v2/invoicing/invoices':
                if self.detail is not None:
                    raise AssertionError('Duplicate provider create')
                self.detail = json.loads(body)['detail']
                return response(self.document(), 201)
            if method == 'POST' and path.endswith('/send'):
                self.state = 'SENT'
                return Response(202, b'')
            if method == 'GET' and self.detail is not None:
                if self.state == 'SENT':
                    self.observations += 1
                    if self.observations >= 2:
                        self.state = 'PAID'
                return response(self.document())
            raise AssertionError('Unexpected fake provider request')

        def document(self):
            status = 'PAYMENT_PENDING' if self.state == 'SENT' and self.observations == 1 else self.state
            return invoice(status, value='3200.00',
                paid='3200.00' if self.state == 'PAID' else None,
                number=self.detail['invoice_number'], reference=self.detail['reference'])

    def blocked(*args, **kwargs):
        raise AssertionError('Outbound connections are disabled in browser tests')

    with TemporaryDirectory(prefix='cashflow-browser-') as directory:
        ledger = LedgerService(Path(directory)/'ledger.db')
        runtime = None
        if args.authenticated:
            api = PayPalClient(PaymentConfig(client_id=uuid4().hex, client_secret=uuid4().hex), transport=BrowserTransport())
            invoices = InvoiceService(ledger, api, lambda ref: 'demo-payer@example.test')
            runtime = PaymentRuntime(ledger, invoices, VerificationService(ledger, api),
                ReconciliationService(ledger, api, invoices), WebhookHandler(ledger, api))
        settings = Settings(password='e2e-only-'+args.run_id if args.authenticated else '',
            origin=f'http://127.0.0.1:{args.port}', db_path=str(Path(directory)/'ledger.db'),
            reconciliation_seconds=3600)
        app = create_app(settings, ledger=ledger, payments=runtime)
        with patch.object(socket, 'create_connection', blocked):
            uvicorn.run(app, host='127.0.0.1', port=args.port, access_log=False, log_level='warning')


if __name__ == '__main__':
    main()
