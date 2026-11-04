# Member 2 Rescue AI — independent handoff review

**Reviewed:** 27 October 2026  
**Reference:** [TEAM_WORKPLAN.md](../../../../TEAM_WORKPLAN.md), especially sections 5 and 8  
**Archive:** `Member2-Rescue-AI-2026-10-27.zip`  
**SHA-256:** `1ece562baf6ffb22020484c46e35dc225256e40b048b97ed44e03d62c7edf077`

## Verdict

The package substantially meets Member 2's isolated module responsibilities and
is suitable for joint integration review. All **252 supplied tests passed**, and
all **8 demonstration scenarios** ran successfully. Its constrained AI design
keeps financial calculations, evidence and approval flags under application-code
control. No payment-execution or ledger-status-writing path was found.

Final team acceptance should remain pending: tighten or explicitly resolve the
response contract, agree input limits/currency/date policy, and complete the
forecast/payment/API mappings. Passing these local tests does not prove a live
AI connection, shared API behavior, frontend integration or the complete demo.

No teammate source was edited. All 14 extracted files remained byte-for-byte
identical to the ZIP after testing. Member 3 runtime and tests were not changed.

## What was inspected and run

The archive contains six Python module files (including an empty `__init__.py`),
five Python test files, two Markdown guides, and one JSON example fixture.

| Component | Assessment |
|---|---|
| `schemas.py` | Strict integer money, duplicate-ID rejection, currency consistency, forecast arithmetic/carry-forward and a 30-day limit are implemented. Contract gaps appear below. |
| `fallback.py` | Deterministic risk analysis and ranking; no double-counting, payment mutation or invented expense savings. Revalidates supplied models. |
| `provider.py` | Configurable HTTPS adapter, environment credentials, restricted selection schema, no redirects/retries, timeout and size checks, minimal context. Tested with HTTPX MockTransport. |
| `service.py` | Builds trusted fallback first; gives the provider an independent copy; validates complete action permutations; preserves amounts/evidence/approval; catches failures and propagates cancellation. |
| `examples.py` | Eight reproducible fictional scenarios; simulated AI is explicitly labelled. CLI and documentation snippets are exercised by the supplied tests. |
| `example_data.json` | Parses successfully; supplied tests compare saved fixtures with actual demo output. |
| `README.md`, `INTEGRATION.md` | Detailed setup, assumptions, limitations, provider configuration and owner checklists. Shared API wiring is correctly left to its owner. |
| Five test modules | Schema, fallback, adapter, service and demonstration behavior all pass. |

Test command inside the isolated source copy:

```powershell
python -B -m pytest backend/tests/rescue_ai --noconftest -p no:cacheprovider -q --tb=short
```

Environment: Python **3.12.14**, Pydantic **2.14.1**, HTTPX **0.28.1**, pytest
**9.1.1** on Windows. Pydantic was already available in the bundled runtime;
HTTPX, pytest and their dependencies were installed only into a temporary review
folder. Project dependency files and global packages were not modified.

External DNS/TCP and real HTTPX provider transports were blocked; inherited
provider credentials were removed from the test subprocess. MockTransport was
allowed. An initial overstrict guard blocked Windows asyncio's internal socket
pair. After correcting that reviewer-side harness issue, the unchanged package
passed **252/252 tests in 3.95 seconds**, with no skips reported. The initial
harness failures are not attributed to Member 2.

Additional checks:

- All **11 Python files** parsed; the **JSON fixture** parsed.
- All eight demos returned expected risk/action counts and demo labels; every
  generated action required approval.
- Additional malformed-provider input still produced safe service fallback.
- No matches were found for the tested private-key/common-token/long credential
  literal patterns. This is a limited working-file scan, not proof of absence
  of every possible secret. No Git history was supplied for review.

## Findings to resolve before final contract approval

### R1 — Response validation permits incomplete recommendations (medium)

