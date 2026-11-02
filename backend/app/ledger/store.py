"""SQLite append-only store with transactional idempotency and integrity checks.

There is intentionally no public generic append/status API. Proposal/approval
commands and narrowly scoped payment commands have separate evidence checks;
an actor string never grants verification authority.
"""

from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from .errors import (EntryNotFound, IdempotencyConflict, IllegalTransition, IntegrityViolation,
                     InvalidInput, SequenceConflict, StorageUnavailable)
from .models import (IntegrityCheckpoint, LedgerEntry, LedgerEvent, LedgerSnapshot,
                     State, require_amount, require_approver, require_currency,
                     require_identifier, require_sequence)
from .state_machine import validate_transition
from .payment_events import PaymentWrites, PAYMENT_SCHEMA
from ..payments.errors import PaymentError

GENESIS_HASH = "0" * 64
_STATES_SQL = ",".join("'" + state.value + "'" for state in State)
_TABLES = ("ledger_entries", "ledger_events", "invoice_bindings", "payment_operations", "processed_webhook_events")
_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS ledger_entries (
    entry_id TEXT PRIMARY KEY,
    correlation_key TEXT UNIQUE NOT NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    currency TEXT NOT NULL CHECK (currency = 'USD'),
    provider TEXT NOT NULL CHECK (provider = 'paypal_sandbox'),
    created_at TEXT NOT NULL
) STRICT;
CREATE TABLE IF NOT EXISTS ledger_events (
    event_id TEXT PRIMARY KEY,
    entry_id TEXT NOT NULL REFERENCES ledger_entries(entry_id),
    seq INTEGER NOT NULL CHECK (seq > 0),
    global_seq INTEGER UNIQUE NOT NULL CHECK (global_seq > 0),
    from_state TEXT CHECK (from_state IN ({_STATES_SQL})),
    to_state TEXT NOT NULL CHECK (to_state IN ({_STATES_SQL})),
    provider_status TEXT,
    provider_invoice_id TEXT,
    paid_amount_cents INTEGER CHECK (paid_amount_cents >= 0),
    actor TEXT NOT NULL,
    reason TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    idempotency_key TEXT UNIQUE NOT NULL,
    request_hash TEXT NOT NULL CHECK (length(request_hash) = 64),
    entry_hash TEXT NOT NULL CHECK (length(entry_hash) = 64),
    prev_hash TEXT NOT NULL CHECK (length(prev_hash) = 64),
    global_prev_hash TEXT NOT NULL CHECK (length(global_prev_hash) = 64),
    event_hash TEXT UNIQUE NOT NULL CHECK (length(event_hash) = 64),
    details_json TEXT NOT NULL DEFAULT '{{}}',
    UNIQUE (entry_id, seq)
) STRICT;
CREATE TABLE IF NOT EXISTS invoice_bindings (
    entry_id TEXT PRIMARY KEY REFERENCES ledger_entries(entry_id),
    provider_invoice_id TEXT UNIQUE NOT NULL,
    event_id TEXT UNIQUE NOT NULL REFERENCES ledger_events(event_id)
) STRICT;
""" + PAYMENT_SCHEMA


def _digest(value: dict) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _request_hash(operation: str, **fields) -> str:
    return _digest({"operation": operation, **fields})


def _event_from_row(row: sqlite3.Row) -> LedgerEvent:
    data = dict(row)
    data["from_state"] = State(data["from_state"]) if data["from_state"] else None
    data["to_state"] = State(data["to_state"])
    return LedgerEvent(**data)


class LedgerStore(PaymentWrites):
    def __init__(self, db_path: str | Path):
        if str(db_path) == ":memory:":
            raise InvalidInput("A persistent database path is required.")
        self._path = Path(db_path).resolve()
        # Parent directory provisioning belongs to deployment/configuration.
        with self._connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
                if not existing:
                    for statement in _SCHEMA.split(";"):
                        if statement.strip():
                            connection.execute(statement)
                    for table in _TABLES:
                        for action in ("UPDATE", "DELETE", "REPLACE"):
                            connection.execute(self._trigger_sql(table, action))
                self._verify(connection)
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    @staticmethod
    def _trigger_sql(table: str, action: str) -> str:
        # Inputs are exclusively internal constants, never caller-supplied SQL.
        if action == "REPLACE":
            conflicts = {
                "ledger_entries": "entry_id = NEW.entry_id OR correlation_key = NEW.correlation_key",
                "ledger_events": ("event_id = NEW.event_id OR global_seq = NEW.global_seq "
                                  "OR idempotency_key = NEW.idempotency_key OR event_hash = NEW.event_hash "
                                  "OR (entry_id = NEW.entry_id AND seq = NEW.seq)"),
                "invoice_bindings": ("entry_id = NEW.entry_id OR provider_invoice_id = NEW.provider_invoice_id "
                                     "OR event_id = NEW.event_id"),
                "payment_operations": ("operation_key = NEW.operation_key OR request_id = NEW.request_id "
                                       "OR event_id = NEW.event_id OR (entry_id = NEW.entry_id AND kind = NEW.kind)"),
                "processed_webhook_events": "provider_event_id = NEW.provider_event_id OR seq = NEW.seq OR event_hash = NEW.event_hash",
            }
            return (f"CREATE TRIGGER IF NOT EXISTS {table}_no_replace "
                    f"BEFORE INSERT ON {table} WHEN EXISTS (SELECT 1 FROM {table} WHERE {conflicts[table]}) "
                    "BEGIN SELECT RAISE(ABORT, 'Append-only ledger'); END")
        return (f"CREATE TRIGGER IF NOT EXISTS {table}_no_{action.lower()} "
                f"BEFORE {action} ON {table} BEGIN "
                "SELECT RAISE(ABORT, 'Append-only ledger'); END")

    @contextmanager
    def _connection(self):
        connection = None
        try:
            connection = sqlite3.connect(self._path, timeout=5, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA synchronous = FULL")
            yield connection
        except sqlite3.IntegrityError:
            raise IntegrityViolation("Ledger constraint rejected the operation.") from None
        except sqlite3.DatabaseError:
            raise StorageUnavailable("Ledger storage is unavailable.") from None
        finally:
            if connection is not None:
                connection.close()

    @contextmanager
    def _transaction(self, *, write: bool = False):
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            try:
                self._verify(connection)
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    def _verify(self, connection: sqlite3.Connection,
                checkpoint: IntegrityCheckpoint | None = None) -> IntegrityCheckpoint:
        """Check hashes AND domain structure in a single consistent snapshot."""
        try:
            if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError
            if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise ValueError
            actual_tables = {row["name"]: " ".join(row["sql"].split()) for row in
                             connection.execute("SELECT name, sql FROM sqlite_master WHERE type = 'table'")}
            for statement in _SCHEMA.split(";"):
                if statement.strip():
                    expected_sql = " ".join(statement.replace(" IF NOT EXISTS", "").split())
                    table_name = expected_sql.split()[2]
                    if actual_tables.get(table_name) != expected_sql:
                        raise ValueError
            expected_triggers = {
                f"{table}_no_{action.lower()}"
                for table in _TABLES
                for action in ("UPDATE", "DELETE", "REPLACE")
            }
            trigger_rows = connection.execute(
                "SELECT name, sql FROM sqlite_master WHERE type = 'trigger'"
            ).fetchall()
            actual_triggers = {row["name"]: row["sql"] for row in trigger_rows}
            if not expected_triggers <= actual_triggers.keys():
                raise ValueError
            for table in _TABLES:
                for action in ("UPDATE", "DELETE", "REPLACE"):
                    expected_sql = self._trigger_sql(table, action).replace(" IF NOT EXISTS", "")
                    if actual_triggers[f"{table}_no_{action.lower()}"] != expected_sql:
                        raise ValueError
            entries = {row["entry_id"]: LedgerEntry(**dict(row)) for row in
                       connection.execute("SELECT * FROM ledger_entries")}
            for entry in entries.values():
                require_identifier(entry.entry_id)
                require_identifier(entry.correlation_key)
                require_amount(entry.amount_cents)
                require_currency(entry.currency)
                if entry.provider != "paypal_sandbox":
                    raise ValueError
                self._validate_time(entry.created_at)
            previous_by_entry = {}
            history_by_entry = {key: [] for key in entries}
            all_events = {}
            global_hash = GENESIS_HASH
            global_seq = 0
            checkpoint_seen = checkpoint is None or checkpoint == IntegrityCheckpoint(0, GENESIS_HASH)
            for row in connection.execute("SELECT * FROM ledger_events ORDER BY global_seq"):
                event = _event_from_row(row)
                entry = entries[event.entry_id]
                previous = previous_by_entry.get(event.entry_id)
                if event.global_seq != global_seq + 1 or event.global_prev_hash != global_hash:
                    raise ValueError
                if event.seq != (previous.seq + 1 if previous else 1):
                    raise ValueError
                if event.prev_hash != (previous.event_hash if previous else GENESIS_HASH):
                    raise ValueError
                if event.from_state != (previous.to_state if previous else None):
                    raise ValueError
                if event.entry_hash != _digest(asdict(entry)):
                    raise ValueError
                payload = asdict(event)
                payload.pop("event_hash")
                if _digest(payload) != event.event_hash:
                    raise ValueError
                require_identifier(event.event_id)
                require_identifier(event.idempotency_key)
                self._validate_time(event.occurred_at)
                details = json.loads(event.details_json)
                if type(details) is not dict:
                    raise ValueError
                if event.reason == "RECOVERY_PROPOSED":
                    expected_request = _request_hash(
                        "propose", amount_cents=entry.amount_cents, currency=entry.currency,
                        idempotency_key=entry.correlation_key)
                    if (previous is not None or event.actor != "system" or event.to_state != State.PROPOSED or details
                            or event.reason != "RECOVERY_PROPOSED"
                            or event.idempotency_key != entry.correlation_key
                            or event.occurred_at != entry.created_at):
                        raise ValueError
                elif event.reason == "HUMAN_APPROVED":
                    require_approver(event.actor)
                    approval_fields = dict(entry_id=entry.entry_id, approved_by=event.actor,
                                           idempotency_key=event.idempotency_key)
                    if details:
                        if set(details) != {"payer_reference"}:
                            raise ValueError
                        require_identifier(details["payer_reference"])
                        approval_fields.update(details)
                    expected_request = _request_hash("approve", **approval_fields)
                    if event.to_state != State.APPROVED:
                        raise ValueError
                else:
                    self._validate_payment_event(event, entry, history_by_entry[event.entry_id])
                    expected_request = event.request_hash
                if event.reason in {"RECOVERY_PROPOSED", "HUMAN_APPROVED"}:
                    if (event.request_hash != expected_request or event.provider_status is not None
                        or event.provider_invoice_id is not None or event.paid_amount_cents is not None):
                        raise ValueError
                    validate_transition(event.from_state, event.to_state)
                history_by_entry[event.entry_id].append(event)
                all_events[event.event_id] = event
                previous_by_entry[event.entry_id] = event
                global_hash, global_seq = event.event_hash, event.global_seq
                if checkpoint == IntegrityCheckpoint(global_seq, global_hash):
                    checkpoint_seen = True
            if set(entries) != set(previous_by_entry) or not checkpoint_seen:
                raise ValueError
            self._validate_payment_tables(connection, all_events)
            return IntegrityCheckpoint(global_seq, global_hash)
        except (ValueError, TypeError, KeyError, RecursionError, InvalidInput, IllegalTransition, PaymentError):
            raise IntegrityViolation("Ledger integrity verification failed.") from None

    @staticmethod
    def _validate_time(value: str) -> None:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo != timezone.utc or parsed.isoformat(timespec="microseconds") != value:
            raise ValueError

    @staticmethod
    def _entry(connection: sqlite3.Connection, entry_id: str) -> LedgerEntry:
        row = connection.execute("SELECT * FROM ledger_entries WHERE entry_id = ?", (entry_id,)).fetchone()
        if row is None:
            raise EntryNotFound("Ledger entry does not exist.")
        return LedgerEntry(**dict(row))

    @staticmethod
    def _existing(connection: sqlite3.Connection, key: str, request_hash: str) -> LedgerEvent | None:
        row = connection.execute("SELECT * FROM ledger_events WHERE idempotency_key = ?", (key,)).fetchone()
        if row is None:
            return None
        if row["request_hash"] != request_hash:
            raise IdempotencyConflict("Idempotency key was already used for a different operation.")
        return _event_from_row(row)

    @staticmethod
    def _insert_workflow_event(connection: sqlite3.Connection, entry: LedgerEntry,
                               *, approval_actor: str | None, key: str,
                               request_hash: str, occurred_at: str, payer_reference: str | None = None) -> LedgerEvent:
        # Even this internal method cannot be used to choose a payment state.
        target = State.PROPOSED if approval_actor is None else State.APPROVED
        if approval_actor is not None:
            require_approver(approval_actor)
        previous = connection.execute(
            "SELECT * FROM ledger_events WHERE entry_id = ? ORDER BY seq DESC LIMIT 1",
            (entry.entry_id,),
        ).fetchone()
        previous_state = State(previous["to_state"]) if previous else None
        validate_transition(previous_state, target)
        head = connection.execute(
            "SELECT global_seq, event_hash FROM ledger_events ORDER BY global_seq DESC LIMIT 1"
        ).fetchone()
        payload = dict(
            event_id="evt_" + uuid4().hex, entry_id=entry.entry_id,
            seq=previous["seq"] + 1 if previous else 1,
            global_seq=head["global_seq"] + 1 if head else 1,
            from_state=previous_state, to_state=target,
            provider_status=None, provider_invoice_id=None, paid_amount_cents=None,
            actor=approval_actor if approval_actor is not None else "system",
            reason="HUMAN_APPROVED" if approval_actor is not None else "RECOVERY_PROPOSED",
            occurred_at=occurred_at, idempotency_key=key, request_hash=request_hash,
            entry_hash=_digest(asdict(entry)),
            prev_hash=previous["event_hash"] if previous else GENESIS_HASH,
            global_prev_hash=head["event_hash"] if head else GENESIS_HASH,
            details_json=json.dumps({"payer_reference": payer_reference}, sort_keys=True, separators=(",", ":")) if payer_reference else "{}",
        )
        payload["event_hash"] = _digest(payload)
        columns = ", ".join(payload)
        placeholders = ", ".join("?" for _ in payload)
        connection.execute(f"INSERT INTO ledger_events ({columns}) VALUES ({placeholders})", tuple(payload.values()))
        return LedgerEvent(**payload)

    def _propose(self, *, idempotency_key: str, amount_cents: int, currency: str) -> LedgerEntry:
        require_identifier(idempotency_key)
        require_amount(amount_cents)
        require_currency(currency)
        request_hash = _request_hash("propose", amount_cents=amount_cents,
                                     currency=currency, idempotency_key=idempotency_key)
        with self._transaction(write=True) as connection:
            existing = self._existing(connection, idempotency_key, request_hash)
            if existing:
                return self._entry(connection, existing.entry_id)
            entry = LedgerEntry("entry_" + uuid4().hex, idempotency_key, amount_cents,
                                currency, "paypal_sandbox", _utcnow())
            connection.execute("INSERT INTO ledger_entries VALUES (?, ?, ?, ?, ?, ?)", tuple(asdict(entry).values()))
            self._insert_workflow_event(connection, entry, approval_actor=None,
                                        key=idempotency_key, request_hash=request_hash,
                                        occurred_at=entry.created_at)
            return entry

    def _approve(self, entry_id: str, *, idempotency_key: str,
                 expected_sequence: int, approved_by: str, payer_reference: str | None = None) -> LedgerEvent:
        require_identifier(entry_id)
        require_identifier(idempotency_key)
        require_sequence(expected_sequence)
        require_approver(approved_by)
        fields = dict(entry_id=entry_id, approved_by=approved_by, idempotency_key=idempotency_key)
        if payer_reference is not None:
            require_identifier(payer_reference)
            fields["payer_reference"] = payer_reference
        request_hash = _request_hash("approve", **fields)
        with self._transaction(write=True) as connection:
            existing = self._existing(connection, idempotency_key, request_hash)
            if existing:
                return existing
            entry = self._entry(connection, entry_id)
            actual = connection.execute("SELECT MAX(seq) FROM ledger_events WHERE entry_id = ?", (entry_id,)).fetchone()[0]
            if actual != expected_sequence:
                raise SequenceConflict("Ledger entry changed; read its current sequence before retrying.")
            return self._insert_workflow_event(connection, entry, approval_actor=approved_by,
                                                key=idempotency_key, request_hash=request_hash,
                                                occurred_at=_utcnow(), payer_reference=payer_reference)

    def get(self, entry_id: str) -> LedgerSnapshot:
        require_identifier(entry_id)
        with self._transaction() as connection:
            entry = self._entry(connection, entry_id)
            events = tuple(_event_from_row(row) for row in connection.execute(
                "SELECT * FROM ledger_events WHERE entry_id = ? ORDER BY seq", (entry_id,)))
            return LedgerSnapshot(entry, events)

    def list_entries(self) -> tuple[LedgerSnapshot, ...]:
        with self._transaction() as connection:
            result = []
            for row in connection.execute("SELECT * FROM ledger_entries ORDER BY entry_id").fetchall():
                entry = LedgerEntry(**dict(row))
                events = tuple(_event_from_row(event) for event in connection.execute(
                    "SELECT * FROM ledger_events WHERE entry_id = ? ORDER BY seq", (entry.entry_id,)))
                result.append(LedgerSnapshot(entry, events))
            return tuple(result)

    def verify_integrity(self, checkpoint: IntegrityCheckpoint | None = None) -> IntegrityCheckpoint:
        if checkpoint is not None and (
            not isinstance(checkpoint, IntegrityCheckpoint)
            or type(checkpoint.global_seq) is not int or checkpoint.global_seq < 0
            or type(checkpoint.event_hash) is not str or len(checkpoint.event_hash) != 64
        ):
            raise InvalidInput("Integrity checkpoint is invalid.")
        with self._connection() as connection:
            connection.execute("BEGIN")
            return self._verify(connection, checkpoint)
