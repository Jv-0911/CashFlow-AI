"""Offline SQLite backup/restart drills; all payment evidence is synthetic."""
from contextlib import closing
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import unittest

from backend.app.ledger.errors import IntegrityViolation, StorageUnavailable
from backend.app.ledger.models import State
from backend.app.ledger.service import LedgerService
from backend.app.payments.errors import ProviderTimeout
from backend.app.payments.webhooks import WebhookHandler
from backend.tests.payments import test_invoice_service as fixtures
from backend.tests.payments import test_webhooks as webhook_fixtures
from backend.tests.payments.fakes import oauth, response


# A fresh interpreter proves that no process-local cache supplies restored state.
# The child blocks real network access independently of the parent test runner.
_RESTART = """
from dataclasses import asdict
import json
import sys
from backend.app.ledger.models import IntegrityCheckpoint
from backend.app.ledger.service import LedgerService
from backend.app.payments.errors import RecoveryRequired
from backend.app.payments.invoice_service import InvoiceService
from backend.app.payments.webhooks import WebhookHandler
from backend.tests.payments.fakes import client, oauth, response
from backend.tests.payments.run_tests import test_environment

with test_environment(sandbox=False):
    request = json.load(sys.stdin)
    ledger = LedgerService(sys.argv[1])
    checkpoint = ledger.verify_integrity(IntegrityCheckpoint(**request['checkpoint']))
    api, fake = client()
    result = None
    if request['mode'] in ('create', 'send'):
        service = InvoiceService(ledger, api, lambda ref: 'demo-payer@example.test')
        operation = service.create_draft if request['mode'] == 'create' else service.send
        try:
            operation(request['entry_id'], idempotency_key=request['mode'])
        except RecoveryRequired:
            result = 'recovery_required'
        else:
            raise AssertionError('An uncertain operation must not be dispatched again')
        assert fake.calls == [], 'Recovery attempted a provider call'
    elif request['mode'] == 'webhook':
        fake.steps += [oauth(), response({'verification_status': 'SUCCESS'})]
        result = WebhookHandler(ledger, api).handle(
            request['body'].encode(), request['headers'])
        assert result == 'duplicate'
        assert [call[1] for call in fake.calls] == [
            '/v1/oauth2/token', '/v1/notifications/verify-webhook-signature']
    assert ledger.verify_integrity() == checkpoint
    print(json.dumps({
        'checkpoint': asdict(checkpoint),
        'snapshots': [asdict(item) for item in ledger.list_entries()],
        'operations': ledger._store.operations(),
        'binding': ledger._store.invoice_binding(request['entry_id']),
        'cash': ledger.recovered_cash(), 'result': result,
    }))
"""