**Location:** `backend/app/rescue_ai/schemas.py:141–144,159`;
`backend/tests/rescue_ai/test_schemas.py`, `test_existing_rescue_example_shape`.

The response model accepts an action with an impact of 100 cents but no response
currency or action currency, and no action explanation, evidence IDs or priority.
The reproduced parsed values were:

```json
{
  "currency": null,
  "action_currency": null,
  "explanation": null,
  "evidence_ids": [],
  "priority": null
}
```

This conflicts with section 5's required recommendation information and section
8's requirement that every monetary value have a currency. It is an intentional
legacy-shape compatibility allowance, and the normal service currently fills
these fields correctly. It is therefore a contract-enforcement gap, not evidence
that the tested service fabricated a financial result.

**Owner/action:** Member 2 and Member 4 should agree a strict output contract for
the production API. Require the recommendation explanation, citations, priority
and an unambiguous currency for monetary impact. Keep legacy-input compatibility
separate if it is still needed. Add rejection tests for incomplete output.

### R2 — Date inputs silently accept numeric timestamps (low)

**Location:** `schemas.py:29,48,80,96,109`.

The documented interface expects ISO calendar dates. Supplying `due_date: 0`
was accepted and converted to `1970-01-01`. A malformed numeric integration
value can therefore become a very old overdue date instead of being rejected,
affecting eligibility and ranking.

**Owner/action:** Member 2/Member 4 should enforce the agreed date representation
at the API boundary, retaining support for legitimate internal `date` objects as
appropriate. Add numeric, numeric-string and timestamp-format rejection tests.

### R3 — Supported currencies are not enforced (medium integration issue)

**Location:** `schemas.py:16`, `fallback.py:_money`.

A fully consistent request using `ZZZ` as currency was accepted and produced a
`ZZZ` response. The schema only checks three uppercase letters; the formatter
always assumes 100 cents per unit. The documentation openly records this limit
and asks the team to keep the MVP in USD, but code does not enforce that policy.

**Owner/action:** Members 1, 2, 3 and 4 should agree and enforce the supported
currency set. For the current Member 3 implementation this is USD. Reject
unsupported currency codes at a defined boundary rather than relying only on
instructions. Broader currencies need agreed minor-unit and conversion rules.

## Hardening and integration responsibilities

These items do not demonstrate a payment-verification bypass. They should be
addressed by the module/integration owners before exposing an untrusted API.

### H1 — Bound input identifiers and collections

**Location:** `schemas.py:15,112–113`; `service.py:analyze_rescue`.

Record IDs have no maximum length; invoice and transaction lists have no maximum
count. A 100,000-character invoice ID was accepted and generated a 402,088-byte
response. A request containing 1,000 invoices produced 1,001 actions, including
its expense action. These were modest boundary probes, not a load/DoS test.

The provider's 200-candidate/64,000-byte limits are useful, but apply after the
fallback constructs its result. The service timeout also surrounds the provider,
not synchronous request validation and fallback processing.

**Action:** Agree maximum ID/text lengths, evidence counts and API body limits;
validate them before analysis. Keep legitimate business workloads in mind and
add tests at/above the chosen limits.

### H2 — Opaque IDs are a privacy requirement, not currently a validation rule

**Location:** `schemas.py:15`, `provider.py:build_provider_context`.

A synthetic invoice ID of `synthetic-payer@example.test` passed validation and
appeared inside the candidate action ID sent to the provider context builder.
No external request was made. Notes and dedicated customer fields are excluded,
but arbitrary IDs can still contain personal data. The integration guide already
warns that IDs can be business information and asks callers to use opaque IDs.

**Action:** The shared backend must supply genuinely opaque authorized IDs. If
the system accepts identifiers from outside that trusted boundary, use a strict
ID policy or temporary provider-facing aliases. Do not claim that removing email
fields alone guarantees no personal data leaves the system.

### H3 — Source-linked cause attribution remains limited

