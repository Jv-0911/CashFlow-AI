"""Immutable environment configuration and exact Sandbox destination guard."""

from dataclasses import dataclass, field
import os
import re

from .errors import ConfigurationError

SANDBOX_BASE_URL = "https://api-m.sandbox.paypal.com"
SANDBOX_HOST = "api-m.sandbox.paypal.com"


@dataclass(frozen=True, slots=True)
class PaymentConfig:
    client_id: str = field(repr=False)
    client_secret: str = field(repr=False)
    mode: str = "sandbox"
    timeout_seconds: int = 10
    max_invoice_cents: int = 1_000_000
    allowed_currencies: tuple[str, ...] = ("USD",)
    webhook_id: str | None = field(default=None, repr=False)
    db_path: str = "./data/ledger.db"

    def __post_init__(self):
        if self.mode != "sandbox":
            raise ConfigurationError()
        for credential in (self.client_id, self.client_secret):
            if type(credential) is not str or not 1 <= len(credential) <= 2048 or not credential.isascii() or any(c.isspace() for c in credential):
                raise ConfigurationError()
        if type(self.timeout_seconds) is not int or not 1 <= self.timeout_seconds <= 30:
            raise ConfigurationError()
        if type(self.max_invoice_cents) is not int or not 1 <= self.max_invoice_cents <= 2**63 - 1:
            raise ConfigurationError()
        if self.allowed_currencies != ("USD",):
            raise ConfigurationError()
        if self.webhook_id is not None and (type(self.webhook_id) is not str or re.fullmatch(r"[A-Za-z0-9]{1,50}", self.webhook_id) is None):
            raise ConfigurationError()
        if type(self.db_path) is not str or not self.db_path or self.db_path == ":memory:":
            raise ConfigurationError()

    @classmethod
    def from_env(cls, env=None):
        source = os.environ if env is None else env
        for key, value in source.items():
            if key.startswith("PAYPAL_") and (key.endswith("URL") or key.endswith("HOST")):
                if value != (SANDBOX_HOST if key.endswith("HOST") else SANDBOX_BASE_URL):
                    raise ConfigurationError()
        try:
            return cls(client_id=source.get("PAYPAL_CLIENT_ID", ""),
                       client_secret=source.get("PAYPAL_CLIENT_SECRET", ""),
                       mode=source.get("PAYPAL_MODE", ""),
                       timeout_seconds=int(source.get("PAYPAL_HTTP_TIMEOUT_SECONDS", "10")),
                       max_invoice_cents=int(source.get("PAYMENTS_MAX_INVOICE_CENTS", "1000000")),
                       allowed_currencies=tuple(source.get("PAYMENTS_ALLOWED_CURRENCIES", "USD").split(",")),
                       webhook_id=source.get("PAYPAL_WEBHOOK_ID") or None,
                       db_path=source.get("LEDGER_DB_PATH", "./data/ledger.db"))
        except (ValueError, TypeError):
            raise ConfigurationError() from None
