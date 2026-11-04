# Final integration audit — 2026-11-04

The existing Member 4 frontend and the integrated forecast, rescue, payments and ledger modules were reviewed and tested. This audit fixes two browser issues without replacing teammates' implementations or changing payment-verification rules. Code fixes are in commit `4cef0f5`.

## Credentials and possible costs

- No exposed credentials were detected in the fetched Git history, including merge changes, or the compiled frontend. The final code-history scan covered 24 commits (about 7.99 MB); the bundle scan covered about 1.26 MB. Automated scans cannot prove that a secret has never existed elsewhere.
- Credential fields in both checked-in `.env.example` files are blank. No populated `.env` was present in this checkout. The audited process had no configured PayPal credentials, AI key or administrator password.
- Ignore rules cover `.env`, private Postman environments, `data/`, databases, private keys, logs and browser artifacts. Generated files and the unrelated accidental untracked shell-output file were not added to the release.
- `CASHFLOW_AI_ENABLED=false` and `CASHFLOW_PAYPAL_ENABLED=false` are the defaults. Local forecast and deterministic rescue analysis need no paid AI key. No real AI or PayPal API call was made during this audit.
- Enabling external AI with a provider key can incur that provider's charges. Authentication, CSRF checks and request throttling protect the endpoint, but the application has no monetary spending cap. Configure provider-side budgets/limits before enabling it; do not put credentials in frontend or `VITE_` variables.
- PayPal is restricted to the pinned Sandbox host. Live payment mode is rejected. Real credentialed Sandbox behavior remains untested by request.
- Hosting, persistent storage and traffic can incur charges independently of API keys. Review the selected hosting plan and [Vercel usage controls](https://vercel.com/docs/pricing/manage-and-optimize-usage). Private hosting environment variables, account subscriptions and billing dashboards were not accessible in this audit.

## Problems fixed

1. **Reset to Baseline retained a 14-day receipt delay.** Reset now sends zero timing, percentage, payroll and lump-sum changes. The browser regression checks both the request and zero net forecast variance.
2. **Partial reconciliation warnings disappeared during refresh.** The ledger page now owns the warning, so unresolved-invoice feedback survives replacement of its action controls. A browser regression simulates a timeout result and checks the warning after refresh.
3. **The expanded browser suite exceeded the real login throttle.** Tests now reuse a disposable session in memory. The first login still exercises the real form, separate tests still reject forged local storage, and the production login limit is unchanged. No session file or credential is exported.
4. **Workflow usability:** added manual dispatch, explicit read-only repository permissions and cancellation of superseded runs on the same branch. Existing offline test, build, browser and container checks remain configured.

Both new browser regressions were observed failing before the fixes and passing afterwards.

## Executed checks

| Check | Result |
|---|---|
| Complete offline backend runner | 978 passed, 432 subtests passed; 3 live PayPal tests skipped intentionally |
| Postman collection guards | 7 passed |
| Frontend unit/integration checks | 154 passed; TypeScript and Oxlint passed |
| Browser suite using disposable local servers and fake PayPal transport | 7 passed |
| Production frontend build | Passed |
| Fresh clone of committed fixes: `npm ci`, `npm test`, `npm run build` | Passed; 154 tests passed again |
| Gitleaks fetched-history scan with `--all --full-history -m` and redaction | No leaks found |
| Gitleaks compiled-frontend scan | No leaks found |
| `npm audit` | Zero known vulnerabilities |
| `pip-audit` of pinned backend constraints | No known vulnerabilities found |
| Git whitespace check and private-file ignore checks | Passed |

The full backend run used the existing Linux/WSL Python environment. The frontend and browser checks used Windows with installed Chrome; the workflow selects Node 24 and Chromium. Dependency checks describe the pinned versions and advisory databases available on the audit date.

The retained landing-page Three.js chunk produces a non-fatal size warning (about 526 KB before gzip). Starlette also emits a test-client deprecation warning. Neither failed the checks; both are maintenance items.

## Workflow evidence and deployment limits

At audit time GitHub's API exposed one successful historical workflow, [run 41675969397](https://github.com/Jv-0911/CashFlow-AI/actions/runs/41675969397), for `cfdc7e8`. No run was available for the restored release `a9d2c4c`. That old green run is **not** evidence that the current integrated release passed GitHub Actions. GitHub reported degraded Git Operations and Actions on [its status page](https://www.githubstatus.com/) during this audit. A successful push must be distinguished from a completed workflow.

A Docker engine was unavailable locally, so the current container build remains unverified until the workflow's Docker step or an equivalent host build completes. No website was deployed or tested against a public hosting URL.

Before public use, follow [DEPLOYMENT.md](DEPLOYMENT.md):

1. Set the Vercel project root to `frontend` and configure `CASHFLOW_BACKEND_URL` as the persistent backend's HTTPS origin. Keep secrets out of the frontend project.
2. Set the backend's exact public frontend origin, backend hostname and a private administrator password. Verify sign-in, cookies, API forwarding and deep links at the actual hosted domains.
3. Mount writable persistent ledger storage for container UID 10001, use one backend worker, and validate backups and restore. Ephemeral storage is unsuitable for the ledger.
4. Confirm a workflow run for the final pushed commit, including the container build. Manual **Run workflow** is now available when GitHub Actions is operating normally.
5. Keep external integrations disabled unless deliberately configured. The three live PayPal tests remain deferred at the user's request.

The site remains a single-business demonstration with labelled fictional USD data. Customer onboarding, Google sign-in, email verification/reset services, bank ingestion and live-money payments are not implemented production services. Session state is in memory and expires on restart. These limits must not be presented as completed production capabilities.
