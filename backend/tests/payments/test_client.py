import copy
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from backend.app.payments.config import SANDBOX_HOST
from backend.app.payments.errors import (AuthError, InvalidRequest, MalformedResponse,
                                         ProviderRejected, ProviderTimeout, ProviderUnavailable, RateLimited)
from backend.app.payments.paypal_client import MAX_RESPONSE_BYTES, Response, SandboxTransport
from backend.app.payments.schemas import parse_invoice, parse_json
from backend.tests.payments.fakes import INVOICE_ID, client, invoice, oauth, response


class ClientTests(unittest.TestCase):
    def test_oauth_cache_and_get(self):
        api, fake = client(oauth(), response(invoice()), response(invoice()))
        self.assertEqual(api.get_invoice(INVOICE_ID).total_cents, 1200)
        api.get_invoice(INVOICE_ID)
        self.assertEqual(len(fake.calls), 3)

    def test_expiring_token_is_refreshed(self):
        now = [0]
        api, fake = client(oauth(), response(invoice()), oauth(), response(invoice()), clock=lambda: now[0])
        api.get_invoice(INVOICE_ID)
        now[0] = 3590
        api.get_invoice(INVOICE_ID)
        self.assertEqual(len(fake.calls), 4)

    def test_one_401_refresh_then_failure(self):
        api, fake = client(oauth(), Response(401, b""), oauth(), Response(401, b""))
        with self.assertRaises(AuthError):
            api.get_invoice(INVOICE_ID)
        self.assertEqual(len(fake.calls), 4)

    def test_auth_failure(self):
        api, _ = client(Response(401, b"untrusted provider diagnostic"))
        with self.assertRaises(AuthError) as caught:
            api.get_invoice(INVOICE_ID)
        self.assertNotIn("diagnostic", str(caught.exception))

    def test_safe_calls_have_bounded_retries(self):
        for failure, expected in ((Response(429, b""), RateLimited), (Response(503, b""), ProviderUnavailable),
                                  (ProviderTimeout(), ProviderTimeout)):
            with self.subTest(expected=expected):
                api, fake = client(oauth(), failure, failure, failure)
                with self.assertRaises(expected):
                    api.get_invoice(INVOICE_ID)
                self.assertEqual(len(fake.calls), 4)

    def test_create_has_request_id_but_no_ambiguous_retry(self):
        request_id = str(uuid4())
        api, fake = client(oauth(), ProviderTimeout())
        with self.assertRaises(ProviderTimeout):
            api.create_invoice({}, request_id)
        self.assertEqual(len(fake.calls), 2)
        self.assertEqual(fake.calls[-1][2]["PayPal-Request-Id"], request_id)

    def test_successful_create_uses_representation_and_typed_response(self):
        api, fake = client(oauth(), response(invoice("DRAFT"), 201))
        result = api.create_invoice({}, str(uuid4()))
        self.assertEqual(result.status, "DRAFT")
        self.assertEqual(fake.calls[-1][2]["Prefer"], "return=representation")

    def test_unsafe_ids_and_routes_never_reach_transport(self):
        api, fake = client()
        for identity in ("https://api-m.paypal.com/x", "../x", INVOICE_ID + "?x=1", INVOICE_ID + "/send", "x\r\nHost: evil"):
            with self.subTest(identity=identity), self.assertRaises(InvalidRequest):
                api.get_invoice(identity)
        for path in ("https://api-m.paypal.com/x", "/v2/invoicing/invoices/" + INVOICE_ID + "/payments"):
            with self.assertRaises(InvalidRequest):
                api._api("POST", path)
        self.assertEqual(fake.calls, [])

    def test_redirects_and_unexpected_status_are_errors(self):
        for status in (301, 302, 307, 400, 403, 404, 422):
            api, _ = client(oauth(), *([Response(status, b"")] * 3))
            expected = ProviderUnavailable if status < 400 else ProviderRejected
            with self.subTest(status=status), self.assertRaises(expected):
                api.get_invoice(INVOICE_ID)

    def test_strict_json_and_body_limits(self):
        for body in (b'{"status":"PAID","status":"SENT"}', b'{"amount":NaN}', b'[]', b'null', b'broken'):
            with self.subTest(body=body), self.assertRaises(MalformedResponse):
                parse_json(body)
        api, _ = client(oauth(), Response(200, b"x" * (MAX_RESPONSE_BYTES + 1)))
        with self.assertRaises(MalformedResponse):
            api.get_invoice(INVOICE_ID)

    def test_unknown_and_malformed_status_never_normalized_to_paid(self):
        for status in (None, {}, [], 1, "FUTURE_STATUS", "paid"):
            with self.subTest(status=status):
                self.assertNotEqual(parse_invoice(invoice(status)).status, "PAID")

    def test_payment_types_are_separated_and_duplicates_rejected(self):
        self.assertEqual(parse_invoice(invoice("PAID", paid="12.00")).paypal_paid_cents, 1200)
        self.assertEqual(parse_invoice(invoice("PAID", paid="12.00", payment_type="EXTERNAL")).paypal_paid_cents, 0)
        value = invoice("PAID", paid="12.00")
        value["payments"]["transactions"] *= 2
        with self.assertRaises(MalformedResponse):
            parse_invoice(value)

    def test_bad_money_and_live_payer_url_rejected(self):
        for value in (12.0, True, "12.001"):
            with self.subTest(value=value), self.assertRaises(MalformedResponse):
                parse_invoice(invoice(value=value))
        value = invoice()
        value["detail"]["metadata"]["recipient_view_url"] = "https://www.paypal.com/invoice/p/#DEMO"
        with self.assertRaises(MalformedResponse):
            parse_invoice(value)

    def test_transport_pins_host_and_keeps_tls_verification_enabled(self):
        with patch("backend.app.payments.paypal_client.http.client.HTTPSConnection") as connection:
            instance = connection.return_value
            instance.getresponse.return_value.status = 302
            self.assertEqual(SandboxTransport().request("GET", "/v2/invoicing/invoices/" + INVOICE_ID,
                                                       {}, None, 10).status, 302)
            self.assertEqual(connection.call_args.args[0], SANDBOX_HOST)
            context = connection.call_args.kwargs["context"]
            self.assertTrue(context.check_hostname)
            import ssl
            self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
            instance.close.assert_called_once()

    def test_malformed_nested_invoice_fields_have_only_typed_errors(self):
        paths = [("detail",), ("amount",), ("detail", "metadata"), ("payments",),
                 ("refunds",), ("primary_recipients",), ("primary_recipients", 0),
                 ("primary_recipients", 0, "billing_info"), ("payments", "transactions"),
                 ("payments", "transactions", 0), ("payments", "transactions", 0, "type"),
                 ("payments", "transactions", 0, "amount")]
        for path in paths:
            for malformed in (None, True, 1, [], "invalid"):
                # Empty transaction lists are schema-valid, but cannot prove paid.
                if path == ("payments", "transactions") and malformed == []:
                    continue
                value = copy.deepcopy(invoice("PAID", paid="12.00"))
                target = value
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = malformed
                with self.subTest(path=path, malformed=malformed), self.assertRaises(MalformedResponse):
                    parse_invoice(value)
