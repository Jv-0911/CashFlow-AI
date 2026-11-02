# Member 3 final review package — 2 November 2026

**Follow-up:** The user subsequently authorized resolving the two shared-file
issues. All four failures now pass locally: **190 standalone passes / 3 skips;
448 affected integrated passes / 3 skips**. See
[CONTRACT_HANDOFF.md](../CONTRACT_HANDOFF.md) for replacements and field mapping.
No remote push occurred. The original review below records the pre-fix revisions.

## Outcome

Member 3 now exports read-only evidence to the supplied forecast and rescue
schemas. Our standalone tests pass. The assembled repository still fails four
checks against its unchanged shared payment example and ignore rules. It is
not yet a fully passing integrated application. No commit, push, pull request,
shared API change, payment-state change, schema migration or PayPal request was made.

## Exact inputs reviewed

| Input | Revision / identity |
|---|---|
| `feat/forecast-engine` | `b52de7c38e8d575d6aa4c68320468f17d60b09ee` |
| `integration` | `f22a3f8388ceb877d9d6f9d56a2621ff4b050f8c` |
| `Payment-ledger` and `main` | `1f29afc225797058484e7d77c0f7429685756856` |
| Member 2 ZIP, explicitly selected by the user | `Member2-Rescue-AI-2026-10-27.zip` |
| ZIP SHA-256 | `1ece562baf6ffb22020484c46e35dc225256e40b048b97ed44e03d62c7edf077` |

