# Member 3 Sandbox runbook

Status: offline tests pass; no credentialed Sandbox calls have been run by the
coding agent. Fake responses validate local behavior, not PayPal compatibility.
PayPal is the only gateway. No AI model participates in payment verification.

## Before credentials

The root `.gitignore` is now supplied and tested. Ask the repository owner to
import the module into the team's Git repository/feature branch and verify its
effective ignore rules using `git check-ignore` before creating a private `.env`
or committing. An existing tracked file is not protected by a later ignore rule;
the owner must review tracked files and history too. This folder has no Git
history to inspect.

Use a PayPal Sandbox business account/app and a separate Sandbox personal payer.
Keep credentials in a local ignored `.env` loaded by the shared application or
in private process environment variables. This stdlib module reads environment
variables; it does not parse `.env` itself. Never paste credentials into chat,
source, command arguments, test fixtures, response examples, or screenshots.
The owned `.env.example` is a blank template only.

From the project root, inspect local prerequisites without making requests or
opening the ledger:

```powershell
python -B -m backend.tests.payments.sandbox_readiness
```

The report contains fixed labels and booleans only. Exit 1 means prerequisites
are missing; exit 0 means its local checks passed. It checks configuration,
the database parent directory, root/nested ignore probes, tracked ignored files,
and which integration tests the environment selects. A selected create/send
test creates a new invoice on each run. This command never runs those tests.
It does not authenticate credentials, prove filesystem permissions/persistence,
scan history for secrets, or replace the release checklist. Run it again in the
same privately configured shell immediately before the explicit Sandbox suite.

The installed root `.gitignore` includes these minimum rules, plus private env
variants, SQLite variants/backups, private keys, logs and credentialed Postman
exports. Review existing tracked files and Git history separately:

```gitignore
.env
data/
*.db
*.db-wal
*.db-shm
*.db-journal
__pycache__/
*.py[cod]
```

| Variable | Value / purpose |
|---|---|
| `PAYPAL_MODE` | Required: `sandbox` |
| `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` | Private Sandbox app credentials |
| `LEDGER_DB_PATH` | Persistent SQLite file in an existing restricted directory |
| `PAYPAL_HTTP_TIMEOUT_SECONDS` | Integer 1–30; default 10 per transport attempt |
| `PAYMENTS_MAX_INVOICE_CENTS` | Positive integer; default 1000000 |
| `PAYMENTS_ALLOWED_CURRENCIES` | `USD` only |
| `PAYPAL_WEBHOOK_ID` | Sandbox app's webhook registration ID; required for handler |

Do not configure a live URL or host. The API base is hardcoded to
`https://api-m.sandbox.paypal.com`. Any provided `PAYPAL_*URL`/`PAYPAL_*HOST`
configuration must match its pinned base/host exactly or startup fails.

## Offline baseline

From the project root:

```powershell
python -B -m backend.tests.payments.run_tests
```

All default tests use synthetic records and fake transport responses. Sandbox
tests are skipped unless explicitly enabled. No external packages are needed.
The combined runner overrides inherited `RUN_PAYPAL_SANDBOX_TESTS=1` unless
`--sandbox` is provided, and blocks DNS/TCP calls during offline execution.
On this Windows machine, the test runner needed permission outside the sandbox
to access temporary SQLite databases; it still made no network calls.

## Opt-in Sandbox checks

Prepare the private environment first. Tests retain records in `LEDGER_DB_PATH`;
do not point them at another member's database or remove the ledger between runs.
If its schema is incompatible, stop and plan a reviewed migration.

1. Set `PAYPAL_SANDBOX_INVOICE_ID` privately to an existing Sandbox invoice.
   Enable integration discovery using the explicit command below. Without the
   additional variables for other tests, only this read-only fetch test runs.

   ```powershell
   python -B -m backend.tests.payments.run_tests --sandbox
   ```

2. To create/send, configure `PAYPAL_SANDBOX_PAYER_EMAIL` privately to the Sandbox
   personal account. Set `PAYPAL_SANDBOX_ALLOW_SEND` to the exact acknowledgement
   `I_APPROVE_A_ONE_CENT_SANDBOX_INVOICE`. Run the command once. This records an
   operator approval in the ledger before creating/sending a USD one-cent invoice.
   Each full rerun with this acknowledgement creates a NEW approved entry/invoice;
   it is not an idempotency replay test. Unset the acknowledgement after the run.
