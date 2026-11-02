# CashFlow AI — Member 3 delivery and team review report

**Role:** PayPal & Recovery Ledger Developer  
**Prepared:** 14 October 2026  
**Delivery status:** Standalone code review accepted by Member 4. Shared contract approval, live Sandbox acceptance and shared-application release checks are still pending.

## 1. What this contribution does

**Subsequent contract/ignore resolution, 2 November 2026:** The user authorized
both shared-file fixes. Local results are now **190 standalone passes / 3 live
skips** and **448 affected integrated passes / 3 skips**, with the four previous
failures resolved. No push occurred. See [CONTRACT_HANDOFF.md](CONTRACT_HANDOFF.md)
for the selected format, preserved ignore rules and remaining application wiring.
The following earlier update is retained as historical context.

**Latest update, 2 November 2026:** Added read-only adapters for the supplied
Member 1 branch and user-selected Member 2 ZIP. Final standalone results are
189 Python passes / 3 deferred live skips, 7 Postman passes and 5 separate
cross-module passes. Teammate implementations were unchanged. Shared contract
and ignore-rule mismatches still cause four assembled-repository failures.
Use the [final review report](reviews/GITHUB_COMPATIBILITY_2026-11-02.md) for the
current delivery, exact branch revisions and work remaining before a push.

**Update received 31 October 2026:** Member 4 accepted the standalone code review
and independently confirmed the reported offline test results. Both suites were
rerun successfully. Private Sandbox setup is still absent, so real payment-flow
acceptance remains pending. Follow [LIVE_ACCEPTANCE.md](LIVE_ACCEPTANCE.md) for
the next steps; this does not imply shared contract/API or deployment approval.

**Local recovery follow-up, 31 October 2026:** Added seven offline backup and
restart tests plus a [recovery runbook](../ledger/RECOVERY_RUNBOOK.md). Final
validation: **178 Python tests passed, 3 Sandbox tests skipped** (181 discovered)
and **7 Postman guard tests passed**. Verified cash, immutable operation claims,
invoice bindings and webhook deduplication survive restoration and a separate
process restart; stale/empty/corrupt backup checks and WAL capture are covered.
No payment runtime, schema, API contract or dependencies changed. The deployment
owner must still configure external checkpoints/backups and test the actual
hosted volume; the user has deferred account-dependent PayPal work. Earlier
baseline counts elsewhere in this report describe the previous delivery.

CashFlow AI helps small businesses forecast cash shortages, understand their
causes, and consider recovery actions. Member 3 supplies the payment and audit
boundary: an approved recovery action can become a PayPal Sandbox invoice, and
only fresh server-side PayPal evidence can make it count as recovered cash.

The delivered flow is:

1. Propose an amount in integer USD cents; recovered cash remains zero.
2. Record explicit human approval and an opaque payer reference.
3. Resolve the recipient through trusted server code, then create a draft.
4. Re-fetch and check the draft before sending it.
5. Fetch PayPal again to verify the payment against the approved terms.
6. Append the observed outcome to the ledger; count only VERIFIED_PAID entries.
7. Reconcile uncertain operations and refresh payment states after outages.

No AI output, browser redirect, client status field, or webhook body can directly
mark an entry paid. This is a Sandbox invoicing integration, not a live-money
processor, forecast engine, AI model or complete web application.

## 2. Delivered components

| Component | What is implemented | Main files |
|---|---|---|
| Domain and transition policy | Immutable records, strict IDs/cents/currency, approval requirements, illegal-transition rejection | `ledger/models.py`, `ledger/state_machine.py` |
| Append-only ledger | SQLite transactions, uniqueness constraints, UPDATE/DELETE/REPLACE guards, entry/global event hash chains, integrity validation, external financial checkpoints | `ledger/store.py`, `ledger/payment_events.py` |
| Public ledger service | Propose, approve, read/list, integrity check and a verified-only recovered-cash function | `ledger/service.py` |
| Sandbox configuration | Exact hardcoded Sandbox host, fail-closed environment validation, private credentials, request/amount limits | `payments/config.py`, `payments/.env.example` |
| Money boundary | Strict integer cents and centralized Decimal conversion to/from PayPal strings | `payments/money.py` |
| PayPal client | In-memory OAuth cache, verified TLS, pinned routes, no redirects, bounded response sizes/retries, typed sanitized errors | `payments/paypal_client.py` |
| Provider validation | Strict JSON, identity/amount/currency checks, safe invoice URLs, recipient fingerprints and PayPal transaction checks | `payments/schemas.py` |
| Invoice service | Approval before creation/sending, stable request IDs, durable dispatch claims, repeat protection, send-time draft validation | `payments/invoice_service.py` |
| Verification | Data-driven status mapping, fresh GET, one-use expiring evidence, approved-term checks before paid state | `payments/verification.py` |
| Recovery | Search/bind an uncertain create using its saved invoice number; fresh verification; sweep including refund checks | `payments/reconciliation.py` |
| Optional webhooks | Remote PayPal signature verification, event-ID deduplication, receipt chain, fresh invoice fetch | `payments/webhooks.py` |
| Integration interfaces | Runtime composition, proposed serializers and sanitized error envelope; no shared HTTP routes | `payments/runtime.py`, `payments/contracts.py` |
| Safe logging | Optional isolated logger retaining only approved event/state labels | `payments/audit.py` |
| Diagnostics | Five Sandbox Postman request templates, empty environment template, offline script guards and read-only readiness checker | `payments/postman/`, `tests/payments/sandbox_readiness.py` |
| Handoff protection | Root `.gitignore`, real Git ignore tests, runbook, architecture and integration/security notes | Root `.gitignore`, module documentation |

