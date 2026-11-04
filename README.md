# CashFlow AI

Cash-flow planning and recovery for a small business: forecast a reserve shortfall, understand the evidence, compare a what-if scenario, and approve an invoice workflow whose payment status comes only from PayPal.

The integrated website uses a **clearly labelled fictional Juniper Studio dataset**. Forecasts and scenarios run Member 1's financial engine; recovery runs Member 2's evidence-based analysis; invoices and the append-only ledger run Member 3's services. Member 4's frontend (merged from the `frontend` branch) and the authenticated API connect these modules. The earlier replacement UI has been removed.

**Live PayPal Sandbox acceptance is intentionally skipped at the user's request.** Offline tests use fake transports. No claim is made that real invoice creation, sending, or payment verification has been validated with PayPal credentials. Hosting, private account setup, and a public demonstration remain deployment tasks.

## Run locally

Use Python 3.12 or newer and Node.js 24 LTS. Run from the repository root. Linux/WSL is recommended for the complete test suite: Member 1's optional model-monitoring and retraining persistence use POSIX file locks. The website's core forecast/scenario flow does not load those optional services on Windows.

Windows CMD:

```bat
python -m venv .venv
.venv\Scripts\python -m pip install -r backend\requirements-dev.txt
copy .env.example .env
cd frontend
npm ci
npm run build
cd ..
.venv\Scripts\python -m backend.app.main
```

Linux / WSL:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt
cp .env.example .env
cd frontend
npm ci
npm run build
cd ..
.venv/bin/python -m backend.app.main
```

Open **http://127.0.0.1:8000**. Use that exact origin (not a different hostname) for sign-in and form submissions. Do not overwrite an existing private `.env` when updating the checkout.

Without credentials the app provides read-only forecast, scenario, and recovery analysis. To test proposals and approvals, privately set `CASHFLOW_ADMIN_PASSWORD` in `.env` to a unique password of 12–256 characters and restart. Never use a published example password. The site then requires sign-in; no password or token is stored in browser local storage. Sessions expire after 30 minutes and are invalidated by server restart.

## What to try

1. Review opening **demo** cash, the reserve, projected low point, and breach date.
2. Open Forecast and change the horizon between 7, 14, and 30 days.
3. In Scenarios, change receipt timing, revenue/expense percentages, or additional expenses. Compare the resulting balances; no account is changed.
4. In AI Rescue, run analysis. Review explanations, evidence IDs, and assumptions. With no external AI configured, the interface explicitly shows deterministic analysis.
5. After administrator sign-in, open Payments & Ledger and record a receivable proposal. Its ledger state is `PROPOSED`, with zero recovered cash.
6. Inspect the ledger row and explicitly approve the amount and administrator-configured test payer. Approval alone sends nothing.
7. When PayPal is privately configured, create a draft, send it, then verify. Only a fresh matching PayPal response can yield `VERIFIED_PAID`.

A failed refresh hides old financial values. An uncertain payment request displays an honest error; refresh and reconcile rather than generating a new operation key. Partial, offline-marked, refunded, and unresolved entries do not contribute to verified recovered cash.

## Optional integrations

All keys remain server-side in `.env` or hosting environment variables. **Never paste or commit secrets.** The checked-in environment template is blank. Build the frontend without credentials; never use a `VITE_` variable for secrets.

PayPal requires `CASHFLOW_PAYPAL_ENABLED=true`, `PAYPAL_MODE=sandbox`, a Sandbox REST client ID/secret, and `PAYPAL_SANDBOX_PAYER_EMAIL` for a Sandbox personal test account. Configure a Sandbox webhook ID only if receiving webhooks. The host is pinned to `https://api-m.sandbox.paypal.com`; live mode or any alternate PayPal URL/host fails startup. All three fictional receivables target the one configured test payer: this is a **single-business demonstration**, not a multi-customer production invoicing system. Do not remap the approved payer reference while invoices exist.

Optional external AI requires `CASHFLOW_AI_ENABLED=true`, `AI_BASE_URL`, `AI_MODEL`, `AI_API_KEY`, and administrator authentication. Member 2's existing adapter selects supported explanation codes and ranks known actions; it cannot create financial facts or authorize payments. Invalid output, timeout, or provider outage falls back to deterministic analysis. Only minimal candidate metadata is sent, not payer emails or customer names. No external AI provider was called during integration testing.

See [the payment runbook](backend/app/payments/SANDBOX_RUNBOOK.md), [Postman templates](backend/app/payments/postman/README.md), and [recovery runbook](backend/app/ledger/RECOVERY_RUNBOOK.md). Before adopting a sponsor service, check its Devpost page for the hackathon's actual offer. Templates are not evidence of a live Postman run.

## Tests

Run the full offline backend suite on Linux/WSL:

```sh
.venv/bin/python -B -m backend.tests.run_offline
node --test backend/tests/payments/postman_guards.test.cjs
```

The runner blocks outbound sockets and forces the three live Sandbox tests off even if the shell has an opt-in flag. Tests use synthetic fixtures and scripted responses, never real payer data. For Member 3 only, the portable standalone runner is `python -B -m backend.tests.payments.run_tests`.

Browser tests build and run two temporary loopback servers: read-only demo and authenticated fake-provider flow. They do not load `.env`; their database and test password are disposable. They never call PayPal.

```sh
cd frontend
npm ci
npm test
npm run build
npx playwright install chromium
CASHFLOW_TEST_PYTHON=.venv/bin/python npm run test:e2e
```

The Python path is resolved from the **repository root** by the test server (an absolute path also works). On Windows CMD set `CASHFLOW_TEST_PYTHON=.venv\Scripts\python.exe` and `CASHFLOW_BROWSER_CHANNEL=chrome` to use an installed Chrome instead of downloading Chromium, then `npm run test:e2e`. Do not run against a production server. Test screenshots stay ignored under `frontend/test-results/`.

CI runs the Linux offline suite, Postman guards, frontend unit tests, production build, and browser checks. The exact installed frontend dependency versions are captured in `frontend/package-lock.json`.

## Deployment and limitations

See [deployment instructions](docs/DEPLOYMENT.md) for Docker, HTTPS, persistent storage, and restore requirements. There is no automatic cloud deployment. Run a **single backend worker**: session and login-rate-limit state are in memory; the reconciliation worker is attached to this process. Public origins require HTTPS and an administrator password. Locally, the application serves the built frontend. For deployment, Vercel serves the frontend and forwards API requests to the persistent backend; secure cookies and CSRF checks continue to apply. Do not expose Vite's development server publicly.

The forecast uses a fixed fictional opening snapshot dated 2026-11-02. A newly verified invoice is shown separately in the ledger; it is **not silently added to that opening snapshot or counted again as recovered forecast cash**. Actual bank ingestion, customer onboarding, tenant isolation, production payments, multi-worker authentication, and public deployment acceptance are outside this demo. The advanced forecasting modules remain available through their documented Python interfaces.

API integration and security boundaries: [API notes](backend/app/api/README.md). Branch integration and executed verification: [integration report](docs/INTEGRATION_REPORT.md).