3. Inspect the entry using the authenticated application or trusted local runtime
   `ledger.list_entries()` and `payments.contracts.entry_view`. Use the saved
   Sandbox invoice URL. Pay manually as the Sandbox personal payer; no test code
   automates payment or interprets the browser return as payment evidence.
4. Set `PAYPAL_SANDBOX_PAID_ENTRY_ID` to that existing ledger entry, with the send
   acknowledgement unset. Run the command again. Verification must fetch PayPal,
   match the approved terms, record VERIFIED_PAID, and pass integrity checks.
   Confirm `ledger.recovered_cash()` includes its integer cents exactly once.
5. Re-run verification for that entry and confirm no duplicate financial event.
   Save only sanitized test counts, timestamps, states, and opaque references.
   Do not save raw OAuth/invoice/webhook responses in Git or logs.

Strict schema parsing may expose a mismatch with real PayPal responses. If so,
keep the entry unverified, inspect privately, and add a sanitized fake fixture
and regression test before changing validation. Never loosen validation merely
to make a demo report success.

## Recovery and errors

| Condition | Meaning and operator action |
|---|---|
| OAuth or send preflight fails before the dispatch claim | No invoice-changing call or ledger write occurred. Correct the problem and retry with the same key; eligibility is rechecked. |
| Timeout, rate limit, authentication or provider outage | State stays unchanged. Correct credentials or wait, then fresh verification/reconciliation. |
| HTTP 408, redirect, conflict, or unexpected HTTP result | No terminal failure is inferred. Reads retry only where safe; a claimed invoice write remains uncertain and must be reconciled, never blindly repeated. |
| Create/send outcome uncertain | Durable claim remains. Call `runtime.reconciliation.reconcile(entry_id)`; never invent another key and resend. |
| No matching invoice or multiple search matches | `RecoveryRequired`; inspect in Sandbox dashboard and retain all history. No automatic repost. |
| Claimed send remains DRAFT | Review required: service will not automatically resend an uncertain request. |
| Invalid amount/currency/identity/recipient/payment evidence | Never count as recovered; fresh verification records UNRESOLVED when allowed. Investigate approved terms. |
| Sequence conflict | Another write won; fetch again rather than committing stale evidence. |
| Contradictory/unknown result for a terminal entry | RecoveryRequired; no state or cash change. Preserve terminal history for review. |
| Integrity violation or incompatible schema | Stop financial writes/reporting, preserve DB, investigate against trusted backups/checkpoints. No automatic repair. |

The periodic sweep must be connected by the shared backend. It revisits bound
entries, including verified entries for refund detection. A webhook receipt may
be committed before an outage; duplicate delivery is acknowledged, so the sweep
is responsible for completing the missed verification.

An existing claim from an earlier version or a crash immediately after claim
commit is still uncertain. Do not delete it or infer from an authentication error
alone that the invoice POST could not have happened. The new safe retry boundary
prevents future preliminary failures from consuming claims; it does not
retroactively classify old attempts.

## Webhook and diagnostics

After the owner deploys a HTTPS route, register it on the same Sandbox app and
configure its webhook ID. Pass original bounded request bytes and signature
headers to `runtime.webhooks.handle`; never pass parsed status directly to the
ledger. Test genuine signed delivery privately, duplicates, and out-of-order
notifications. Public demo users must not control webhook configuration.

The [Postman collection instructions](postman/README.md) cover OAuth, create,
send, get, and signature verification. Before using Postman or Render, check its
Devpost page for this hackathon's actual offer. The collection is diagnostic;
the application flow should run through `InvoiceService` and verification.

## Completion evidence still required

- Actual create/send/manual-pay/verify results using Sandbox credentials.
- Shared API authorization, error mapping, and UI contract review.
- Persistent hosting, restart survival, backups, reconciliation scheduling.
- Repository/history secret scan and the shared pre-merge checklist.

Offline tests alone do not satisfy these release criteria.