class RecoveryDrillTests(unittest.TestCase):
    setUp = fixtures.InvoiceServiceTests.setUp
    approve = fixtures.InvoiceServiceTests.approve
    provider_invoice = fixtures.InvoiceServiceTests.provider_invoice
    draft = fixtures.InvoiceServiceTests.draft
    sent = fixtures.InvoiceServiceTests.sent
    headers = webhook_fixtures.WebhookTests.headers
    body = webhook_fixtures.WebhookTests.body

    def backup(self):
        source = Path(self.temp.name) / "ledger.db"
        target = Path(self.temp.name) / "recovery.db"
        # The source URI cannot silently create a missing source database.
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as src:
            with closing(sqlite3.connect(target)) as dest:
                src.backup(dest)
        return target

    def restart(self, target, mode, **extra):
        checkpoint = self.ledger.verify_integrity()
        request = {'checkpoint': asdict(checkpoint), 'entry_id': self.entry.entry_id,
                   'mode': mode, **extra}
        result = subprocess.run(
            [sys.executable, '-B', '-c', _RESTART, str(target)],
            input=json.dumps(request), text=True, capture_output=True, timeout=30,
            cwd=Path(__file__).resolve().parents[3], check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        actual = json.loads(result.stdout)
        expected = {
            'checkpoint': asdict(checkpoint),
            'snapshots': [asdict(item) for item in self.ledger.list_entries()],
            'operations': self.ledger._store.operations(),
            'binding': self.ledger._store.invoice_binding(self.entry.entry_id),
            'cash': self.ledger.recovered_cash(),
        }
        self.assertEqual({k: v for k, v in actual.items() if k != 'result'},
                         json.loads(json.dumps(expected)))
        return actual

    def test_verified_cash_and_duplicate_receipt_survive_backup_and_process_restart(self):
        self.sent()
        self.fake.steps += [response({'verification_status': 'SUCCESS'}),
                            response(self.provider_invoice('PAID', paid='12.00'))]
        WebhookHandler(self.ledger, self.api).handle(self.body(), self.headers())
        result = self.restart(self.backup(), 'webhook',
                              body=self.body().decode(), headers=self.headers())
        self.assertEqual(result['cash'], {'USD': 1200})
        self.assertEqual(result['result'], 'duplicate')

    def test_uncertain_create_remains_blocked_after_backup_and_process_restart(self):
        self.approve()
        self.fake.steps += [oauth(), ProviderTimeout()]
        with self.assertRaises(ProviderTimeout):
            self.service.create_draft(self.entry.entry_id, idempotency_key='create')
        self.assertEqual(self.ledger.get(self.entry.entry_id).state, State.APPROVED)
        result = self.restart(self.backup(), 'create')
        self.assertEqual(result['cash'], {'USD': 0})
        self.assertEqual(result['result'], 'recovery_required')

    def test_uncertain_send_remains_blocked_after_backup_and_process_restart(self):
        self.draft()
        self.fake.steps += [response(self.provider_invoice()), ProviderTimeout()]
        with self.assertRaises(ProviderTimeout):
            self.service.send(self.entry.entry_id, idempotency_key='send')
        self.assertEqual(self.ledger.get(self.entry.entry_id).state, State.INVOICE_DRAFTED)
        result = self.restart(self.backup(), 'send')
        self.assertEqual(result['cash'], {'USD': 0})
        self.assertEqual(result['result'], 'recovery_required')

    def test_older_backup_cannot_satisfy_a_newer_trusted_checkpoint(self):
        earlier = self.ledger.verify_integrity()
        target = self.backup()
        self.approve()
        latest = self.ledger.verify_integrity()
        restored = LedgerService(target)
        self.assertEqual(restored.verify_integrity(earlier), earlier)
        with self.assertRaises(IntegrityViolation):
            restored.verify_integrity(latest)
        self.assertEqual(restored.get(self.entry.entry_id).state, State.PROPOSED)
        self.assertEqual(self.ledger.get(self.entry.entry_id).state, State.APPROVED)

    def test_backup_includes_committed_wal_records(self):
        source = Path(self.temp.name) / 'ledger.db'
        # Keep a connection open so the committed WAL remains separate from
        # the main file. A raw copy of only ledger.db would miss these records.
        with closing(sqlite3.connect(source)) as connection:
            self.assertEqual(connection.execute('PRAGMA journal_mode=WAL').fetchone()[0], 'wal')
            connection.execute('PRAGMA wal_autocheckpoint=0')
            connection.execute('BEGIN')
            connection.execute('SELECT COUNT(*) FROM ledger_events').fetchone()
            self.approve()
            self.assertGreater(Path(str(source) + '-wal').stat().st_size, 0)
            result = self.restart(self.backup(), 'inspect')
        self.assertEqual(result['snapshots'][0]['events'][-1]['to_state'], 'APPROVED')

    def test_corrupt_backup_fails_without_changing_source(self):
        before = self.ledger.verify_integrity()
        target = self.backup()
        target.write_bytes(b'not a SQLite database')
        with self.assertRaises((IntegrityViolation, StorageUnavailable)):
            LedgerService(target)
        self.assertEqual(self.ledger.verify_integrity(), before)

    def test_empty_replacement_cannot_satisfy_nonempty_trusted_checkpoint(self):
        # Normal startup permits a new ledger. Startup success by itself is
        # therefore insufficient evidence that a backup restored any history.
        restored = LedgerService(Path(self.temp.name) / 'empty.db')
        with self.assertRaises(IntegrityViolation):
            restored.verify_integrity(self.ledger.verify_integrity())
        self.assertEqual(restored.list_entries(), ())
