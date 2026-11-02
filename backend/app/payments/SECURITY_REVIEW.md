# Member 3 security review and follow-up register

Updated 2026-10-14. Reviewed configuration, money, schemas, HTTP/OAuth, invoice
operations, verification, reconciliation, webhooks, runtime/serializers, ledger
models/state machine/storage, Member 3 tests, Postman assets and module docs.
No shared routes or frontend files were changed. This code review and its offline
regressions are not production certification or proof against every attack.

## Findings addressed

| Priority | Finding | Resolution / regression evidence |
|---|---|---|
| High | Malformed OAuth could be mistaken for malformed invoice evidence, changing a verified entry without fetching the invoice. | OAuth parsing/response-limit failures become AuthError; regression proves no invoice GET or ledger write. |
| High | Evidence age was checked before waiting for the write transaction and integrity scan. | Consume/check the one-use observation inside the transaction after the wait; expiry regression simulates delay. |
| High | HTTPResponse.read1 can silently return a truncated Content-Length body, even a valid JSON prefix. | Remaining length at EOF produces ProviderUnavailable, preserving state; tests use real HTTP parsing with in-memory sockets. |
| High | Ambiguous HTTP results were treated as definite rejections, allowing a timeout/redirect/conflict to cause terminal FAILED after an invoice write. | HTTP 408 becomes ProviderTimeout; redirects/conflicts/unexpected HTTP outcomes stay unavailable. Definite rejection is explicitly restricted. Create/send retain their claim and prior state; verification writes nothing. Three regression methods cover 31 cases; the old code failed 27 cases before the fix. |
| Medium | Default test runs could inherit RUN_PAYPAL_SANDBOX_TESTS=1. | Combined runner now requires --sandbox; default discovery/execution clears inherited opt-in and blocks DNS/TCP APIs. |
| Medium | Terminal contradictions attempted a disallowed transition. | Return RecoveryRequired and write nothing. Unknown statuses still map to UNRESOLVED, but terminal reopening remains forbidden. No new transition. |
| Medium | Decimal inherited exponent limits/traps from other application code. | Dedicated Decimal Context; strict integer maximum and boolean allow_zero validation. |
| Medium | Deeply nested corrupted ledger metadata leaked RecursionError. | Translate to IntegrityViolation; regression confirms cash reporting also fails closed. |
| Medium | Reusable logging redaction boundary was missing. | New audit.py handler filter discards free text, arguments, exceptions, stacks and extras; only enum event/state labels survive. |
| Medium | Postman guards relied on throwing errors, with TLS/redirect settings left to the operator. | Explicit skipRequest, exact effective destination checks, both write approval attestations, valid request UUIDs, TLS on, redirects/cookies off. |
| Medium | A failed Postman OAuth attempt could leave a previous local token. | Clear before acquisition/response processing; validate successful token shape/expiry before local storage. |
| Medium | OAuth and send-preflight failures consumed claims despite no invoice-changing dispatch. | Claim after successful OAuth/preflight, immediately before POST, with atomic eligibility checks. Eleven new regressions cover retries, races, commit-before-dispatch, crash uncertainty and stable IDs through 401 refresh. |
| Low | Direct transport and several concurrency/boundary cases lacked tests. | Added complete/truncated/chunked/oversize reads, TLS/connect failure, timeouts, cleanup, concurrent sends, malformed nested schemas and webhook limits/outages. |
| Low | Some comments still described the foundation slice. | Updated comments and documentation. |

Clarification: malformed nested provider fields were already rejected safely.
The missing recursion-error translation was in stored ledger metadata. The new
parser matrix strengthens coverage without relaxing or rewriting that parser.

## Validation actually executed

Latest authorized shared-file resolution: **190 standalone passes / 3 live
skips; 448 affected integrated passes / 3 skips**, no failures. All four earlier
contract/ignore failures are resolved in the local candidate. The team ignore
rules were retained, the tested implementation example was selected, and no
payment state/security behavior changed. See [CONTRACT_HANDOFF.md](CONTRACT_HANDOFF.md).
Counts and unresolved-file statements below describe earlier review stages.

2026-11-02 follow-up: final standalone run **189 passed / 3 live skipped**;
Postman guards **7 passed**; separate cross-module checks **5 passed**. Added
read-only peer evidence exports and fixed Member 3 pytest discovery. The assembled
repository retains four failing checks for its old shared payment example and
incomplete ignore rules. See [the branch review](reviews/GITHUB_COMPATIBILITY_2026-11-02.md)
for exact revisions, all executed results, unchanged teammate-file hashes and
remaining boundaries. Earlier counts below are historical.

Latest offline follow-up, 2026-10-31: **181 Python tests discovered, 178 passed,
3 Sandbox tests skipped**; **7 JavaScript guards passed**. Seven new recovery
drills cover SQLite backup, a separate process restart, retained verified cash,
bindings/operation identities, webhook duplicate protection, uncertain dispatch
claims, committed WAL records, and stale/corrupt/empty recovery candidates.
The WAL test initially failed because its fixture did not retain an active read
snapshot; that test setup was corrected and the complete Python suite rerun
successfully. No runtime, schema, transition or contract changes were necessary.
See [the recovery runbook](../ledger/RECOVERY_RUNBOOK.md) for operator steps and
the limit of a financial checkpoint versus a whole-backup digest. Account work
is deferred at the user's request. The earlier baseline below is historical.

```powershell
python -B -m backend.tests.payments.run_tests
node --test backend/tests/payments/postman_guards.test.cjs
```

- Python: 174 discovered; **171 passed**, **3 Sandbox tests skipped**.
- JavaScript: **7 passed**, using existing Node built-in test/vm/assert libraries.
- Fresh source copy: 59 source/template/document files copied to a temporary
  directory; Python again reported 171 passed / 3 Sandbox skipped, and all 7
  JavaScript tests passed. The final validation wrapper exited 0.
