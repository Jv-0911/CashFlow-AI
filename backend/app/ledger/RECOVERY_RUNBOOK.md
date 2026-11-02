# Ledger backup and recovery handoff

This procedure belongs to the trusted deployment operator. It does not add an
HTTP endpoint, change payment states, or authorize invoice dispatch. The offline
drill uses temporary databases and fake PayPal responses; hosted durability and
real provider reconciliation still need their own acceptance checks.

## Prepare a recoverable backup

1. Restrict access to the database directory and backup destination. Keep backups
   outside Git and public artifacts. Even without payer emails or credentials,
   they contain financial history and opaque customer references. Use protected,
   independently retained storage and the deployment owner's retention policy.
2. For an exact checkpoint/backup pair, pause all ledger writers and wait for
   in-flight operations to finish. This includes API actions, webhook handlers
   and reconciliation. Record `ledger.verify_integrity()` and retain its
   `global_seq` and `event_hash` outside the database in trusted storage.
3. Use SQLite's connection `backup()` API to a new, uniquely named destination.
   Open the source with a read-only SQLite URI (`mode=ro`) so a wrong source path
   cannot silently create a database. Close both connections when finished.
   Do not overwrite an earlier backup or copy just the main file of a live DB:
   committed records may still reside in its WAL. A filesystem-level backup
   needs an independently validated consistency mechanism.
4. Validate a disposable copy of the completed backup with the same reviewed
   application version: open `LedgerService(copy_path)` and call
   `verify_integrity(saved_checkpoint)`. With writers paused, the returned
   checkpoint must exactly match the saved checkpoint. Compare entries, states,
   integer cash totals, bindings and operation identities with the source.
5. Retain the completed backup's SHA-256 digest and checkpoint in independently
   trusted storage, along with UTC time, application version and non-sensitive
   counts. A digest stored beside a writable backup is not a trusted anchor.
   The whole-file digest protects that backup's receipt records too; the ledger's
   financial checkpoint alone does not anchor the separate receipt-chain tail.
6. Resume service only after validation succeeds. Keep updating independent
   financial checkpoints as history advances. The hosting owner must implement
   and monitor backup/checkpoint scheduling, storage permissions and retention;
   this module does not provide that infrastructure.

SQLite's backup API also permits a consistent snapshot while the source changes.
However, a checkpoint captured separately might describe an earlier or later
snapshot. The paused procedure above avoids treating those as an exact pair.

## Restore without reissuing uncertain payments

1. Stop application writers, webhook processing and scheduled sweeps. Preserve
   the current database and associated journals for investigation. Never replace
   a database while connections are open, combine it with another database's WAL,
   or edit its rows, triggers, schema or operation keys to make recovery pass.
2. Select an existing, non-empty backup. Check its whole-file digest against the
   independently retained value before opening it. Validate a separate recovery
   copy, leaving the original backup and failed database untouched.
3. Call `verify_integrity()` with the **latest independently trusted financial
   checkpoint**, not merely a checkpoint calculated from the restored copy.
   Opening a new/empty path is allowed during normal startup, so successful
   `LedgerService(...)` construction alone is not proof of restoration.
4. A missing checkpoint or a backup older than the latest checkpoint leaves a
   recovery gap. Keep invoice creation/sending disabled and escalate to the
   operator and Member 3. Do not substitute an older checkpoint to bypass the
   failure. Recover missing history from trusted retained data; this module has
   no automatic merge, migration or reconstruction feature.
5. Even a matching checkpoint cannot prove that no later operation happened
   after that checkpoint was saved. Determine the backup's recovery point and
   account for all subsequent dispatches before resuming writes. A lost create
   claim can otherwise cause a duplicate invoice. PayPal search alone cannot
   reconstruct missing human approvals or authorize a replacement proposal.
6. For intact histories, inspect saved operation claims and invoice bindings.
   A timeout or restart does not release a claim. Use the existing reconciliation
   service to recover uncertain outcomes through server-side PayPal reads when
   account access is available. Do not create new keys, reset claims, manually
   mark entries paid, or repeat create/send as a recovery shortcut.
7. Promote only the validated recovery copy through the owner's stopped-service
   deployment procedure. Recheck integrity/checkpoint after restart. Before
   enabling payment actions, reconcile intact entries and verify actual hosting
   persistence, authorization and scheduling. Provider outages preserve the last
   state and leave recovery incomplete; restored totals are historical verified
   observations, not a new confirmation from PayPal.

## Offline evidence and remaining limits

Run from the project root:

```powershell
python -B -m backend.tests.payments.run_tests
```

`backend/tests/ledger/test_recovery_drill.py` exercises:

- Verified cash, full history, bindings and operation identities after a SQLite
  backup and a separate Python process restart.
- A restored duplicate webhook still needs signature verification and performs
  no invoice fetch or additional financial write.
- Uncertain create/send claims still reject redispatch without provider calls.
- Consistent capture of committed WAL records.
- Rejection of stale backups against newer trusted checkpoints, corrupt backup
  files, and empty replacement ledgers against a non-empty checkpoint.

Network access is blocked in both the suite and the restarted test process.
The drill does not simulate power loss, prove filesystem durability, configure
external anchors, or restore a deployed server. Re-run the deployment-specific
drill on the actual persistent volume before hosted acceptance.