The fallback accurately summarizes forecast aggregates, reserve gap and possible
actions. It explicitly states that individual causes cannot be established
without linked source records. Transaction evidence is not linked to forecast
events, so the module cannot demonstrate that a particular invoice/expense
caused the forecast shortage or calculate an incremental scenario improvement.

**Action:** Members 1, 2 and 4 should either agree a traceable event-link contract
or accept and preserve this documented aggregate-only diagnosis for the MVP.
Do not add more confident causal claims without evidence.

## Comparison with the team workplan

| Requirement | Result | Remaining condition |
|---|---|---|
| 5A: structured forecast/invoice/transaction input, evidence IDs, external provider config | Implemented and tested | Real Member 1/3 mappings and input policies must be agreed |
| 5B: explain shortages, cite evidence, show uncertainty/insufficient evidence | Implemented at aggregate level | Individual causal attribution needs source links; limitation is disclosed |
| 5C: ranked actions with stable IDs, impact, assumptions and approval | Generated service outputs satisfy these requirements | Tighten response schema under R1 |
| 5D: configurable provider, schema checks, timeout/errors/rate limits, fallback, key handling | Implemented and mock-tested | Real endpoint/model protocol compatibility unverified; ID privacy remains caller-dependent |
| 5E: no invented money/payment status or unapproved financial action | No violating path found; adversarial supplied tests pass | API must preserve the approval boundary and never treat recommendations as receipts |
| 5F: required automated failure/safety tests | 252 supplied tests pass | Add regressions for R1–R3/H1–H2 as policies are agreed |
| 5G: module, schemas, provider/fallback, examples, tests and docs | Present in the archive | Shared dependency/setup files must be updated by their owner |
| Section 8: money/currency, dates, IDs, nullable fields, demo labelling, contracts | Mostly implemented; demos and nullable impact documented | R1/R2/R3 and shared contract approval remain |
| Member 2 Definition of Done: Member 4 can integrate through agreed API | Callable interface and handoff provided | Actual shared contract approval and API integration are not demonstrated |

## Specific Member 3 integration review

The ZIP expects simplified invoice states `unpaid`, `pending`, `paid`, `cancelled`
and a supplied outstanding amount and due date. This cannot be wired by simply
renaming every Member 3 state:

- Only authoritative VERIFIED_PAID evidence may support a paid representation.
- OFFLINE_MARKED_PAID must never be presented as PayPal-verified payment.
- PARTIALLY_PAID requires an authoritative remaining balance, not the original
  invoice total and not Member 3's verified-only recovered-cash total.
- UNRESOLVED, FAILED, REFUNDED and other states need an explicit joint policy;
  do not guess that they are unpaid and automatically suggest collection.
- The current Member 3 public serializer does not provide a due date or an
  authoritative outstanding-balance field. Agree the source/mapping before
  creating the rescue request; do not invent a date or silently alter a contract.
- Suggestions must remain proposals. Payment verification and approval stay in
  Member 3; updating a forecast after verified cash is joint Member 1/4 work.

These are integration dependencies, not changes made by this review.

## Recommended next actions

1. Send R1–R3 to Member 2 and Member 4 for contract decisions and regression tests.
2. Agree input bounds and opaque-ID handling at the shared API boundary.
3. Members 1/3/4 provide explicit mappings for forecast snapshots, invoice states,
   outstanding amounts, due dates and verified receipts.
4. Member 4 records the agreed runtime dependencies and portable setup commands.
   The archive's documented `.venv-win` executable is not included in the ZIP.
5. Run joint API/UI tests, including provider failure and the complete
   forecast → recommendation → approval → Sandbox invoice → verified payment →
   refreshed forecast workflow. Run any live AI compatibility check separately
   using privately configured credentials and an approved provider.

**Acceptance recommendation:** accept the package for integration review;
withhold final contract/product sign-off until the listed decisions and joint
tests are complete. No critical payment mutation or fabricated-cash defect was
identified in the reviewed paths. This review is not a security certification.
