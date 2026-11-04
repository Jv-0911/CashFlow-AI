# Vercel readiness

Member 4's frontend is now sourced from `frontend` commit `9b67234`. The previous assistant frontend is removed from the current tree; Git history is preserved. Integration keeps the original UI and connects it to the existing forecasting, rescue and payment services.

Deployment configuration is in `frontend/vercel.ts`; the backend-only `Dockerfile` runs one persistent Python process. Follow [DEPLOYMENT.md](DEPLOYMENT.md) for exact project settings, origins, storage and acceptance checks.

The frontend can be deployed on Vercel. The current SQLite ledger, process-local sessions and reconciliation worker require a separate persistent backend. Do not move the ledger into Vercel temporary storage.

Remaining user setup: frontend/backend public hostnames, private administrator password, backend persistent disk ownership, backups/restore verification, and deployment acceptance. PayPal Sandbox tests remain skipped by explicit request. No cloud deployment or live provider acceptance is claimed.
