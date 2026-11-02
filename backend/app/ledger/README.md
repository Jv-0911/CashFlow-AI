# Recovery ledger

This module implements proposals, explicit human approval, immutable invoice
bindings and operation claims, and verified payment history. Payment services
in `../payments/` own PayPal access; only fresh-fetch verification may write
VERIFIED_PAID. State-machine definitions alone confer no write authority.

## Runtime and tests

Uses Python 3.11+ and its standard library (`sqlite3`, `hashlib`, `unittest`).
SQLite must support STRICT tables (3.37+). No packages were installed or added.
Run from the project root:

```powershell
python -B -m unittest discover -s backend/tests/ledger -p 'test_*.py' -v
```

Tests use temporary databases containing synthetic identifiers and integer
amounts. They make no network calls. Direct corruption SQL appears only in
tests to simulate an administrator bypassing the database guards.

## Service interface (internal; not an HTTP contract)

`LedgerService(db_path)` opens or creates a dedicated database in an existing
directory and checks integrity. Existing incompatible schemas are rejected;
there is no automatic migration or repair. The database path is a trusted
server configuration value and must never come from a request body.

- `propose(idempotency_key=..., amount_cents=..., currency="USD")` atomically
  inserts the immutable entry and its initial `PROPOSED` event.
- `approve(entry_id, idempotency_key=..., expected_sequence=...,
  approved_by=..., payer_reference=...)` appends `APPROVED`. A server-owned
  payer reference is required for subsequent invoice operations. Member 4's authenticated server code
  must derive the principal from the authenticated session and check that
  the human may approve that entry. Never copy `approved_by` from client or
  AI input. The ledger itself cannot authenticate a human.
- `get(entry_id)` and `list_entries()` return immutable snapshots. The latest
  event supplies current state and sequence; entry data never changes.
- `recovered_cash()` returns integer cents grouped by currency and has no
  parameter for including other states. Only current VERIFIED_PAID entries
  count; partial/offline/refunded entries contribute zero.
- `verify_integrity(checkpoint=None)` returns an `IntegrityCheckpoint` or
  raises `IntegrityViolation`. A trusted earlier checkpoint can detect
  deletion of the chain tail or rollback past that checkpoint.

Identifiers are bounded opaque references, not emails or free-form text.
Money must be a positive Python integer within SQLite's signed 64-bit range;
booleans, floats, strings, and unsupported currencies are rejected. USD is the
only supported currency. Payment services also enforce their configured business
amount limit; Decimal conversion is centralized in `payments/money.py`.

## Persistence guarantees

- Entries, events, invoice bindings, operation claims, and webhook receipts have insert/read operations
  only. Database triggers reject updates, deletes, and replacement inserts,
  including when a connection has recursive triggers disabled.
- SQL uniqueness covers entry correlation keys, event idempotency keys,
  event sequence per entry, global sequence, and invoice bindings. The
  invoice-binding table enforces one invoice per entry and one entry per
  invoice. Operation claims and webhook provider event IDs are also unique.
- `BEGIN IMMEDIATE` serialises write decisions. Expected-sequence checks
  reject stale competing writes. An idempotent repeat returns the original
  result; reuse with changed request content raises `IdempotencyConflict`.
- An entry and its first event commit atomically. Exceptions roll back the
  transaction. SQLite uses full synchronous durability on local storage.
- SHA-256 covers canonical event fields and immutable entry metadata. Events
  link to both the preceding event for their entry and the preceding event
  globally, preventing undetected removal of an entire intermediate entry.
  Webhook receipts use a separate hash chain and never append paid-state events.
- Schema, triggers, foreign keys, hashes, sequences, operation fingerprints,
  and supported state transitions are checked on startup and before every
  service read/write. Corruption blocks both writes and cash reporting.
- Errors have fixed messages; no caller content, database paths, provider
  bodies, credentials, or tokens are logged or included in error messages.

## Limits that matter

Python module privacy and an actor string are **not** security boundaries
against arbitrary code running in the backend process. All backend code is
trusted; hostile HTTP input must go through authenticated, narrow service
commands. File permissions must prevent untrusted users from opening the DB.

A hash chain alone cannot detect deletion of its own tail, complete database
replacement, or a consistent rewrite by someone controlling the database.
The optional financial checkpoint detects rollback only when retained in independently
trusted storage; it does not anchor the separate receipt-chain head. This module
does not deploy external anchor storage. Backups,
access controls, and persistent hosting remain deployment responsibilities.

See [RECOVERY_RUNBOOK.md](RECOVERY_RUNBOOK.md) for consistent backup creation,
independent checkpoint validation, and safe restore handling. Offline tests
exercise backup and fresh-process restart, including uncertain dispatch claims
and committed WAL records; actual hosted restore acceptance remains pending.

Integrity scans are linear in history size and intentionally conservative for
the small Sandbox demo. This implementation is not a production payment system.
Offline payment tests also exercise bindings, fresh verification, outages,
webhooks, and reconciliation. Run the combined suite using
`python -B -m backend.tests.payments.run_tests`. Live Sandbox tests are opt-in;
see `../payments/SANDBOX_RUNBOOK.md`. No shared HTTP routes are implemented here.
