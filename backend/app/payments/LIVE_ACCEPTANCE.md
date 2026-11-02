# Member 3 — final acceptance tracking

Updated 2026-10-31.

Latest local acceptance, 2026-11-02: the user-authorized contract/ignore fixes
pass **190 standalone tests** and **448 affected integrated tests**, with three
live tests skipped in each suite. The four old shared-file failures are resolved
locally; no remote push or live acceptance is claimed. See
[CONTRACT_HANDOFF.md](CONTRACT_HANDOFF.md). Earlier results below are historical.

Offline follow-up 2026-11-02: **189 Python passes / 3 live skips**, **7 Postman
guard passes**, **5 separate cross-module passes**. Supplied teammate code was
tested without modification. Shared contract/ignore mismatches and deployment
remain open; [the branch review](reviews/GITHUB_COMPATIBILITY_2026-11-02.md)
records them. PayPal-account-dependent work remains deferred by the user.

## Review accepted; live acceptance pending

The user supplied Member 4's review on 2026-10-31. Member 4 accepted the standalone
implementation from the code-review perspective and independently confirmed
171 Python passes / 3 Sandbox skips and 7 Postman guard passes. Payment
verification, idempotency, ledger integrity and security design were reviewed.

This approval does not establish that the shared API contract, authentication,
hosting, or real Sandbox flow has been accepted. Those require separate evidence.
The agent reran the baseline on 2026-10-31: 174 Python tests discovered,
171 passed / 3 Sandbox skipped, and 7 Postman guard tests passed.

The user confirmed that private Sandbox configuration and an integrated team
checkout are not available yet. No credentialed PayPal calls were attempted.

Latest local follow-up, 2026-10-31: **178 Python passes / 3 Sandbox skips**
(181 discovered), plus **7 Postman guard passes**. Seven new backup/restart
drills passed using synthetic data. See
[RECOVERY_RUNBOOK.md](../ledger/RECOVERY_RUNBOOK.md). The user has deferred
account-dependent work; account setup below is retained for later, not an
immediate prerequisite for continuing local checks.

## Deferred account setup

Before adopting sponsor services, check the relevant Devpost offer for this
hackathon. For PayPal account setup:

1. Sign into the [PayPal Developer Dashboard](https://developer.paypal.com/dashboard/).
2. In Apps & Credentials, use the Sandbox environment and create or select the
   app associated with the Sandbox business seller. Keep its client ID and secret
   private. See [PayPal's credential setup instructions](https://developer.paypal.com/api/get-started/).
3. In Testing Tools > Sandbox Accounts, identify the separate personal buyer
   and business seller. Use existing default accounts if suitable. Keep the
   personal account login available for manual test payment. See
   [PayPal's Sandbox account instructions](https://developer.paypal.com/sandbox-testing/accounts).
4. Confirm only that the accounts/app are ready. Never send credentials, tokens,
   payer emails or account passwords through chat, screenshots or test logs.

The business app credentials authenticate API calls; the personal buyer login is
used in the browser to pay the test invoice. They serve different purposes.

The core create/send/verify test can run before shared HTTP routes or hosting
exist. Credentials can be supplied privately in a local process environment;
Git is not a runtime dependency. Before persisting a private `.env` or committing,
verify effective ignore rules in the actual repository. Never place credential
values in command arguments or literal shell commands saved in history.

## Acceptance steps and required evidence

| Step | Status | Completion evidence |
|---|---|---|
| Standalone code review | Accepted, as reported by the user | Member 4 review above |
| Offline regressions | Passed 2026-10-31 | 178 Python passes, 3 Sandbox skips; 7 JS passes |
| Local backup/restart drill | Passed 2026-10-31 | Seven synthetic recovery tests; independent process restart and committed WAL capture included |
| Private Sandbox app/accounts | Deferred by user | Business app and separate personal payer available locally |
| Runtime configuration/persistent local DB | Pending | Sandbox mode, private credentials, correct payer and existing restricted DB directory |
| Real create/send | Pending | Explicit one-cent approval recorded; actual Sandbox draft/send response; saved provider binding/URL |
| Read actual invoice | Pending | Fresh authenticated GET of that Sandbox invoice validates successfully |
| Manual Sandbox payment | Pending | User pays as the separate personal Sandbox payer |
| Verify paid | Pending | Fresh PayPal GET matches approved identity/terms and records VERIFIED_PAID |
| Repeat/reopen checks | Pending | No duplicate financial event for unchanged evidence; cash counted once; persistent ledger passes integrity after reopening |
| Real webhook delivery | Shared dependency | Registered HTTPS endpoint, real signature verification, duplicate/out-of-order and outage/reconciliation checks |
| Hosted durability/reconciliation | Shared dependency | Persistent storage, scheduled sweep, restart survival and backup/restore verified |
| Git/history and shared release checks | Shared dependency | Actual team repository scanned; API authorization/contract/UI tests accepted |

Use [SANDBOX_RUNBOOK.md](SANDBOX_RUNBOOK.md) for test commands. Sending needs
its explicit acknowledgement and records an approval before dispatch. Each
create/send test run creates a new approved one-cent invoice; do not rerun it
blindly. After an uncertain result, preserve the ledger and reconcile the saved
operation. After creation, unset the send acknowledgement before running paid
verification checks.

Record only sanitized counts, dates, states and opaque references here after
real tests run. Do not attach raw provider bodies or secrets. A skipped test is
not evidence of a successful live test. Do not mark full Member 3 acceptance
complete until the applicable pending checks have evidence.