- Synthetic/generated data only. No PayPal requests, TLS bypass, new packages,
  schema migration, deployment, or Git commit.
- Postman scripts ran against a fake pm object. Actual Postman import/runtime
  behavior and real PayPal response compatibility remain unverified.
- Local Sandbox readiness helper: ten new regressions passed for missing/invalid
  configuration, unsafe hosts, absent directories/repository/ignore rules,
  incomplete ignore coverage, tracked ignored files, Git errors/timeouts,
  explicit send selection, read-only behavior and private-value suppression.
  Running the helper before the current handoff returned exit 1 as expected:
  repository protections and private environment configuration were absent. The
  root ignore file is now supplied/tested, but Git/private configuration remain
  absent. No live test
  is selected. This helper is preparation, not a history scan or payment proof.
- Root `.gitignore`: three real Git tests passed in isolated temporary
  repositories, covering nested sensitive files, visible templates/source, and
  already tracked ignored files. No repository was initialized in this workspace.
- Working files: Python syntax, JSON and local documentation links checked;
  no matches for the tested private-key, common-token and long credential-literal
  patterns. This heuristic scan cannot prove absence of all secrets. No Git
  history exists here; the destination repository still needs a history scan.

## Outstanding work and decisions

2026-10-31 update: the user supplied Member 4's standalone code-review approval.
Member 4 independently confirmed 171 Python passes / 3 Sandbox skips and 7
Postman guard passes. The agent reran both suites with those same results.
Private Sandbox configuration and an integrated team checkout are not available;
no credentialed calls have run. See [LIVE_ACCEPTANCE.md](LIVE_ACCEPTANCE.md).
The acceptance message does not explicitly approve shared contract/API shapes.

| Item | Owner / dependency | Required next step |
|---|---|---|
| Sandbox create/send/manual-pay/verify and real response schemas | Member 3 + private test credentials | Follow SANDBOX_RUNBOOK; preserve strict validation and add sanitized fixtures for actual incompatibilities. |
| Genuine webhook delivery | Member 3 + shared HTTPS endpoint | Register same Sandbox app; test signature, duplicate delivery and outage followed by reconciliation. |
| Contract review/shared routes/UI | Member 4 | Review example JSON and serializers before integration. No contract shape was changed in this review. |
| Authorization, tenant isolation, CSRF/rate limits | Member 4 | Server-derived human identity and entry ownership on every operation; internal ledger has no tenant filtering. |
| Approved payer reference lifetime | Member 4 + Member 3 | Do not reassign an approved reference to another payer. Initial approval depends on an immutable authorized server lookup. |
| Shared logging | Member 4 | Use isolated payment logger or filter every payment handler; inspect unfiltered HTTP access/error and third-party logs separately. |
| Reconciliation scheduler | Shared backend owner | Run bounded, non-overlapping sweeps using the same persistent ledger. A receipt followed by failed fetch relies on this sweep. |
| Older or crash-window ambiguous claims | Member 3/operator | New OAuth/preflight failures no longer consume claims. Existing claims stay blocked if dispatch cannot be excluded; preserve history, reconcile and never invent another key to bypass them. |
| Render/persistence/backups | Deployment owner | Local backup/restart drills now pass; actual entrypoint, private env, one disk-backed instance, external retention and hosted restore remain pending. Follow the ledger recovery runbook. |
| Independent integrity anchors | Deployment owner | Financial checkpoint must live outside DB. It does not anchor receipt-chain tail; consistent administrator rewrites remain outside the guarantee. |
| Absolute transport deadline | Shared backend owner / future hardening | Socket timeouts and between-operation deadlines exist; OS DNS and slowly delivered headers are not guaranteed to obey a total wall-clock limit. Use supervised worker limits; do not promise a strict request SLA. |
| Git and credential history | Repository owner | Root ignore rules are now supplied/tested. Import into the team repository and verify its effective ignores, index and entire history before merge. No .git exists here. |
| Actual Postman execution | Member 3/operator | Use skipRequest-capable Postman, verify private import/settings. Attestations cannot independently prove ledger approval. |
| Shared end-to-end suite and hosted demo | Whole team / Member 4 | Test the authenticated API/UI flow after integration and then run the hosted Sandbox demonstration. |

## Files changed in this review

- Payments: `paypal_client.py`, `invoice_service.py`, `verification.py`, `money.py`, new `audit.py`.
- Ledger: `payment_events.py`, `store.py`, `models.py`, `state_machine.py`.
- Postman: `postman/paypal-sandbox.collection.json`.
- Payment tests: `run_tests.py`, `test_verification.py`, `test_config_money.py`,
  `test_payment_integrity.py`, `test_client.py`, `test_invoice_service.py`,
  `test_webhooks.py`; new `test_transport.py`, `test_offline_runner.py`,
  `test_audit.py`, `test_safe_dispatch.py`, `postman_guards.test.cjs`.
- Sandbox preparation: new `sandbox_readiness.py` and
  `test_sandbox_readiness.py` under `backend/tests/payments/`.
- Handoff review: root `.gitignore` (explicitly authorized), new
  `test_gitignore.py`, `test_http_outcomes.py`, and `MEMBER3_TEAM_REPORT.md`;
  HTTP classification fix in `paypal_client.py` and adjusted `test_client.py`.
- Payment docs: README, ARCHITECTURE, SANDBOX_RUNBOOK, INTEGRATION_HANDOFF,
  postman/README, and this register.

USD-only policy, terminal transitions, contract proposal, and DB schema remain
unchanged. Implementation changes are confined to Member 3 paths; the explicitly
authorized root `.gitignore` is the sole ownership exception.
