# PayPal and recovery ledger implementation status

Integrated release (2026-11-03): the shared API now supplies administrator
authentication, CSRF-protected approval/invoice commands, server-owned payer
resolution, and periodic reconciliation. The React website consumes the existing
Member 3 serializers and verification services. See the current
[integration report](../../../docs/INTEGRATION_REPORT.md) and
[API notes](../api/README.md). Historical standalone reports below describe
earlier stages; live Sandbox acceptance is still skipped by the user's choice.

Member 3 only. The PayPal Sandbox client, approved invoice create/send flow,
fresh-fetch verification, reconciliation, and optional webhook handler are
implemented. All automated offline checks use synthetic data and scripted
transport responses. Live Sandbox behavior and deployment are not yet verified.

Member 4's standalone code-review approval was reported on 2026-10-31. The
offline baseline was rerun successfully that day. See
[LIVE_ACCEPTANCE.md](LIVE_ACCEPTANCE.md) for the remaining credentialed tests,
account setup, and shared release dependencies. Contract/API approval and live
acceptance remain separate from standalone code review.

The foundation includes immutable ledger models, transition policy, transactional
SQLite storage, human approval, and offline adversarial tests. See
[`../ledger/README.md`](../ledger/README.md) for interfaces, limits, and commands,
and [`ARCHITECTURE.md`](ARCHITECTURE.md) for resolution of source-document conflicts.

## Build sequence

1. Ledger foundation and offline tests.
2. Demo-labelled contract proposal for Member 4 review.
3. Sandbox configuration guard and Decimal money helpers.
4. PayPal client with in-memory OAuth, transport safeguards, and typed errors.
5. Approved draft creation and send operations with durable operation identities.
6. Fresh-fetch verification with strict amount/currency/invoice matching.
7. Reconciliation of uncertain outcomes.
8. Optional verified, deduplicated webhook triggers.
9. Sandbox runbook, idempotency/error documentation, and release review.

The default test suite requires no credentials and sends no network traffic:

```powershell
python -B -m backend.tests.payments.run_tests
```

Sandbox tests are marked `sandbox` and skipped by default. See
[`SANDBOX_RUNBOOK.md`](SANDBOX_RUNBOOK.md) for explicit opt-in testing and
[`INTEGRATION_HANDOFF.md`](INTEGRATION_HANDOFF.md) for Member 4's review and hosting
work. The user selected the tested Member 3 implementation contract for the
replacement shared example; see [CONTRACT_HANDOFF.md](CONTRACT_HANDOFF.md).

Latest contract/ignore follow-up (2026-11-02): **190 standalone Python passes,
3 live skips; 448 affected integrated passes, 3 live skips**. The four earlier
shared-file failures are resolved locally; the replacements still need the
user's push. See [CONTRACT_HANDOFF.md](CONTRACT_HANDOFF.md) and the historical
[branch review](reviews/GITHUB_COMPATIBILITY_2026-11-02.md) for scope and results.

Read-only exports for the supplied forecast and rescue schemas are documented
in [TEAM_COMPATIBILITY.md](TEAM_COMPATIBILITY.md). They preserve payment truth,
reject unrepresentable states and never execute recommended actions.

See [`SECURITY_REVIEW.md`](SECURITY_REVIEW.md) for findings, fixes, executed test
results and release dependencies. The default combined runner blocks network
connections and overrides inherited Sandbox opt-in; use `--sandbox` explicitly.
Postman guards have an offline check using the existing Node runtime:

```powershell
node --test backend/tests/payments/postman_guards.test.cjs
```

The root `.gitignore` has now been added with the user's explicit authorization
and tested using temporary Git repositories. It excludes private environments,
ledger databases/journals/backups, keys, logs and caches while retaining blank
templates. This folder still has no Git repository/history. Import the reviewed
Member 3 files into the team's feature branch; check the actual destination's
ignore rules and history before committing. No Sandbox integration run has
been claimed. See [MEMBER3_TEAM_REPORT.md](MEMBER3_TEAM_REPORT.md) for the team handoff.

## Security and recovery behavior

Only `VerificationService.verify(entry_id)` can mint a one-use observation after
a fresh PayPal GET. It checks the approved invoice identity, amount, currency,
reference, invoice number, recipient fingerprint, and PayPal transaction evidence.
Redirects, AI output, client status fields, and signed webhook bodies cannot
produce verified cash. Partial and offline payments contribute zero.

