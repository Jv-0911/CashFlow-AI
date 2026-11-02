# Contract and ignore-rule resolution — 2 November 2026

The user authorized resolving both shared-file mismatches. The local replacement
`contracts/payment-ledger.example.json` now identifies the existing tested
serializer format as `MEMBER_3_IMPLEMENTATION_CONTRACT`, version `1.0`.
This records Member 3's implementation choice; it does not claim an external
review, deployment, or live payment test. All records remain labelled demo data.

## Consumer mapping

The JSON file is a documentation/fixture envelope, not one HTTP response.
`ledger_response` is the list response produced by `ledger_view(ledger)`;
`error_response` illustrates `error_view`. `requests` contains service-input
examples. It does not define new routes or permit client-supplied human identity.

| Old single-entry example | Selected implementation |
|---|---|
| `ledger_entry_id` | `ledger_response.entries[].entry_id`, the local ledger identity |
| `invoice_id` | `provider_invoice_id` only for a genuine stored PayPal invoice ID; never reinterpret the old placeholder as a real provider ID |
| `amount_cents`, `currency`, `provider` | Same meanings on each entry; integer cents, USD, `paypal_sandbox` |
| Lowercase `pending_verification` | Read the actual uppercase ledger `status`; no blanket text conversion or client status setter |
| `verified_at` | Non-null only while the current state is `VERIFIED_PAID` |
| No provider status/evidence | Separate `provider_status`, `provider_invoice_id`, `paid_amount_cents`, timestamps and sequence |
| No total | `recovered_cash`: currency-labelled totals from current `VERIFIED_PAID` entries only |

The list response includes `is_demo_data`; it must reflect the source of the
data. A non-demo label never turns a forecast into verified cash. A pending old
fixture is not enough evidence to manufacture an `AWAITING_VERIFICATION` event
or any other state. Load real snapshots through the ledger service. No existing
database migration is needed: models, transitions, hashes and runtime response
fields are unchanged. Shared HTTP/UI consumers still need wiring to this format.

## Ignore rules

The local root `.gitignore` now retains all rules from the supplied integration
revision `f22a3f8388ceb877d9d6f9d56a2621ff4b050f8c` and appends the Member 3
protections. Existing Python/frontend/build/IDE exclusions are preserved.
Added protections cover data directories, SQLite databases/journals/backups,
private key material, private environment files and credentialed Postman exports.
Blank `.env.example` and the blank Postman template remain visible.

Ignore rules do not remove already tracked files or erase Git history. Inspect
the final index before committing and repeat the history checks after merging.
Both integration and Payment-ledger branch heads were rechecked before this work;
they matched the earlier review. A new rescue branch was visible but was not
substituted for the user-selected ZIP in this focused task.

## Executed validation

- Final standalone suite: **190 passed, 3 live tests skipped** (193 discovered).
- Affected integrated suites (payments, ledger, unchanged rescue ZIP and shared
  API fixtures): **448 passed, 3 skipped**, plus 432 reported subtests; no failures.
- All four previous contract/ignore failures now pass using the replacement files.
- New regression confirms the team's existing build/environment ignores survive.
  Its first version incorrectly expected a root-relative Streamlit rule to apply
  under frontend too; the test expectation was corrected, preserving the original
  rule, and both suites were rerun successfully.
- No live PayPal calls. Unchanged numerical forecast/Node suites were not rerun
  for this metadata/ignore change; earlier results remain in the branch report.

The Linux test copy used the exact replacement root files and updated tests.
This is a passing local integration candidate, not a claim that GitHub has been
updated. The remote repository still has the old files until the user pushes.

## Files changed in this slice

- `.gitignore`
- `contracts/payment-ledger.example.json`
- `backend/app/payments/contracts.py` (module description only)
- `backend/tests/payments/test_contract.py`
- `backend/tests/payments/test_adapters.py`
- `backend/tests/payments/test_gitignore.py`
- `backend/app/payments/CONTRACT_HANDOFF.md` (this document)
- Payment documentation: `README.md`, `INTEGRATION_HANDOFF.md`, `ARCHITECTURE.md`,
  `SECURITY_REVIEW.md`, `MEMBER3_TEAM_REPORT.md`, `LIVE_ACCEPTANCE.md`, and
  `reviews/GITHUB_COMPATIBILITY_2026-11-02.md`.

## User handoff

Review the two root replacement files and this mapping before pushing the full
Member 3 package. No commit or remote write was performed. Preserve any newer
team rules if the destination `.gitignore` changes meanwhile. After applying
these files to the intended checkout, rerun Member 3 tests and the affected
integrated tests. Application wiring is still separate; hosting/workflow/recovery
are user-managed, and live Sandbox tests remain deferred as requested.
