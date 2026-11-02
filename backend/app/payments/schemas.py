"""Strict validation of the provider fields used as financial evidence.

Unconsumed PayPal fields are ignored, never persisted or logged. Consumed money,
identity and transaction fields are never coerced from numbers or booleans.
"""

from dataclasses import dataclass
import json
import hashlib
import re
from urllib.parse import urlsplit

from .errors import InvalidRequest, MalformedResponse
from .money import paypal_to_cents


def recipient_fingerprint(email):
    if (type(email) is not str or len(email) > 254 or not email.isascii()
            or re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}", email) is None):
        raise InvalidRequest()
    return hashlib.sha256(email.encode("ascii")).hexdigest()


def invoice_id(value: str) -> str:
    if type(value) is not str or re.fullmatch(r"INV2-[A-Z0-9]{4}(?:-[A-Z0-9]{4}){3}", value) is None:
        raise InvalidRequest()
    return value


def safe_invoice_url(value):
    if value is None:
        return None
    if type(value) is not str or len(value) > 2048 or any(ord(c) < 33 for c in value) or "\\" in value:
        raise MalformedResponse()
    try:
        url = urlsplit(value)
        if (url.scheme != "https" or url.hostname not in {"www.sandbox.paypal.com", "sandbox.paypal.com", "api-m.sandbox.paypal.com"}
                or url.username is not None or url.password is not None or url.port not in (None, 443)
                or not url.path.startswith("/invoice/")):
            raise MalformedResponse()
    except ValueError:
        raise MalformedResponse() from None
    return value


def parse_json(raw: bytes) -> dict:
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError
            result[key] = value
        return result
    def reject_constant(_):
        raise ValueError
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=object_pairs,
                           parse_constant=reject_constant)
        if type(value) is not dict:
            raise ValueError
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise MalformedResponse() from None


def _text(value, maximum):
    if type(value) is not str or not 1 <= len(value) <= maximum:
        raise MalformedResponse()
    return value


@dataclass(frozen=True, slots=True)
class Invoice:
    invoice_id: str
    status: str | None
    currency: str
    total_cents: int
    paid_cents: int
    paypal_paid_cents: int
    due_cents: int | None
    refund_cents: int
    invoice_number: str
    reference: str
    invoice_url: str | None
    transaction_ids: tuple[str, ...]
    recipient_fingerprint: str


def parse_invoice(value: dict) -> Invoice:
    try:
        identity = invoice_id(value["id"])
        detail = value["detail"]
        amount = value["amount"]
        currency = _text(amount["currency_code"], 3)
        if detail["currency_code"] != currency:
            raise MalformedResponse()
        total = paypal_to_cents(amount["value"], currency)
        number = _text(detail["invoice_number"], 25)
        reference = _text(detail["reference"], 128)
        recipients = value["primary_recipients"]
        if type(recipients) is not list or len(recipients) != 1:
            raise MalformedResponse()
        recipient_hash = recipient_fingerprint(recipients[0]["billing_info"]["email_address"])
        status = value.get("status")
        if type(status) is not str or re.fullmatch(r"[A-Za-z_]{1,64}", status) is None:
            status = None  # Missing/malformed statuses can never mean paid.
        metadata = detail.get("metadata", {})
        url = safe_invoice_url(metadata.get("recipient_view_url"))
        due = value.get("due_amount")
        due_cents = None
        if due is not None:
            if due["currency_code"] != currency:
                raise MalformedResponse()
            due_cents = paypal_to_cents(due["value"], currency, allow_zero=True)
        payments = value.get("payments", {})
        paid = payments.get("paid_amount")
        paid_cents = 0
        if paid is not None:
            if paid["currency_code"] != currency:
                raise MalformedResponse()
            paid_cents = paypal_to_cents(paid["value"], currency, allow_zero=True)
        rows = payments.get("transactions", [])
        if type(rows) is not list or len(rows) > 100:
            raise MalformedResponse()
        paypal_paid = 0
        transaction_total = 0
        ids = set()
        for row in rows:
            if row["type"] not in {"PAYPAL", "EXTERNAL"} or row["amount"]["currency_code"] != currency:
                raise MalformedResponse()
            row_amount = paypal_to_cents(row["amount"]["value"], currency)
            transaction_total += row_amount
            if row["type"] == "PAYPAL":
                payment_id = _text(row["payment_id"], 22)
                if re.fullmatch(r"[A-Za-z0-9_-]+", payment_id) is None or payment_id in ids:
                    raise MalformedResponse()
                ids.add(payment_id)
                paypal_paid += row_amount
        if rows and transaction_total != paid_cents:
            raise MalformedResponse()
        refund = value.get("refunds", {}).get("refund_amount")
        refund_cents = 0
        if refund is not None:
            if refund["currency_code"] != currency:
                raise MalformedResponse()
            refund_cents = paypal_to_cents(refund["value"], currency, allow_zero=True)
        return Invoice(identity, status, currency, total, paid_cents, paypal_paid,
                       due_cents, refund_cents, number, reference, url, tuple(sorted(ids)), recipient_hash)
    except (KeyError, TypeError, AttributeError, InvalidRequest):
        raise MalformedResponse() from None
