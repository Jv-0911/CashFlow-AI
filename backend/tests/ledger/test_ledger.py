"""Offline ledger tests; no PayPal calls and no third-party dependencies."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import FrozenInstanceError, asdict, replace
import hashlib
import inspect
import json
from pathlib import Path
import random
import sqlite3
from tempfile import TemporaryDirectory
from threading import Barrier
import unittest
from unittest.mock import patch

from backend.app.ledger.errors import (EntryNotFound, IdempotencyConflict, IllegalTransition,
                                       IntegrityViolation, InvalidInput, SequenceConflict,
                                       StorageUnavailable)
from backend.app.ledger.models import IntegrityCheckpoint, LedgerSnapshot, State
from backend.app.ledger.service import LedgerService, _verified_recovered_cash
from backend.app.ledger.state_machine import Origin, TRANSITIONS, validate_transition
from backend.app.ledger.store import GENESIS_HASH, LedgerStore


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "ledger.db"
        self.service = LedgerService(self.path)

    def propose(self, key="request_demo_1", amount=1200):
        return self.service.propose(idempotency_key=key, amount_cents=amount, currency="USD")

    def approve(self, entry, key="approval_demo_1", seq=1, actor="user_demo_1"):
        return self.service.approve(entry.entry_id, idempotency_key=key,
                                    expected_sequence=seq, approved_by=actor)

    def test_empty_ledger(self):
        self.assertEqual(self.service.list_entries(), ())
        self.assertEqual(self.service.recovered_cash(), {})
        self.assertEqual(self.service.verify_integrity(), IntegrityCheckpoint(0, GENESIS_HASH))

    def test_proposal_and_explicit_approval_are_immutable_events(self):
        entry = self.propose()
        proposal = self.service.get(entry.entry_id)
        approval = self.approve(entry)
        snapshot = self.service.get(entry.entry_id)
        self.assertEqual(snapshot.state, State.APPROVED)
        self.assertEqual(snapshot.sequence, 2)
        self.assertEqual(snapshot.events[0], proposal.events[0])
        self.assertEqual(approval.actor, "user_demo_1")
        self.assertEqual(approval.from_state, State.PROPOSED)
        self.assertEqual(self.service.recovered_cash(), {"USD": 0})
        for obj, field, value in ((entry, "amount_cents", 1), (approval, "to_state", State.VERIFIED_PAID)):
            with self.assertRaises(FrozenInstanceError):
                setattr(obj, field, value)

    def test_persists_across_reopen(self):
        entry = self.propose()
        self.approve(entry)
        self.assertEqual(LedgerService(self.path).get(entry.entry_id), self.service.get(entry.entry_id))

    def test_missing_entry(self):
        with self.assertRaises(EntryNotFound):
            self.service.get("entry_missing")

    def test_invalid_amounts_write_nothing(self):
        for amount in (True, False, 0, -1, 1.5, "1200", None, 2**63):
            with self.subTest(amount=amount), self.assertRaises(InvalidInput):
                self.propose(amount=amount)
        self.assertEqual(self.service.list_entries(), ())

    def test_integer_boundaries(self):
        for index, amount in enumerate((1, 2**63 - 1)):
            self.assertEqual(self.propose(key=f"boundary_{index}", amount=amount).amount_cents, amount)

    def test_invalid_currency(self):
        for currency in (None, "", "usd", "EUR", "US", "USD ", 123):
            with self.subTest(currency=currency), self.assertRaises(InvalidInput):
                self.service.propose(idempotency_key="key", amount_cents=1, currency=currency)
        self.assertEqual(self.service.list_entries(), ())

    def test_invalid_keys_and_sql_injection_write_nothing(self):
        for key in (None, "", "has space", "x" * 129, "key\nvalue", "'; DROP TABLE ledger_events;--"):
            with self.subTest(key=key), self.assertRaises(InvalidInput):
                self.propose(key=key)
        self.assertEqual(self.service.list_entries(), ())

    def test_invalid_approvers_write_nothing(self):
        entry = self.propose()
        for actor in (None, "", "system", "verification_service", "webhook", "AI", "anonymous", "has space"):
            with self.subTest(actor=actor), self.assertRaises(InvalidInput):
                self.approve(entry, actor=actor)
        self.assertEqual(self.service.get(entry.entry_id).sequence, 1)

    def test_invalid_expected_sequence(self):
        entry = self.propose()
        for seq in (None, True, 0, -1, "1", 1.0):
            with self.subTest(seq=seq), self.assertRaises(InvalidInput):
                self.approve(entry, seq=seq)

    def test_idempotent_proposal_returns_original_after_approval(self):
        entry = self.propose()
        self.approve(entry)
        self.assertEqual(self.propose(), entry)
        self.assertEqual(self.service.get(entry.entry_id).sequence, 2)

    def test_idempotent_approval_returns_original_despite_stale_sequence(self):
        entry = self.propose()
        approval = self.approve(entry)
        self.assertEqual(self.approve(entry), approval)
        self.assertEqual(self.service.get(entry.entry_id).sequence, 2)

    def test_reusing_key_for_different_amount_fails(self):
        self.propose()
        with self.assertRaises(IdempotencyConflict):
            self.propose(amount=1300)
        self.assertEqual(len(self.service.list_entries()), 1)

    def test_reusing_key_for_different_approval_fails(self):
        entry = self.propose()
        self.approve(entry)
        with self.assertRaises(IdempotencyConflict):
            self.approve(entry, actor="user_demo_2")
        other = self.propose(key="other")
        with self.assertRaises(IdempotencyConflict):
            self.approve(other)
        self.assertEqual(self.service.get(other.entry_id).sequence, 1)

    def test_keys_are_unique_across_operations(self):
        entry = self.propose()
        with self.assertRaises(IdempotencyConflict):
            self.approve(entry, key=entry.correlation_key)
        self.assertEqual(self.service.get(entry.entry_id).sequence, 1)

    def test_stale_sequence_writes_nothing(self):
        entry = self.propose()
        before = self.service.verify_integrity()
        with self.assertRaises(SequenceConflict):
            self.approve(entry, seq=2)
        self.assertEqual(self.service.verify_integrity(), before)

    def test_reapproval_with_new_key_is_illegal_and_writes_nothing(self):
        entry = self.propose()
        self.approve(entry)
        before = self.service.verify_integrity()
        with self.assertRaises(IllegalTransition):
            self.approve(entry, key="new_approval", seq=2)
        self.assertEqual(self.service.verify_integrity(), before)

    def test_partial_transaction_failure_rolls_back_entry(self):
        with patch.object(LedgerStore, "_insert_workflow_event", side_effect=RuntimeError("simulated crash")):
            with self.assertRaises(RuntimeError):
                self.propose()
        self.assertEqual(self.service.list_entries(), ())
        self.assertEqual(self.propose().correlation_key, "request_demo_1")

    def test_sql_triggers_reject_all_updates_and_deletes(self):
        self.propose()
        with closing(sqlite3.connect(self.path)) as connection, connection:
            for table in ("ledger_entries", "ledger_events"):
                for sql in (f"DELETE FROM {table}", f"UPDATE {table} SET entry_id = entry_id"):
                    with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError):
                        connection.execute(sql)
        self.service.verify_integrity()

    def test_sql_constraints_enforce_entry_key_uniqueness_and_money(self):
        entry = self.propose()
        with closing(sqlite3.connect(self.path)) as connection, connection:
            base = asdict(entry)
            for changes in ({"entry_id": "other_entry"},
                            {"entry_id": "other_entry", "correlation_key": "other", "amount_cents": 0},
                            {"entry_id": "other_entry", "correlation_key": "other", "amount_cents": -1},
                            {"entry_id": "other_entry", "correlation_key": "other", "amount_cents": 1.5},
                            {"entry_id": "other_entry", "correlation_key": "other", "currency": "EUR"}):
                with self.subTest(changes=changes), self.assertRaises(sqlite3.IntegrityError):
                    connection.execute("INSERT INTO ledger_entries VALUES (?, ?, ?, ?, ?, ?)", tuple((base | changes).values()))

    def test_replace_cannot_bypass_append_only_even_without_recursive_triggers(self):
        entry = self.propose()
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("PRAGMA recursive_triggers = OFF")
            for table in ("ledger_entries", "ledger_events"):
                row = connection.execute(f"SELECT * FROM {table}").fetchone()
                placeholders = ",".join("?" for _ in row)
                with self.subTest(table=table), self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(f"INSERT OR REPLACE INTO {table} VALUES ({placeholders})", row)
        self.assertEqual(self.service.get(entry.entry_id).sequence, 1)

    def test_sql_constraints_enforce_event_key_and_sequence_uniqueness(self):
        entry = self.propose()
        event = self.service.get(entry.entry_id).events[0]
        with closing(sqlite3.connect(self.path)) as connection, connection:
            for field in ("seq", "global_seq", "idempotency_key"):
                payload = asdict(event) | {"event_id": "evt_other", "seq": 2, "global_seq": 2,
                                            "idempotency_key": "other", "event_hash": "a" * 64}
                payload[field] = getattr(event, field)
                placeholders = ",".join("?" for _ in payload)
                with self.subTest(field=field), self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(f"INSERT INTO ledger_events VALUES ({placeholders})", tuple(payload.values()))

    def test_database_unique_constraints_work_independently_of_insert_guards(self):
        entry = self.propose()
        event = self.service.get(entry.entry_id).events[0]
        connection = sqlite3.connect(self.path)
        try:
            connection.execute("BEGIN")
            connection.execute("DROP TRIGGER ledger_entries_no_replace")
            connection.execute("DROP TRIGGER ledger_events_no_replace")
            duplicate_entry = asdict(entry) | {"entry_id": "entry_other"}
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("INSERT INTO ledger_entries VALUES (?, ?, ?, ?, ?, ?)", tuple(duplicate_entry.values()))
            for field in ("seq", "global_seq", "idempotency_key"):
                payload = asdict(event) | {"event_id": "evt_other", "seq": 2, "global_seq": 2,
                                            "idempotency_key": "other", "event_hash": "a" * 64}
                payload[field] = getattr(event, field)
                placeholders = ",".join("?" for _ in payload)
                with self.subTest(field=field), self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(f"INSERT INTO ledger_events VALUES ({placeholders})", tuple(payload.values()))
        finally:
            connection.rollback()
            connection.close()
        self.service.verify_integrity()

    def test_invoice_bindings_have_both_unique_constraints_and_append_only_guards(self):
        first = self.propose()
        second = self.propose(key="second")
        events = [self.service.get(entry.entry_id).events[0].event_id for entry in (first, second)]
        connection = sqlite3.connect(self.path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("INSERT INTO invoice_bindings VALUES (?, ?, ?)", (first.entry_id, "INV-DEMO-1", events[0]))
            for args in ((first.entry_id, "INV-DEMO-2", events[1]), (second.entry_id, "INV-DEMO-1", events[1])):
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute("INSERT INTO invoice_bindings VALUES (?, ?, ?)", args)
            for sql in ("DELETE FROM invoice_bindings", "UPDATE invoice_bindings SET provider_invoice_id = 'INV-DEMO-3'"):
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(sql)
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("INSERT OR REPLACE INTO invoice_bindings VALUES (?, ?, ?)",
                                   (first.entry_id, "INV-DEMO-3", events[0]))
        finally:
            connection.rollback()
            connection.close()
        self.service.verify_integrity()

    def test_concurrent_duplicate_proposals_create_one_entry(self):
        barrier = Barrier(8)
        def worker(_):
            barrier.wait()
            return LedgerService(self.path).propose(idempotency_key="concurrent", amount_cents=1200, currency="USD")
        with ThreadPoolExecutor(max_workers=8) as pool:
            entries = list(pool.map(worker, range(8)))
        self.assertEqual(len(set(entries)), 1)
        self.assertEqual(len(self.service.list_entries()), 1)
        self.assertEqual(self.service.verify_integrity().global_seq, 1)

    def test_concurrent_duplicate_approvals_create_one_event(self):
        entry = self.propose()
        barrier = Barrier(8)
        def worker(_):
            barrier.wait()
            return self.approve(entry)
        with ThreadPoolExecutor(max_workers=8) as pool:
            events = list(pool.map(worker, range(8)))
        self.assertEqual(len(set(events)), 1)
        self.assertEqual(self.service.get(entry.entry_id).sequence, 2)

    def test_concurrent_conflicting_payloads_have_one_winner(self):
        barrier = Barrier(2)
        def worker(amount):
            barrier.wait()
            try:
                return self.propose(key="race", amount=amount)
            except IdempotencyConflict:
                return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, (100, 200)))
        self.assertEqual(results.count("conflict"), 1)
        self.assertEqual(len(self.service.list_entries()), 1)

    def test_concurrent_different_approval_keys_have_one_sequence_winner(self):
        entry = self.propose()
        barrier = Barrier(2)
        def worker(key):
            barrier.wait()
            try:
                return self.approve(entry, key=key)
            except SequenceConflict:
                return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, ("race_a", "race_b")))
        self.assertEqual(results.count("conflict"), 1)
        self.assertEqual(self.service.get(entry.entry_id).sequence, 2)

    def test_interleaved_entries_have_correct_independent_and_global_chains(self):
        first = self.propose()
        second = self.propose(key="second")
        approval = self.approve(first)
        first_event = self.service.get(first.entry_id).events[0]
        second_event = self.service.get(second.entry_id).events[0]
        self.assertEqual(approval.prev_hash, first_event.event_hash)
        self.assertEqual(approval.global_prev_hash, second_event.event_hash)
        self.assertEqual(approval.seq, 2)
        self.assertEqual(approval.global_seq, 3)

    def test_canonical_hash_is_independently_reproducible(self):
        entry = self.propose()
        event = self.service.get(entry.entry_id).events[0]
        payload = asdict(event)
        expected = payload.pop("event_hash")
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
        self.assertEqual(hashlib.sha256(encoded).hexdigest(), expected)

    def corrupt(self, table, action, statement, values=()):
        # Deliberately simulate a database administrator bypassing protections.
        # These destructive statements exist only in temporary test databases.
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute(f"DROP TRIGGER {table}_no_{action.lower()}")
            connection.execute(statement, values)
            connection.execute(LedgerStore._trigger_sql(table, action))

    def test_event_tamper_detected_and_reads_and_writes_fail_closed(self):
        entry = self.propose()
        self.corrupt("ledger_events", "UPDATE", "UPDATE ledger_events SET actor = 'changed'")
        for operation in (self.service.verify_integrity, self.service.recovered_cash,
                          self.service.list_entries, lambda: self.service.get(entry.entry_id),
                          lambda: self.approve(entry), lambda: LedgerService(self.path)):
            with self.subTest(operation=operation), self.assertRaises(IntegrityViolation):
                operation()

    def test_immutable_entry_tamper_detected(self):
        self.propose()
        self.corrupt("ledger_entries", "UPDATE", "UPDATE ledger_entries SET amount_cents = 9999")
        with self.assertRaises(IntegrityViolation):
            self.service.verify_integrity()

    def test_every_event_field_is_covered_by_integrity_check(self):
        entry = self.propose()
        original = self.service.get(entry.entry_id).events[0]
        changes = {
            "event_id": "evt_changed", "entry_id": "entry_changed", "seq": 2,
            "global_seq": 2, "from_state": "APPROVED", "to_state": "VERIFIED_PAID",
            "provider_status": "PAID", "provider_invoice_id": "INV-DEMO-CHANGED",
            "paid_amount_cents": 1200, "actor": "verification_service", "reason": "changed",
            "occurred_at": "2026-10-11T00:00:00.000000+00:00", "idempotency_key": "changed",
            "request_hash": "a" * 64, "entry_hash": "b" * 64, "prev_hash": "c" * 64,
            "global_prev_hash": "d" * 64, "event_hash": "e" * 64,
            "details_json": "{\"changed\":true}",
        }
        self.assertEqual(set(changes), set(asdict(original)))
        for field, value in changes.items():
            with self.subTest(field=field):
                self.corrupt("ledger_events", "UPDATE", f"UPDATE ledger_events SET {field} = ?", (value,))
                with self.assertRaises(IntegrityViolation):
                    self.service.verify_integrity()
                self.corrupt("ledger_events", "UPDATE", f"UPDATE ledger_events SET {field} = ?", (getattr(original, field),))
        self.service.verify_integrity()

    def test_rehashing_forged_paid_event_still_does_not_create_a_payment_path(self):
        entry = self.propose()
        original = self.service.get(entry.entry_id).events[0]
        payload = asdict(original) | {"to_state": State.VERIFIED_PAID,
                                      "actor": "verification_service", "provider_status": "PAID",
                                      "paid_amount_cents": 1200}
        payload.pop("event_hash")
        forged_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.corrupt("ledger_events", "UPDATE",
                     "UPDATE ledger_events SET to_state = ?, actor = ?, provider_status = ?, paid_amount_cents = ?, event_hash = ?",
                     (State.VERIFIED_PAID, "verification_service", "PAID", 1200, forged_hash))
        with self.assertRaises(IntegrityViolation):
            self.service.recovered_cash()

    def test_middle_event_deletion_detected(self):
        entry = self.propose()
        self.approve(entry)
        self.corrupt("ledger_events", "DELETE", "DELETE FROM ledger_events WHERE seq = 1")
        with self.assertRaises(IntegrityViolation):
            self.service.verify_integrity()

    def test_tail_deletion_detected_with_external_checkpoint(self):
        entry = self.propose()
        self.approve(entry)
        checkpoint = self.service.verify_integrity()
        self.corrupt("ledger_events", "DELETE", "DELETE FROM ledger_events WHERE seq = 2")
        # A self-contained hash chain cannot detect deletion of its own tail.
        self.assertEqual(self.service.verify_integrity().global_seq, 1)
        with self.assertRaises(IntegrityViolation):
            self.service.verify_integrity(checkpoint)

    def test_old_checkpoint_remains_valid_after_further_appends(self):
        entry = self.propose()
        checkpoint = self.service.verify_integrity()
        self.approve(entry)
        self.assertEqual(self.service.verify_integrity(checkpoint).global_seq, 2)

    def test_missing_or_modified_trigger_fails_startup(self):
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("DROP TRIGGER ledger_events_no_update")
        with self.assertRaises(IntegrityViolation):
            LedgerService(self.path)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("CREATE TRIGGER ledger_events_no_update BEFORE UPDATE ON ledger_events BEGIN SELECT 1; END")
        with self.assertRaises(IntegrityViolation):
            LedgerService(self.path)

    def test_wrong_checkpoint_rejected(self):
        self.propose()
        with self.assertRaises(IntegrityViolation):
            self.service.verify_integrity(IntegrityCheckpoint(1, "a" * 64))
        with self.assertRaises(InvalidInput):
            self.service.verify_integrity(IntegrityCheckpoint(-1, "bad"))

    def test_errors_do_not_include_caller_values_or_filesystem_path(self):
        invalid_identifier = "invalid identifier must not appear"
        with self.assertRaises(InvalidInput) as caught:
            self.propose(key=invalid_identifier)
        self.assertNotIn(invalid_identifier, str(caught.exception))
        with self.assertRaises(StorageUnavailable) as caught:
            LedgerService(Path(self.temp.name) / "missing_parent" / "ledger.db")
        self.assertNotIn(self.temp.name, str(caught.exception))

    def test_no_false_completed_status_from_any_current_untrusted_path(self):
        entry = self.propose()
        self.approve(entry)
        before = self.service.verify_integrity()
        for source in ("client_request", "redirect", "webhook_body", "signed_webhook_body",
                       "ai_output", "unknown_status", "malformed_response"):
            for field in ("status", "to_state", "provider_status", "actor", "paid_amount_cents"):
                with self.subTest(source=source, field=field), self.assertRaises(TypeError):
                    self.service.propose(idempotency_key=source, amount_cents=1200,
                                         currency="USD", **{field: "VERIFIED_PAID"})
                with self.subTest(source=source, field=field), self.assertRaises(TypeError):
                    self.service.approve(entry.entry_id, idempotency_key=source,
                                         expected_sequence=2, approved_by="user_demo_1",
                                         **{field: "VERIFIED_PAID"})
        with self.assertRaises(InvalidInput):
            self.approve(entry, key="forged_actor", seq=2, actor="verification_service")
        self.assertEqual(self.service.verify_integrity(), before)
        self.assertEqual(self.service.get(entry.entry_id).state, State.APPROVED)
        self.assertEqual(self.service.recovered_cash(), {"USD": 0})

    def test_recovered_cash_policy_for_every_state(self):
        entry = self.propose()
        base = self.service.get(entry.entry_id).events[0]
        # Pure aggregation fixtures, never inserted into a live ledger.
        for state in State:
            event = replace(base, to_state=state, paid_amount_cents=1200, provider_status="PAID")
            with self.subTest(state=state):
                self.assertEqual(_verified_recovered_cash((LedgerSnapshot(entry, (event,)),)),
                                 {"USD": 1200 if state == State.VERIFIED_PAID else 0})

    def test_recovered_cash_counts_latest_state_once(self):
        entry = self.propose()
        base = self.service.get(entry.entry_id).events[0]
        paid = replace(base, to_state=State.VERIFIED_PAID, paid_amount_cents=1200, provider_status="PAID")
        refunded = replace(paid, to_state=State.REFUNDED)
        self.assertEqual(_verified_recovered_cash((LedgerSnapshot(entry, (base, paid, paid)),)), {"USD": 1200})
        self.assertEqual(_verified_recovered_cash((LedgerSnapshot(entry, (base, paid, refunded)),)), {"USD": 0})

    def test_recovered_cash_rejects_inconsistent_verified_amount(self):
        entry = self.propose()
        base = self.service.get(entry.entry_id).events[0]
        for amount in (None, 1, 1199, 1201, True):
            event = replace(base, to_state=State.VERIFIED_PAID, provider_status="PAID", paid_amount_cents=amount)
            with self.subTest(amount=amount), self.assertRaises(IntegrityViolation):
                _verified_recovered_cash((LedgerSnapshot(entry, (event,)),))
        self.assertEqual(list(inspect.signature(self.service.recovered_cash).parameters), [])


class TransitionTests(unittest.TestCase):
    def test_only_proposed_can_be_initial(self):
        for target in State:
            if target == State.PROPOSED:
                validate_transition(None, target)
            else:
                with self.subTest(target=target), self.assertRaises(IllegalTransition):
                    validate_transition(None, target)

    def test_all_workflow_pairs_reject_sensitive_states(self):
        for previous in State:
            for target in (State.VERIFIED_PAID, State.PARTIALLY_PAID, State.REFUNDED):
                with self.subTest(previous=previous, target=target), self.assertRaises(IllegalTransition):
                    validate_transition(previous, target, has_approval=True, provider_status="PAID")

    def test_direct_pending_to_paid_requires_approval_and_exact_status(self):
        validate_transition(State.PAYMENT_PENDING, State.VERIFIED_PAID,
                            origin=Origin.VERIFICATION, has_approval=True, provider_status="PAID")
        for status in (None, "", "MARKED_AS_PAID", "paid", "UNKNOWN", "PARTIALLY_PAID"):
            with self.subTest(status=status), self.assertRaises(IllegalTransition):
                validate_transition(State.PAYMENT_PENDING, State.VERIFIED_PAID,
                                    origin=Origin.VERIFICATION, has_approval=True, provider_status=status)
        with self.assertRaises(IllegalTransition):
            validate_transition(State.PAYMENT_PENDING, State.VERIFIED_PAID,
                                origin=Origin.VERIFICATION, provider_status="PAID")

    def test_uncertain_state_cannot_invent_human_approval(self):
        for previous in (State.UNRESOLVED, State.AWAITING_VERIFICATION):
            for target in (State.PROPOSED, State.APPROVED):
                with self.subTest(previous=previous, target=target), self.assertRaises(IllegalTransition):
                    validate_transition(previous, target, origin=Origin.VERIFICATION,
                                        has_approval=True, provider_status="PAID")

    def test_verified_state_cannot_be_downgraded_by_workflow(self):
        for target in State:
            with self.subTest(target=target), self.assertRaises(IllegalTransition):
                validate_transition(State.VERIFIED_PAID, target, has_approval=True, provider_status="PAID")

    def test_raw_strings_are_not_policy_capabilities(self):
        with self.assertRaises(IllegalTransition):
            validate_transition("PAYMENT_PENDING", State.VERIFIED_PAID,
                                origin=Origin.VERIFICATION, has_approval=True, provider_status="PAID")
        with self.assertRaises(IllegalTransition):
            validate_transition(State.PAYMENT_PENDING, State.VERIFIED_PAID,
                                origin="verification", has_approval=True, provider_status="PAID")

    def test_transition_table_is_immutable(self):
        with self.assertRaises(TypeError):
            TRANSITIONS[State.PROPOSED] = frozenset({State.VERIFIED_PAID})

    def test_generated_workflow_sequences_never_reach_verified_cash(self):
        rng = random.Random(20261012)
        for _ in range(100):
            current = State.PROPOSED
            for _ in range(50):
                target = rng.choice(tuple(State))
                try:
                    validate_transition(current, target, has_approval=True, provider_status="PAID")
                except IllegalTransition:
                    continue
                current = target
                self.assertNotIn(current, {State.VERIFIED_PAID, State.PARTIALLY_PAID, State.REFUNDED})


if __name__ == "__main__":
    unittest.main()
