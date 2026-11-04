# Member 4 frontend

This is the frontend from `origin/frontend` commit `9b67234`, integrated with the existing backend. Its landing page, dashboard, charts, theme, pages and drag-and-drop customization are retained. Integration changes live mainly in `src/api/`, session handling, and the existing ledger page/drawer.

Use Node 24 LTS. Run `npm ci`, `npm test`, and `npm run build`. From the repository root start the Python application as described in the root README; it serves `dist/` locally. For Vite development, set the backend's `CASHFLOW_PUBLIC_ORIGIN=http://localhost:5173` and open that exact URL. The existing Vite proxy forwards `/api` and `/health` to port 8000.

## Deployment

Deploy this directory as the Vercel project root. `vercel.ts` sets Vite, `npm ci`, `npm run build`, output `dist`, same-origin API forwarding and deep links. Set only the non-secret `CASHFLOW_BACKEND_URL=https://your-persistent-backend-host` in Vercel; missing/invalid values fail configuration. Keep all passwords and PayPal/AI credentials on the backend. See [deployment instructions](../docs/DEPLOYMENT.md).

## Access and data

Sign-in uses the backend's configured single-business administrator password; the email field is a display label, not an identity provider. Local storage never authorizes payment actions. Registration, Google authentication, email verification and password-reset delivery are not configured; their original screens explain that limitation without granting access or pretending to send email.

Forecast/scenario/analytics use fictional business data calculated by the backend. Rescue suggestions are estimates, not recovered cash. Recommendations are not added again to baseline receipts. The ledger comes only from authenticated backend reads; provider failure never substitutes local fixture payments. The existing pure fixture/model helpers remain for isolated unit tests and illustrative landing content.

Browser display/customization settings are local preferences. They do not change backend amounts, currency, reserve policy, approval or provider status. The demo operates in USD.

## Browser checks

Build first, then run `npm run test:e2e` with `CASHFLOW_TEST_PYTHON` pointing to the backend Python environment. The fixture servers run on loopback ports 8766/8767 with a temporary ledger, disposable password, and fake provider. See the root README for Windows and Linux commands. No live PayPal calls occur.