Paths in this table are relative to `backend/app/` except tests and the explicitly
identified root files. Full delivery folders are listed in section 9.

## 3. Payment and integrity rules enforced

- USD only; monetary inputs are integer cents. Floats and booleans are rejected.
- The only API destination is `https://api-m.sandbox.paypal.com`. Mode/host
  mismatches fail configuration; TLS verification is never disabled.
- Human approval is recorded before both draft creation and sending. The shared
  API must authenticate that human; an actor string alone is not authentication.
- Creation/sending acquire a database-unique operation claim immediately before
  dispatch, after OAuth/preflight. PayPal receives the saved request UUID.
- OAuth/preflight failures before a claim can be retried with the same key.
  Ambiguous writes retain the claim and require reconciliation, never a new key
  to bypass duplicate protection.
- Only verification can supply the one-use observation used for a paid write.
  The invoice ID, approved amount/currency, reference, invoice number, recipient
  fingerprint, PayPal transaction totals, remaining due and refund amount must
  match the rules. Evidence age is checked after acquiring the write transaction.
- Partial, pending, offline-marked, unknown and proposed outcomes contribute
  zero recovered cash. A refunded entry leaves the total entirely. The total is
  not a partial-payment or net-refund accounting report.
- Unknown/malformed statuses are unresolved, never success. Terminal entries
  cannot be automatically reopened; contradictory observations require review.
- Network/auth/rate-limit failures do not change the last payment state.
- Webhook authenticity is checked before deduplication and a fresh invoice GET.
  A receipt followed by a failed GET relies on the reconciliation sweep.
- Ledger writes append events; reads/writes check schema, guards, chains and
  financial invariants. Tokens stay in memory; payer emails are not persisted
  by the ledger. No full provider/webhook payload is logged by this module.

## 4. Bugs found and corrected during the reviews

| Finding | Correction and evidence |
|---|---|
| Malformed OAuth could be mistaken for malformed invoice evidence | OAuth parsing failures are authentication errors and cannot change payment state. |
| Verification evidence could expire while waiting for a transaction | Freshness is checked after the write lock and integrity scan. |
| A truncated HTTP body could end with valid JSON | Incomplete Content-Length responses fail as transport errors. |
| Decimal behavior could depend on ambient application settings | Money helpers use an isolated Decimal context. |
| Corrupt deeply nested ledger JSON could leak an implementation exception | It now produces a sanitized integrity error. |
| Default tests could inherit a live-testing opt-in | The default runner overrides that flag and blocks DNS/TCP APIs. |
| Authentication/preflight failures unnecessarily consumed a dispatch claim | Claims now occur after those checks; race/crash tests preserve at-most-once dispatch. |
| Postman rejection scripts and token handling needed hardening | Explicit skipRequest guards, exact URLs, TLS/redirect settings and stale-token clearing added. |
| Ambiguous HTTP status codes could cause terminal FAILED | HTTP 408 is a timeout; redirects/conflicts/unexpected HTTP results preserve uncertainty. Definite rejections use a restricted status set. |

The latest HTTP regression matrix covers 31 create/send/verification cases.
The old behavior failed 27 of them before the fix; all now pass. Existing
definite-rejection tests still pass. No new state, transition, shared route or
contract shape was introduced in this review.

The full finding register and remaining limitations are in
[SECURITY_REVIEW.md](SECURITY_REVIEW.md).

## 5. Tests and checks actually executed

From the project root:

```powershell
python -B -m backend.tests.payments.run_tests
node --test backend/tests/payments/postman_guards.test.cjs
python -B -m backend.tests.payments.sandbox_readiness
```

