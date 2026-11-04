# Deploying the integrated demonstration

The integration does not create a hosting account or deploy automatically. Before using Render or another sponsor, check its Devpost page for this hackathon's actual offer.

## Vercel frontend

1. Import `Jv-0911/CashFlow-AI`, production branch `main`.
2. Set **Root Directory** to `frontend`, framework **Vite**, Node **24.x**, install `npm ci`, build `npm run build`, output `dist`.
3. Set `CASHFLOW_BACKEND_URL` to the persistent backend's exact HTTPS origin, for example `https://api.example.test` (replace with your real host). No path, query, port, credentials, or trailing API suffix. This is a routing value, not a secret. `frontend/vercel.ts` validates it at configuration time.
4. Give the frontend a stable production URL. Set that exact origin on the backend. Do not grant wildcard preview origins access to the payment backend; use an isolated backend/database for preview testing.
5. Deploy after the backend is healthy. Rewrites forward `/api/*` and `/health` before React deep-link routes. Financial/session responses are never cached. No Python functions or ledger databases are deployed in the frontend project.

Vercel supports programmatic build-time configuration and external rewrites: [configuration documentation](https://vercel.com/docs/project-configuration/vercel-ts), [rewrites documentation](https://vercel.com/docs/routing/rewrites).

## Persistent backend

Build the root Dockerfile with repository-root build context. It contains only the existing backend, contracts and runtime dependencies. Use one service instance with a persistent disk. Start command is already provided:

```sh
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log
```

Configure HTTPS routing to port 8000 and `/health` as the health-check path. For Render choose a Docker web service and attach a persistent disk; before adopting a sponsor service, check its Devpost offer. All hosting setup remains manual. Do not log request bodies, cookies, authorization headers or provider error bodies.

Required backend environment settings:

| Setting | Value |
|---|---|
| `CASHFLOW_PUBLIC_ORIGIN` | Exact frontend production origin, e.g. `https://your-site.vercel.app`, no trailing slash |
| `CASHFLOW_BACKEND_HOST` | Exact backend DNS hostname, e.g. `your-backend.onrender.com`, no scheme/path/port/wildcard |
| `CASHFLOW_ADMIN_PASSWORD` | Privately generated unique 12–256 character password |
| `LEDGER_DB_PATH` | `/app/data/ledger.db` |
| `PAYPAL_MODE` | `sandbox` |
| `CASHFLOW_PAYPAL_ENABLED` | `false` until privately configured; keep false when skipping live tests |
| `CASHFLOW_AI_ENABLED` | `false` unless intentionally configuring a supported AI provider |

Mount the persistent disk at `/app/data`, writable by application UID 10001. Check actual mounted ownership: the image's directory ownership does not override an attached volume's permissions. Never use `/tmp` or an ephemeral deployment filesystem for the ledger. Store all optional credentials only in backend environment settings; never in Vercel frontend variables, Git, screenshots or exported environments.

One worker and one instance are required because sessions, throttles and reconciliation scheduling are process-local. A restart invalidates sign-in sessions; it must preserve ledger entries. Configure host-level request limits and trusted proxy/IP handling without trusting arbitrary forwarded headers.

## Hosted acceptance (performed by you)

- Open the production frontend and refresh `/dashboard/forecast` directly; assets and deep links must work.
- Sign in. Confirm `/api/v1/session` is authenticated, cookies are Secure/HttpOnly/SameSite=Strict, and no API response is cached. The proxy must preserve browser Origin, cookies and `X-CSRF-Token`; do not weaken server checks if forwarding is misconfigured.
- Check 7/14/30 day forecasts, AI Rescue, scenarios, analytics, themes and saved widget layouts. All business data is explicitly fictional.
- Record one proposal, inspect its amount, tick explicit approval and record approval. With PayPal disabled, invoice buttons remain unavailable and verified recovered cash stays zero.
- Sign out and verify private ledger/API requests are rejected. Disconnect the backend and confirm an error rather than replacement fixture payments.
- Test redeploy persistence and backup/restore below. Review host logs for sensitive data.

Google sign-in, self-registration, email verification/reset and multiple tenants are not implemented. Access is through the configured administrator password. Local UI preferences do not change backend financial policy.

## Durable ledger and recovery acceptance

Use the existing [ledger recovery runbook](../backend/app/ledger/RECOVERY_RUNBOOK.md). Its online SQLite backup operation preserves WAL changes; copying only the main database while running is insufficient. Keep independently stored integrity checkpoints and encrypted, restricted backups off the application disk. Test restore into a separate path and verify integrity before switching service paths.

After deployment, record a proposal and approval, restart/redeploy, then confirm the same entries remain. Test a backup/restore drill separately. Confirm secrets and private data do not appear in access/error logs. The hash chain detects ordinary modification, not an administrator who can rewrite every record and its hashes; independent checkpoints and backups remain necessary.

The application checks integrity on startup and on ledger operations. When payments are explicitly enabled it reconciles relevant entries every 60 seconds, including previously verified entries to observe refunds. A failed sweep preserves state; manual reconciliation returns per-entry error codes. A provider outage is not a new payment status.

## Still unverified externally

No real cloud deployment, credentialed AI provider call, or PayPal Sandbox test was performed during integration. Complete those checks only with the relevant private setup and authorization. Live Sandbox tests remain skipped by user choice. The app must not be described as production-ready payment infrastructure.

References: [FastAPI process deployment](https://fastapi.tiangolo.com/deployment/server-workers/), [Playwright local test servers](https://playwright.dev/docs/test-webserver).