Creation and sending claim durable unique operation keys before dispatch and use
stable `PayPal-Request-Id` headers. Ambiguous outcomes retain the previous state
and require reconciliation; a repeat never blindly dispatches another write.
Safe reads have bounded retries. Transport/auth/rate-limit failures are honest
typed errors, not evidence of a new payment state. See the runbook for recovery.

OAuth acquisition and send preflight run before the durable dispatch claim.
Failures in those preliminary steps leave the ledger unchanged and can be
retried with the same key. Immediately before the invoice-changing call, a trusted
service callback commits the unique claim and supplies its saved request ID.
Once claimed, uncertainty never permits redispatch. Older claims retain their
conservative recovery policy.

Only USD is supported. This module owns no HTTP routes or authentication system;
the shared API now supplies them, its scheduler, and the deployment entrypoint.
Python process access and database-admin
access are trusted boundaries; the hash chain is not protection against an
administrator rewriting the entire database. Independently stored checkpoints
and backups remain deployment duties.

`audit.py` provides an isolated payment logger and handler filter retaining only
known event/state labels. Arbitrary messages, exceptions and extras are discarded.
Shared application/access logging still needs owner configuration and review;
this module does not change global logging settings.

## Pre-merge checklist

- [x] Sandbox host pinned; verified TLS; redirects disabled; bounded transport.
- [x] Integer cents and centralized strict Decimal conversion.
- [x] Approval before create/send, fresh fetch before verified cash, no generic
  status setter; malformed/unknown statuses never count as paid.
- [x] Unique operation/event keys, append-only triggers, financial and receipt
  hash chains, transaction rollback, tampering and concurrency tests.
- [x] Signature verification before webhook deduplication and fresh invoice GET.
- [x] Fixed sanitized errors; tokens in memory; no full bodies or payer emails
  logged or persisted by these modules; secret-free examples.
- [x] Shared integration authenticates and authorizes financial operations,
  requires explicit approval, and resolves the test payer from server configuration.
- [x] Root ignore rules added and tested, including nested paths and detection
  of already tracked ignored files. Source/template files remain visible.
- [x] Offline SQLite backup/fresh-process recovery drill, including WAL data,
  duplicate receipts, uncertain claims and stale/empty/corrupt backup checks.
  See [the recovery runbook](../ledger/RECOVERY_RUNBOOK.md); this does not complete
  the hosted persistence and restore acceptance below.
- [x] Destination ignore protections verified; staged changes and fetched Git
  history scanned with Gitleaks. No leaks were detected by that scan.
- [ ] Execute opt-in Sandbox create/send, manually pay, verify, and retain results
  without secrets or personal data; run shared backend tests after integration.
- [ ] Provision persistent storage, backup/restore checks, external checkpoints,
  periodic reconciliation, and restricted production-server access.
- [ ] Complete the root module checklist items that require the shared API,
  credentials, hosted demo, and other members' integration.

## Tool usage register

| Tool | Role | External payment access |
|---|---|---|
| Python standard library | Domain models, SHA-256 canonical hashing, validation | None |
| SQLite via `sqlite3` | Local transactional append-only storage | None |
| `unittest` | Offline unit, tampering, rollback, and concurrency tests | None |
| Existing Node built-in test/vm/assert | Execute Postman guards against a fake runtime | None |
| Existing Git CLI | Validate ignore rules and tracked-file detection in temporary repositories | None; no push |
| GitHub connector / isolated Git checkout | Inspect supplied branch revisions and limited history scan | Repository reads only |
| Ubuntu WSL and temporary pytest/scientific dependencies | Run unchanged forecast/rescue suites and cross-module tests | Network blocked during tests |
| PayPal public API documentation | Response schemas and signature/idempotency behavior | Documentation only |
| Postman collection files | Five diagnostic templates; guards tested locally, no actual Postman/PayPal run | None so far |
| Render public documentation | Persistent-storage and environment-variable handoff | No deployment |
| React, TypeScript, Vite, Zod | Website and strict response validation in shared frontend | No credential handling in browser |
| FastAPI, Uvicorn, python-dotenv | Shared authenticated API and private configuration | Existing Sandbox client only |
| Playwright / local Chrome | End-to-end browser tests against isolated fake-provider servers | None |
| Gitleaks / pip-audit / npm audit | Redacted history/staged-secret scans and dependency checks | None |
| Prettier | Format new frontend source and tests for team maintenance | None |

APIMatic was evaluated and not adopted: the five required operations are already
covered by a small handwritten wrapper; generation would still need the same
validation and security wrapper. No generated client, external dependency,
Zapier workflow, or AI model is in the payment path. Check each sponsor's Devpost
page for this hackathon's actual offer before using its service. Update this
register after real collection runs or deployment.
