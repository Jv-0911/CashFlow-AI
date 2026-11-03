# Deploying the integrated demonstration

The integration does not create a hosting account or deploy automatically. Before using Render or another sponsor, check its Devpost page for this hackathon's actual offer.

## Build and serve

Use the checked-in multi-stage Dockerfile, or install `backend/requirements.txt`, run `npm ci && npm run build` inside `frontend`, and start from the repository root:

```sh
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log
```

Configure the host to route HTTPS to port 8000. Serve frontend and API from the same origin. `/health` is the health-check path. Do not use a separate frontend host without designing and testing a new origin/authentication policy. Do not enable request-body, authorization-header, cookie, or error-body logging in your reverse proxy. Do not expose the development server.

For Render, choose a Docker web service, a single instance, and persistent storage. Set the public origin to the exact HTTPS URL assigned by Render. Use dashboard environment variables for credentials; do not put their values in a blueprint, Git, a public environment export, or a screenshot.

## Required manual settings

- `CASHFLOW_PUBLIC_ORIGIN=https://your-exact-host` with no path or trailing slash.
- `CASHFLOW_ADMIN_PASSWORD`: a privately generated strong unique password, at least 12 characters. Public hosting without it fails startup.
- `LEDGER_DB_PATH=/app/data/ledger.db` for the Docker layout. Mount a persistent disk at `/app/data`, writable only by the application user (UID 10001). Verify ownership for your host's mounted volume. A plain ephemeral filesystem is unacceptable.
- `PAYPAL_MODE=sandbox`; keep `CASHFLOW_PAYPAL_ENABLED=false` until privately configured. Never use live credentials. Optional PayPal/AI values are described in `.env.example` and their module runbooks.
- One worker and one application instance. Sessions, login throttling, and the periodic reconciliation scheduler are process-local. Scaling requires shared session/rate-limit infrastructure and one coordinated scheduler first.
- An HTTPS proxy, private environment administration, access restrictions, and host-level request limits. Verify forwarding/IP settings against your host; do not trust arbitrary forwarded headers. The app limits sign-ins and financial actions and bounds request bodies.

## Durable ledger and recovery acceptance

Use the existing [ledger recovery runbook](../backend/app/ledger/RECOVERY_RUNBOOK.md). Its online SQLite backup operation preserves WAL changes; copying only the main database while running is insufficient. Keep independently stored integrity checkpoints and encrypted, restricted backups off the application disk. Test restore into a separate path and verify integrity before switching service paths.

After deployment, record a proposal and approval, restart/redeploy, then confirm the same entries remain. Test a backup/restore drill separately. Confirm secrets and private data do not appear in access/error logs. The hash chain detects ordinary modification, not an administrator who can rewrite every record and its hashes; independent checkpoints and backups remain necessary.

The application checks integrity on startup and on ledger operations. When payments are explicitly enabled it reconciles relevant entries every 60 seconds, including previously verified entries to observe refunds. A failed sweep preserves state; manual reconciliation returns per-entry error codes. A provider outage is not a new payment status.

## Still unverified externally

No real cloud deployment, credentialed AI provider call, or PayPal Sandbox test was performed during integration. Complete those checks only with the relevant private setup and authorization. Live Sandbox tests remain skipped by user choice. The app must not be described as production-ready payment infrastructure.

References: [FastAPI process deployment](https://fastapi.tiangolo.com/deployment/server-workers/), [Playwright local test servers](https://playwright.dev/docs/test-webserver).
