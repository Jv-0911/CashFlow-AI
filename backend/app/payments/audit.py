"""Opt-in payment logging with an allowlist, not best-effort secret matching.

Attach the filter to every payment log HANDLER, including structured handlers.
It discards arbitrary messages, arguments, exceptions, stacks and extra fields.
It does not configure the shared application's root or HTTP access loggers.
"""
from enum import StrEnum
import logging

from ..ledger.models import State


class AuditEvent(StrEnum):
    APPROVAL_RECORDED = "PAYMENT_APPROVAL_RECORDED"
    INVOICE_CREATED = "PAYMENT_INVOICE_CREATED"
    INVOICE_SENT = "PAYMENT_INVOICE_SENT"
    VERIFICATION_COMPLETED = "PAYMENT_VERIFICATION_COMPLETED"
    OPERATION_FAILED = "PAYMENT_OPERATION_FAILED"
    REVIEW_REQUIRED = "PAYMENT_REVIEW_REQUIRED"


class SafePaymentLogFilter(logging.Filter):
    def filter(self, record):
        event = record.__dict__.get("payment_event")
        state = record.__dict__.get("payment_state")
        message = event.value if type(event) is AuditEvent else "PAYMENT_LOG_REDACTED"
        if type(event) is AuditEvent and type(state) is State:
            message += " state=" + state.value
        level = record.levelno if type(record.levelno) is int and record.levelno in {
            logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL
        } else logging.INFO
        safe = logging.LogRecord("cashflow.payments", level, "", 0, message, (), None)
        # Keep no caller-controlled source, thread name, exception or extras.
        safe.threadName = "payment"
        safe.processName = "payment"
        record.__dict__.clear()
        record.__dict__.update(safe.__dict__)
        return True


def make_payment_logger(stream):
    """Create an isolated logger; never modifies global logging configuration."""
    logger = logging.Logger("cashflow.payments", logging.INFO)
    logger.propagate = False
    handler = logging.StreamHandler(stream)
    handler.addFilter(SafePaymentLogFilter())
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


def log_event(logger, event: AuditEvent, *, state: State | None = None):
    if type(event) is not AuditEvent or (state is not None and type(state) is not State):
        raise ValueError("Payment audit labels must be explicit enum values.")
    logger.info("payment", extra={"payment_event": event, "payment_state": state})
