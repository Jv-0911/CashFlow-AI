from dataclasses import FrozenInstanceError
from decimal import localcontext
import random
import unittest
from uuid import uuid4

from backend.app.payments.config import PaymentConfig, SANDBOX_BASE_URL
from backend.app.payments.errors import ConfigurationError, InvalidRequest, MalformedResponse
from backend.app.payments.money import cents_to_paypal, paypal_to_cents, validate_money


def config_fixture(**overrides):
    return PaymentConfig(client_id=uuid4().hex, client_secret=uuid4().hex, **overrides)


class ConfigMoneyTests(unittest.TestCase):
    def test_env_requires_sandbox_credentials_and_exact_host(self):
        env = {"PAYPAL_CLIENT_ID": uuid4().hex, "PAYPAL_CLIENT_SECRET": uuid4().hex, "PAYPAL_MODE": "sandbox"}
        self.assertEqual(PaymentConfig.from_env(env).mode, "sandbox")
        for key, value in (("PAYPAL_MODE", "live"), ("PAYPAL_MODE", "SANDBOX"),
                           ("PAYPAL_MODE", ""), ("PAYPAL_CLIENT_SECRET", ""),
                           ("PAYPAL_BASE_URL", "https://api-m.paypal.com"),
                           ("PAYPAL_API_HOST", "api-m.sandbox.paypal.com.evil.test"),
                           ("PAYPAL_BASE_URL", SANDBOX_BASE_URL + "/"),
                           ("PAYMENTS_ALLOWED_CURRENCIES", "JPY")):
            with self.subTest(key=key, value=value), self.assertRaises(ConfigurationError):
                PaymentConfig.from_env(env | {key: value})
        with self.assertRaises(ConfigurationError):
            PaymentConfig.from_env({})

    def test_config_is_immutable_and_repr_has_no_credentials(self):
        config = config_fixture()
        self.assertNotIn(config.client_id, repr(config))
        self.assertNotIn(config.client_secret, repr(config))
        with self.assertRaises(FrozenInstanceError):
            config.mode = "live"

    def test_limits_are_validated(self):
        for fields in ({"timeout_seconds": 0}, {"timeout_seconds": True}, {"timeout_seconds": 31},
                       {"max_invoice_cents": 0}, {"max_invoice_cents": 2**63},
                       {"allowed_currencies": ("USD", "EUR")}):
            with self.subTest(fields=fields), self.assertRaises(ConfigurationError):
                config_fixture(**fields)

    def test_money_roundtrips_and_ignores_ambient_decimal_precision(self):
        rng = random.Random(1013)
        with localcontext() as context:
            context.prec = 2
            for amount in [1, 99, 100, 101, 2**63 - 1] + [rng.randrange(1, 2**63) for _ in range(1000)]:
                text = cents_to_paypal(amount, maximum=2**63 - 1)
                self.assertEqual(paypal_to_cents(text, "USD"), amount)

    def test_money_rejects_invalid_requests(self):
        for amount in (True, False, 0, -1, 1.1, "100", None, 1_000_001):
            with self.subTest(amount=amount), self.assertRaises(InvalidRequest):
                cents_to_paypal(amount)
        for currency in ("usd", "EUR", "JPY", None):
            with self.subTest(currency=currency), self.assertRaises(InvalidRequest):
                validate_money(100, currency)

    def test_decimal_parser_is_strict(self):
        for value in ("1.001", "1e2", "NaN", "Infinity", "-1.00", "+1", " 1", "01.00", "1.", ".01", "0", 1.25, True, "9" * 100):
            with self.subTest(value=value), self.assertRaises(MalformedResponse):
                paypal_to_cents(value, "USD")
        self.assertEqual(paypal_to_cents("0.00", "USD", allow_zero=True), 0)
        self.assertEqual(paypal_to_cents("1.2", "USD"), 120)

    def test_money_is_independent_of_ambient_exponent_limits_and_traps(self):
        with localcontext() as context:
            context.Emax = 2
            context.Emin = -2
            for signal in context.traps:
                context.traps[signal] = True
            self.assertEqual(cents_to_paypal(999999), "9999.99")
            self.assertEqual(paypal_to_cents("9999.99", "USD"), 999999)

    def test_money_options_are_strictly_typed(self):
        for maximum in (True, 1.0, "100", None):
            with self.subTest(maximum=maximum), self.assertRaises(InvalidRequest):
                validate_money(1, "USD", maximum=maximum)
        for allow_zero in (1, "true", None):
            with self.subTest(allow_zero=allow_zero), self.assertRaises(MalformedResponse):
                paypal_to_cents("0", "USD", allow_zero=allow_zero)
