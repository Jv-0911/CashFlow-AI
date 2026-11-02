"""The only PayPal decimal-string / integer-cent conversion boundary."""

from decimal import Context, Decimal, localcontext
import re

from .errors import InvalidRequest, MalformedResponse

MAX_STORAGE_CENTS = 2**63 - 1


def validate_money(cents: int, currency: str, *, maximum: int = 1_000_000) -> None:
    if (type(cents) is not int or type(maximum) is not int or not 0 < cents <= maximum <= MAX_STORAGE_CENTS
            or type(currency) is not str or currency != "USD"):
        raise InvalidRequest()


def cents_to_paypal(cents: int, currency: str = "USD", *, maximum: int = 1_000_000) -> str:
    validate_money(cents, currency, maximum=maximum)
    with localcontext(Context(prec=32)):
        return format(Decimal(cents) / Decimal(100), ".2f")


def paypal_to_cents(value: str, currency: str, *, allow_zero: bool = False) -> int:
    if (type(allow_zero) is not bool or type(value) is not str or len(value) > 22
            or re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?", value) is None
            or type(currency) is not str or currency != "USD"):
        raise MalformedResponse()
    with localcontext(Context(prec=32)):
        cents = int(Decimal(value) * Decimal(100))
    if not (0 if allow_zero else 1) <= cents <= MAX_STORAGE_CENTS:
        raise MalformedResponse()
    return cents
