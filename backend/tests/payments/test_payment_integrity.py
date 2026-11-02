"""Adversarial storage checks; corruption SQL is confined to test databases."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import asdict
from pathlib import Path
import sqlite3
from threading import Barrier
import unittest

from backend.app.ledger.errors import IntegrityViolation
from backend.app.ledger.service import LedgerService
from backend.app.ledger.store import _digest
from backend.tests.payments import test_invoice_service as fixtures
from backend.tests.payments.fakes import INVOICE_ID


class PaymentIntegrityTests(unittest.TestCase):
    setUp = fixtures.InvoiceServiceTests.setUp
    approve = fixtures.InvoiceServiceTests.approve
    provider_invoice = fixtures.InvoiceServiceTests.provider_invoice
    draft = fixtures.InvoiceServiceTests.draft
    sent = fixtures.InvoiceServiceTests.sent

    def connection(self):
        return sqlite3.connect(Path(self.temp.name) / "ledger.db")

    def test_payment_tables_reject_updates_deletes_and_replacements(self):
        self.sent()
        self.ledger._store._claim_webhook("event_demo", INVOICE_ID)
        with closing(self.connection()) as connection:
            for table in ("payment_operations", "processed_webhook_events", "invoice_bindings"):
                with self.subTest(table=table):
                    column = connection.execute(f"PRAGMA table_info({table})").fetchone()[1]
                    for statement in (f"UPDATE {table} SET {column} = {column}",
                                      f"DELETE FROM {table}",
                                      f"INSERT OR REPLACE INTO {table} SELECT * FROM {table}"):
                        with self.assertRaises(sqlite3.IntegrityError):
                            connection.execute(statement)
                        connection.rollback()
        self.ledger.verify_integrity()

    def test_concurrent_webhook_receipts_have_one_winner_and_no_financial_write(self):
        self.sent()
        checkpoint = self.ledger.verify_integrity()
        path = Path(self.temp.name) / "ledger.db"
        stores = [LedgerService(path)._store for _ in range(4)]
        barrier = Barrier(4)

        def claim(store):
            barrier.wait()
            return store._claim_webhook("event_same", INVOICE_ID)[1]

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(claim, stores))
        self.assertEqual(results.count("claimed"), 1)
        self.assertEqual(results.count("duplicate"), 3)
        self.assertEqual(self.ledger.verify_integrity(), checkpoint)
        with closing(self.connection()) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM processed_webhook_events").fetchone()[0], 1)

    def test_receipt_chain_detects_altered_content_even_after_guard_restored(self):
        self.sent()
        self.ledger._store._claim_webhook("event_demo", INVOICE_ID)
        self.corrupt("processed_webhook_events", "provider_event_id = 'event_changed'")
        with self.assertRaises(IntegrityViolation):
            self.ledger.verify_integrity()
        with self.assertRaises(IntegrityViolation):
            self.ledger.recovered_cash()

    def test_operation_record_must_match_its_hashed_event(self):
        self.sent()
        self.corrupt("payment_operations", "payload_hash = 'changed'")
        with self.assertRaises(IntegrityViolation):
            self.ledger.verify_integrity()

    def test_deeply_nested_corrupt_metadata_is_a_sanitized_integrity_error(self):
        self.sent()
        payload = asdict(self.ledger.get(self.entry.entry_id).events[-1])
        payload.pop("event_hash")
        payload["details_json"] = '{"nested":' + '[' * 2000 + '0' + ']' * 2000 + '}'
        with closing(self.connection()) as connection, connection:
            trigger = connection.execute("SELECT sql FROM sqlite_master WHERE name = 'ledger_events_no_update'").fetchone()[0]
            connection.execute("DROP TRIGGER ledger_events_no_update")
            connection.execute("UPDATE ledger_events SET details_json = ?, event_hash = ? WHERE event_id = ?",
                               (payload["details_json"], _digest(payload), payload["event_id"]))
            connection.execute(trigger)
        with self.assertRaises(IntegrityViolation):
            self.ledger.verify_integrity()
        with self.assertRaises(IntegrityViolation):
            self.ledger.recovered_cash()

    def corrupt(self, table, assignment):
        # Simulates database-administrator access, outside the HTTP trust boundary.
        with closing(self.connection()) as connection, connection:
            triggers = connection.execute("SELECT name, sql FROM sqlite_master WHERE type = 'trigger' AND tbl_name = ?", (table,)).fetchall()
            for name, _ in triggers:
                connection.execute(f'DROP TRIGGER "{name}"')
            connection.execute(f"UPDATE {table} SET {assignment}")
            for _, sql in triggers:
                connection.execute(sql)
