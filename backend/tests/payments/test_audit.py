import io
import json
import logging
import unittest
from uuid import uuid4

from backend.app.ledger.models import State
from backend.app.payments.audit import AuditEvent, SafePaymentLogFilter, log_event, make_payment_logger


class AuditTests(unittest.TestCase):
    def test_only_explicit_event_and_state_are_emitted(self):
        output = io.StringIO()
        logger = make_payment_logger(output)
        log_event(logger, AuditEvent.VERIFICATION_COMPLETED, state=State.VERIFIED_PAID)
        self.assertIn("PAYMENT_VERIFICATION_COMPLETED state=VERIFIED_PAID", output.getvalue())
        self.assertFalse(logger.propagate)

    def test_free_text_arguments_exception_and_extra_fields_are_discarded(self):
        sentinel = uuid4().hex
        output = io.StringIO()
        logger = make_payment_logger(output)
        try:
            raise RuntimeError(sentinel)
        except RuntimeError:
            logger.exception("Authorization: %s", sentinel, extra={"body": {"payer": sentinel}, "secret": sentinel}, stack_info=True)
        self.assertIn("PAYMENT_LOG_REDACTED", output.getvalue())
        self.assertNotIn(sentinel, output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())

    def test_structured_record_drops_all_unapproved_fields_without_formatting_them(self):
        class Unprintable:
            def __str__(self):
                raise AssertionError("Must never format untrusted content")

        record = logging.LogRecord("private-name", logging.ERROR, "private-path", 1, Unprintable(), (Unprintable(),), None)
        record.secret = "private-extra"
        record.payment_event = AuditEvent.OPERATION_FAILED
        record.payment_state = "private-state"
        SafePaymentLogFilter().filter(record)
        self.assertEqual(record.getMessage(), "PAYMENT_OPERATION_FAILED")
        self.assertNotIn("private-", json.dumps(record.__dict__))
        self.assertNotIn("secret", record.__dict__)

    def test_untrusted_labels_are_rejected(self):
        logger = make_payment_logger(io.StringIO())
        for event, state in (("PAYMENT_INVOICE_SENT", None), (AuditEvent.INVOICE_SENT, "INVOICE_SENT")):
            with self.assertRaises(ValueError):
                log_event(logger, event, state=state)
