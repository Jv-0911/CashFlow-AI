"""Scripted offline transport. Tokens/credentials are generated and redacted."""
import json
from uuid import uuid4

from backend.app.payments.config import PaymentConfig
from backend.app.payments.paypal_client import PayPalClient, Response

INVOICE_ID = "INV2-DEMO-0000-0000-0001"


def response(value, status=200):
    return Response(status, json.dumps(value).encode())


def oauth():
    return response({"access_token": uuid4().hex, "token_type": "Bearer", "expires_in": 3600})


def invoice(status="SENT", *, number="CF" + "A" * 23, reference="entry_demo", value="12.00", currency="USD", paid=None, payment_type="PAYPAL"):
    result = {"id": INVOICE_ID, "status": status,
              "detail": {"currency_code": currency, "invoice_number": number, "reference": reference,
                         "metadata": {"recipient_view_url": "https://www.sandbox.paypal.com/invoice/p/#DEMO"}},
              "amount": {"currency_code": currency, "value": value}}
    result["primary_recipients"] = [{"billing_info": {"email_address": "demo-payer@example.test"}}]
    if paid is not None:
        result["payments"] = {"paid_amount": {"currency_code": currency, "value": paid},
                              "transactions": [{"type": payment_type, "payment_id": "TXNDEMO1", "method": "PAYPAL",
                                                "amount": {"currency_code": currency, "value": paid}}]}
        result["due_amount"] = {"currency_code": currency, "value": "0.00" if status == "PAID" else "6.00"}
    return result


class ScriptedTransport:
    def __init__(self, *steps):
        self.steps = list(steps)
        self.calls = []

    def request(self, method, path, headers, body, timeout_seconds):
        public_headers = {key: value for key, value in headers.items() if key != "Authorization"}
        self.calls.append((method, path, public_headers, body if path != "/v1/oauth2/token" else None))
        if not self.steps:
            raise AssertionError("Unexpected provider call")
        step = self.steps.pop(0)
        if isinstance(step, Exception):
            raise step
        return step(method, path, public_headers, body) if callable(step) else step


def client(*steps, **kwargs):
    transport = ScriptedTransport(*steps)
    config = PaymentConfig(client_id=uuid4().hex, client_secret=uuid4().hex, webhook_id="WEBHOOKDEMO")
    return PayPalClient(config, transport=transport, sleep=lambda _: None, **kwargs), transport