| Check | Result / interpretation |
|---|---|
| Python offline suite | 174 discovered: **171 passed, 3 Sandbox tests skipped** |
| Postman JavaScript guards | **7 passed** using Node's built-in test runtime and a fake `pm` object |
| Git ignore tests | 3 tests included in the Python total; actual Git used in isolated temporary repositories |
| Fresh source-copy validation | Same Python suite and Postman guards passed from a temporary copy without the original source path |
| Static validation | All 41 Python files parsed; all 3 JSON files parsed; local module documentation links checked |
| Working-file credential-pattern scan | No matches for the tested private-key/common-token/long credential-literal patterns; not a guarantee that every possible secret format was detected |
| Sandbox readiness | Not ready: private process configuration and an actual project Git repository are still absent; the root ignore file is now supplied |
| Git history scan | Not possible here: this folder has no `.git` history |

Coverage includes valid/invalid requests, money/currency boundaries, auth failure,
timeouts/rate limits/provider errors, idempotency, concurrent duplicate writes,
approval enforcement, pending/partial/paid/cancelled/failed/offline outcomes,
amount/currency/recipient mismatch, signature failures, duplicate/out-of-order
webhooks, illegal transitions, tampering and no false completed-payment paths.

All provider responses used in those tests were synthetic/scripted. No real
PayPal transaction, genuine webhook delivery, Postman service run or deployment
has been completed. A fresh-copy test is not a clean clone of the future shared
repository. The current validation environment was Python 3.14.4, Node 25.9.0,
Git 2.55.0 on Windows. No new packages were installed. The Python code requires
Python 3.11+ features and SQLite STRICT-table support; validate the chosen hosted
runtime before deployment. Git is optional for core runtime, but needed for the
three ignore tests; Node is only needed for the Postman guard tests.

## 6. Reviews requested from teammates

