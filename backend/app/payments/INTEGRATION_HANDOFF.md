# Member 4 review and shared-backend handoff

Member 3 implementation is isolated under payments/ledger and their tests. The
user authorized selecting the tested implementation contract and merging ignore
protections. See [CONTRACT_HANDOFF.md](CONTRACT_HANDOFF.md) for the replacement
files and field mapping. Shared routes/UI must use that format; no route was changed.

Start with [MEMBER3_TEAM_REPORT.md](MEMBER3_TEAM_REPORT.md) for the complete
delivery summary, test evidence, review assignments and outstanding dependencies.
The user separately authorized the root `.gitignore`; it is now supplied/tested.

## Files to review

- `contracts/payment-ledger.example.json`: demo-labelled contract, integer cents,
  approval input, nullable provider fields, and recovered total semantics.
- `backend/app/payments/contracts.py`: implementation serializers and sanitized error
  envelope; no HTTP status/route decisions are imposed.
- `backend/app/payments/runtime.py`: internal service composition.
- `backend/app/payments/ARCHITECTURE.md`: resolved conflicts and trust boundaries.
- `backend/app/payments/SANDBOX_RUNBOOK.md`: live validation still required.

Approval means the team agrees on field names, nullability, currency/amount
meaning, authorized operations, and the display distinction between proposals
and verified outcomes. It does not itself send invoices or prove payments.

## API integration responsibilities

For the supplied Member 1 forecast and Member 2 rescue modules, use the
[read-only evidence adapters](TEAM_COMPATIBILITY.md). Keep their incomplete
evidence errors visible. Recovery totals do not establish opening bank cash or
complete daily actuals. No shared HTTP/schema change is included in these adapters.

Construct `PaymentRuntime.from_env(recipient_resolver)` once during startup,
after provisioning the database directory. It validates Sandbox configuration
and checks schema/integrity. Fail startup if either check fails.

The resolver is a server-owned lookup from an approved payer reference to the
correct Sandbox recipient email. Enforce tenant/entry ownership before every
read or write, including totals. The internal ledger has no tenant filtering;
do not expose `ledger_view()` across users or tenants without a reviewed
isolation design. A single-tenant demo must enforce that boundary explicitly.

Authenticated server code must derive `approved_by` from the human session,
verify permission, and record `ledger.approve(...)` with `payer_reference`,
`expected_sequence`, and a stable idempotency key. Never accept actor labels,
provider status, paid amounts, recipient replacement, or verification proof
from a client or AI. Protect state-changing browser actions against CSRF as
appropriate to the chosen session mechanism.

Use `invoices.create_draft` and `invoices.send` only after approval. Use
`verification.verify(entry_id)` for explicit refresh; it accepts no paid-state
input. Call `ledger.recovered_cash()` for trusted totals. Display unknown,
partial, offline, failed, and unresolved states honestly. A redirect may ask
the server to refresh but cannot signal payment completion.

Set server request/body limits and rate limits. For webhooks, pass original
bounded bytes and headers to the handler; acknowledge returned `processed`,
`duplicate`, or `unknown_invoice` results as appropriate. Map invalid signatures
and provider errors honestly without echoing input. Keep access/error logs free
of Authorization headers, webhook bodies, payer emails, and credentials. Do not
serialize exception internals or request objects.

For payment logging, `payments.audit.make_payment_logger(stream)` creates an
isolated filtered logger. Emit `log_event(logger, AuditEvent.OPERATION_FAILED)`
or another explicit event, optionally with a State enum. The handler discards
free text, arguments, exception/stack traces and custom fields. If using your
own handlers, attach `SafePaymentLogFilter` to every payment handler, including
structured handlers; a filter on a parent logger alone does not protect child
records. This does not replace approval records in the ledger or sanitize
unrelated shared access/application logging.

Schedule `runtime.reconciliation.sweep()` periodically with bounded overlap;
report only sanitized results. The transport timeout is per attempt, with up to
three safe-read attempts plus backoff; account for that in worker/request limits.
The sweep is implemented, but no scheduler or shared HTTP adapter is installed.

## Render settings the owner must configure

Check Render's Devpost offer before adopting its service. No deployment has
been made: this folder has no shared backend entrypoint or Git repository.

1. Connect the reviewed private repository and choose the shared backend's
   actual build/start command. Do not invent an entrypoint for this module.
2. Choose a service supporting a persistent disk. Mount it at `/var/data` and
   set `LEDGER_DB_PATH=/var/data/ledger.db`. The current store is SQLite; changing
   to a hosted SQL database requires an explicitly reviewed adapter/migration.
3. Set private Render environment variables: `PAYPAL_MODE=sandbox`, Sandbox
   client ID/secret, allowed currency `USD`, appropriate maximum invoice cents,
   and webhook ID after registration. Do not put secrets in a committed config.
4. Run one service instance against its local disk. Run reconciliation in that
   service's process/lifecycle: a separate Render cron service cannot share the
   attached disk. An ephemeral filesystem is unacceptable for this ledger.
5. Configure the owner's HTTPS webhook route and register it with the same
   Sandbox app. Verify genuine deliveries after deployment.
6. Restrict filesystem/service access, provision database-consistent backups,
   retain financial checkpoints independently, and test restore and restart
   survival. The provided checkpoint does not anchor the webhook receipt chain.
   Follow the [ledger recovery procedure](../ledger/RECOVERY_RUNBOOK.md). Local
   backup/restart drills are supplied; the owner must still validate the actual
   volume, backup retention and recovery point before enabling invoice dispatch.
7. Run the shared backend suite and the explicit Sandbox runbook before judges
   use the hosted flow. Update the tool register with what was actually used.

Render documents its [persistent disk limits](https://render.com/docs/disks)
and [environment configuration](https://render.com/docs/configure-environment-variables).
Disk-backed services have deployment/scaling constraints; confirm the chosen
plan's current capabilities and cost in the dashboard before purchase.

## Outside Member 3 scope

The owner must create the shared routes, authentication/authorization,
repository setup, hosting entrypoint, UI wiring, and scheduler, and verify/merge
the supplied ignore rules in the destination repository. Member 3 has not edited
the shared application areas. AG Grid may be suggested to Member 4 for
the table, but no frontend sponsor dependency was adopted.