Repository: [Jv-0911/CashFlow-AI](https://github.com/Jv-0911/CashFlow-AI).
The supplied workplan matches the local plan. At these revisions, integration
contains API fixtures and placeholder domain modules; Payment-ledger/main contain
only `.gitignore`, `LICENSE` and `README.md`. Rescue implementation is absent
from the supplied branches. The ZIP is the tested Member 2 source, not a claim
that it has been merged. Later branch changes require a fresh comparison.

## What changed and why

- Added `forecast_event` and `rescue_invoice` in `evidence_exports.py`, producing
  the peers' existing input fields without importing their dependencies into
  the payment runtime. See [TEAM_COMPATIBILITY.md](../TEAM_COMPATIBILITY.md).
- Unpaid/pending exports require a recorded provider observation showing the
  full amount outstanding. A send acknowledgement alone is insufficient.
- Unsupported partial/offline/refunded/unresolved/proposal states raise a fixed
  error rather than becoming paid or silently disappearing from a complete
  analysis. Missing due dates are not invented. Projected collection dates and
  assumptions remain separate from payment evidence.
- Added eleven standalone regressions and five separately invoked tests using
  the real forecast engine and deterministic rescue service with synthetic data.
- Replaced our nested `pytest.ini` with marker registration in our `conftest.py`.
  The old configuration made pytest miss the parent API fixtures in combined
  collection. Renamed a helper that pytest mistakenly counted as a test.
- Our fixture checks now accept the repository example's UTF-8 BOM and report
  the actual contract mismatch. Provider-response parsing is unchanged.

## Tests actually executed

| Check | Result |
|---|---|
| Final standalone Member 3 unittest suite | **189 passed, 3 live Sandbox tests skipped**; 192 discovered |
| Postman script guards | **7 passed**, fake Postman runtime |
| Member 1 forecast suite in the initial complete assembled run | **498 passed**; no forecast failures in that run |
| Unchanged Member 2 tests in the corrected focused run | **252 passed** |
| Shared API fixture tests after our pytest fix | **6 passed** |
| Separate cross-module command | **5 passed**, actual forecast/rescue functions, fake PayPal transport |
| Corrected focused assembled run | **443 passed, 4 failed, 3 skipped**, plus 432 reported subtests |
| Final contract diagnostic rerun against unchanged shared example | **4 passed, 2 failed**, both intentional detection of the existing mismatch |

Do not sum these rows: several suites overlap. The focused run covered payments,
ledger, rescue and API tests. The five compatibility tests were run separately
with `python -B -m backend.tests.payments.team_compatibility`; explicitly adding
that filename to pytest did not include them in the reported pytest count.

The initial complete assembled run reported 935 passes, four shared-file failures,
three skips, six API fixture errors and one helper warning. The API errors and
warning were fixed in our tests and retested. A redundant second numerical run
was interrupted after 176 passes; it is not counted as a completed run. Unchanged
forecast calculations were not rerun after the test-discovery fix.

Standalone command: `python -B -m backend.tests.payments.run_tests`.
Combined pytest collection needs `--import-mode=importlib` because forecast and
payments both contain `test_reconciliation.py`. Shared HTTP tests currently
exercise fixture endpoints; they do not prove authenticated payment integration.

Linux tests used Python 3.14.4 with isolated dependencies selected from Member 1's
declared ranges: Pydantic 2.14.2, pytest 9.2.0, HTTPX 0.28.1, FastAPI 0.162.0,
NumPy 2.5.4, scikit-learn 1.9.1, SciPy 1.18.1 and joblib 1.6.0. No project/global
dependencies were changed. Linux is needed for Member 1's POSIX filesystem locks.
External sockets and real HTTPX transports were blocked; in-process ASGI and
scripted transports remained available. Live PayPal opt-in was disabled.

## Four remaining failures: two shared-file decisions

1. **Payment contract, two failures.** The repository example is a single small
   object with `ledger_entry_id`, `invoice_id` and lowercase application status.
   The existing local proposal has explicit demo metadata, `ledger_response`,
   state/provider evidence, timestamps and verified-only totals. The shared file
   lacks `is_demo_data` and `ledger_response`. Choose the shared representation
   before replacing that file or wiring the API. No new contract was silently adopted.
2. **Ignore rules, two failures.** The repository ignores ordinary databases but
   misses journal/backup variants, `data/`, private key files and credentialed
   Postman environment exports. The existing local root `.gitignore` already
   passes our checks. Merge its payment-specific protection rules into the
   destination rules, preserving teammates' existing exclusions and blank-template
   exceptions; do not blindly replace their entire file. Then rerun ignore checks.

Both failures are visible and retained. Tests were not weakened to make the
repository appear ready. Shared files and teammate implementations were untouched.

## Other work still needed

- Bring the complete Member 3 delivery into the intended branch: that branch has
  no payment implementation yet. Coordinate integration of the forecast branch
  and Member 2 ZIP; this review did not merge any branch.
- Wire authenticated, authorized payment/approval routes and the UI to the
  services. The current API returns labelled forecast fixtures, not the full
  forecast/rescue/payment workflow. Preserve tenant isolation and server-owned
  recipient/reference lookups.
- Supply trusted invoice due dates and explicit collection assumptions to the
  exports. Surface unavailable/stale evidence. Do not use recovered totals as a
  bank opening balance or complete daily actuals: settlement dates, fees, other
  business movements and full coverage are not established by this ledger.
- Keep Member 2's recommendations as proposals. Following up an existing invoice
  must not automatically create another invoice for the same receivable. The
  earlier [Member 2 review](MEMBER2_REVIEW_2026-10-27.md) still applies to this ZIP.
- Configure persistent hosting, periodic reconciliation, protected backups,
  independent checkpoints and actual hosted restore testing.
- Keep live PayPal create/send/read/manual-pay/verify and genuine webhook tests
  deferred until access is available. Three skipped tests remain unverified.
- Recheck the final destination index and all reachable history before committing.
  A limited scan of four fetched commits / 67 unique blobs found no matches for
  the tested private-key/token patterns or sensitive filenames. This is not a
  guarantee that every possible secret is absent, and excludes unknown refs or
  later commits.

## Files changed in this slice

All paths below are within Member 3 ownership. The root contract, root ignore
file, workplan, API, forecast and rescue source were not edited.

- Added `backend/app/payments/evidence_exports.py`
- Added `backend/app/payments/TEAM_COMPATIBILITY.md`
- Added `backend/tests/payments/test_evidence_exports.py`
- Added `backend/tests/payments/team_compatibility.py`
- Added `backend/tests/payments/conftest.py`
- Removed `backend/tests/payments/pytest.ini`
- Updated `backend/tests/payments/test_config_money.py`
- Updated `backend/tests/payments/test_adapters.py`
- Updated `backend/tests/payments/test_contract.py`
- Updated `backend/app/payments/README.md`
- Updated `backend/app/payments/INTEGRATION_HANDOFF.md`
- Updated `backend/app/payments/SECURITY_REVIEW.md`
- Updated `backend/app/payments/MEMBER3_TEAM_REPORT.md`
- Updated `backend/app/payments/LIVE_ACCEPTANCE.md`
- Added this report: `backend/app/payments/reviews/GITHUB_COMPATIBILITY_2026-11-02.md`

The isolated test copy's 81 non-Member-3 files were hash-checked after execution:
zero changes. No teammate tests or implementation were patched to make them pass.

## User's final review before pushing

Review the adapter/state table, unavailable-evidence behavior and the two
shared-file decisions above. After those decisions and destination checks, push
the complete intended Member 3 files, not just this slice; omit private data,
test environments, temporary review checkouts and archives. Rerun the supplied
commands in that checkout. No credentials are needed for these offline checks.

Tools used: GitHub connector for branch/source inspection; Git for the isolated
checkout and history/ignore checks; Python/unittest/SQLite for Member 3; Ubuntu
WSL and isolated pip/pytest/scientific libraries for unchanged teammate tests;
Node's built-in test runner for Postman guards. No sponsor service was newly
adopted, no AI-provider request was sent, and no remote write occurred.