| Owner | Review requested | Files / acceptance decision |
|---|---|---|
| Member 4 — integration lead | Approve proposed field names, request inputs, nullable fields, errors, currency and recovered-cash semantics before API/UI adoption | [`payment-ledger.example.json`](../../../contracts/payment-ledger.example.json), [`contracts.py`](contracts.py) |
| Member 4 / backend integrator | Review service calls, authentication boundary, authorized payer lookup and database startup behavior | [`runtime.py`](runtime.py), [`INTEGRATION_HANDOFF.md`](INTEGRATION_HANDOFF.md), [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| Member 1 — forecast owner | Agree how verified outcomes feed financial inputs without double-counting invoice receipts; preserve currency and projection distinctions | Contract proposal and recovered-cash semantics in this report |
| Member 2 — AI owner | Confirm that recommendations remain proposals, use approved server-side inputs, and cannot call a paid-state setter or treat estimates as receipts | Contract proposal and approval/verification boundary |
| Repository/deployment owner | Review ignore rules, destination Git index/history, persistent storage, backup/restore and hosted process settings | Root [`.gitignore`](../../../.gitignore), runbook and integration handoff |

Member 4 review was intentionally deferred during isolated module development.
It is now needed before shared contracts/routes/UI are treated as agreed. Review
approval does not authenticate payments or replace actual Sandbox acceptance.

## 7. What other members still need to add

| Owner | Work to add outside Member 3's module |
|---|---|
| Member 4 / shared backend | HTTP routes/adapters; agree the human-approval route; call `PaymentRuntime.from_env` at startup after loading private configuration |
| Member 4 / shared backend | Human authentication, entry/tenant authorization on every read/write/total, CSRF protection where needed, request/body limits and rate limits |
| Member 4 / shared backend | Immutable authorized payer-reference lookup; never trust payer replacement, actor labels, statuses or amounts from the browser/AI |
| Member 4 / frontend | Invoice/ledger UI, explicit approval action, pending/error/retry handling, verified-only cash display and honest stale-data messaging |
| Member 4 / integration | Error-to-HTTP mapping, contract tests and shared API/UI end-to-end tests; review shared access/error logging for sensitive data |
| Shared backend owner | Bounded, non-overlapping reconciliation scheduling against the same persistent ledger |
| Deployment owner | Actual backend entrypoint, private Sandbox environment variables, public HTTPS webhook endpoint/registration, one persistent SQLite instance, restricted access |
| Deployment owner | Database-consistent backups, restore/restart-survival test, independently retained integrity checkpoints and supervised worker time limits |
| Repository owner | Import into the team feature branch, review staged files and history, configure GitHub remote/permissions, use a PR into `integration` |
| Member 1 | Connect the forecast/scenario module through reviewed contracts; Member 3 does not implement forecasting |
| Member 2 | Connect evidence-based AI recommendations through reviewed contracts; Member 3 does not implement the AI provider/model |

The internal ledger has no tenant filtering. Do not expose its full list or
totals to multiple tenants without a reviewed isolation design. For a
single-tenant demo, enforce that boundary in the shared application.

## 8. Remaining Member 3 acceptance work and limitations

1. Privately configure a Sandbox business app and separate personal payer.
2. Run actual invoice GET/create/send tests using the runbook's explicit opt-in.
3. Manually pay the approved Sandbox invoice; fresh-fetch verification must
   match approved terms and count the cents exactly once. Repeat verification.
4. Validate actual response schemas; preserve fail-closed behavior and add
   sanitized regressions for any compatibility issue.
5. After the HTTPS adapter exists, test genuine signed webhooks, duplicates,
   out-of-order delivery and recovery after an outage.
6. Confirm the scheduled sweep, hosted restart survival and backup restoration.
7. Complete destination repository/history checks and shared integration tests.

Additional limits to retain in the release decision:

- Hash chains are not protection against a database administrator consistently
  rewriting all history. External financial checkpoints/backups are required;
  the provided checkpoint does not anchor the webhook receipt-chain tail.
- Socket timeouts and bounded retries do not guarantee an absolute wall-clock
  deadline for DNS or slowly delivered headers. Use supervised worker limits.
- Old/crash-window uncertain claims are never reset or deleted automatically.
  There is no automatic database migration or terminal-state reopening.
- Approval depends on the shared server's authenticated human identity and
  stable payer lookup. Python backend code and database administration are
  trusted boundaries.
- Full-ledger integrity scans suit a small hackathon dataset; production-scale
  throughput and multi-instance operation have not been validated.

**Progress estimate:** approximately 85% of the complete Member 3 acceptance
scope. This is a planning estimate, not a test coverage or security score.
The isolated implementation and offline review are ready for handoff. Budget
roughly 4–8 additional working hours for the remaining live/integration work
once private credentials and the shared hosting/API prerequisites are available;
teammate waiting time and unexpected compatibility defects are additional.

## 9. How to share and prepare for GitHub

Share this report with these folders/files, preserving their paths:

```text
.gitignore
backend/app/payments/
backend/app/ledger/
backend/tests/payments/
backend/tests/ledger/
contracts/payment-ledger.example.json
```

Start reviewers with this report, then the contract proposal, architecture,
integration handoff and security register. The original root planning documents
remain unchanged and explain the team's ownership. This workspace contains the
Member 3 delivery and planning documents, not the other members' implementation.

For the shared repository, use the team's `feat/paypal-ledger` branch and PR
workflow into `integration`. Merge the supplied `.gitignore` with existing rules;
do not replace other members' files. Before committing, inspect staged paths,
verify `.env`, `data/` and database sidecars are ignored, and check for already
tracked secrets. Ignore rules do not remove files from past commits or make
forced additions safe. Run the offline commands above from the actual clone and
scan its full history with the team's agreed secret-scanning process.

Do not share `.env`, private Postman exports, ledger databases, logs, keys or real
customer/provider response data. The supplied `.env.example` and Postman
environment are blank templates. Module code reads process environment variables
and does not itself parse `.env` files. The runbook documents private setup.

No Git repository has been initialized here; no commit, remote, PR, push or
deployment has been made. This report is ready to send; external team messaging
has not been performed.

## 10. Sponsor/tool usage for the submission

| Tool | Actual use / current status |
|---|---|
| PayPal | Central Sandbox API integration implemented; public documentation consulted; real credentialed calls still pending |
| Postman | Five diagnostic request templates and an empty environment prepared; scripts tested offline with Node, no actual Postman service run |
| Render | Deployment/persistent-disk settings documented; no deployment made |
| APIMatic | Evaluated and not adopted; the small handwritten wrapper is already implemented |
| Python stdlib / SQLite / unittest | Runtime, append-only ledger, hashes and offline tests |
| Existing Node / Git | Local Postman script checks and isolated ignore-rule tests |

No Zapier, AG Grid, Bryntum, Elastic, Channel3, KERNEL or Astropods integration was
used for Member 3. AG Grid may be considered by Member 4 for the frontend table.
Before adopting any sponsor service, check its Devpost page for the hackathon's
actual offer. Update the submission tool list only with what was actually used.

## 11. Files changed in the final review/handoff slice

- Added root `.gitignore` with explicit user authorization.
- Fixed HTTP outcome classification in `backend/app/payments/paypal_client.py`.
- Updated `backend/tests/payments/test_client.py` for conservative redirect handling.
- Added `backend/tests/payments/test_http_outcomes.py` and
  `backend/tests/payments/test_gitignore.py`.
- Updated `backend/app/payments/README.md`, `ARCHITECTURE.md`,
  `SANDBOX_RUNBOOK.md`, `INTEGRATION_HANDOFF.md` and `SECURITY_REVIEW.md`.
- Added this `backend/app/payments/MEMBER3_TEAM_REPORT.md`.

Earlier slices delivered the remaining components listed above. Root planning
documents, the contract proposal shape, ledger schema, state policy and shared
application areas were not changed by this final slice. No dependency was added.
