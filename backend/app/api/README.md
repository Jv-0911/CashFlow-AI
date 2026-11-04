# Integrated single-business API

All money is integer USD cents, dates are ISO 8601, and all business fixtures are fictional. The application is a single-business demo with one administrator, not a multi-tenant service. The configured origin, cookie, and CSRF controls belong to this integration layer. Payment truth remains exclusively in Member 3's fresh-fetch verification service.

| Route | Behavior / access |
|---|---|
| `GET /health`, `/api/v1/health` | Public health status |
| `GET /api/v1/session` | Authentication/configuration status; CSRF token only for an authenticated session |
| `POST /api/v1/session` | Password login; exact Origin, bounded attempts; HttpOnly SameSite=Strict cookie |
| `DELETE /api/v1/session` | Sign out; session, Origin and CSRF required |
| `GET /api/v1/dashboard` | Actual engine output and fictional source records; private ledger totals only after sign-in |
| `GET /api/v1/forecast?horizon_days=14` | Actual forecast engine; 1–30 days; original fixture retained at `/forecast/demo` |
| `POST /api/v1/scenario` | Adapter for Member 4 controls: percentages, receipt delay, lump sum and recurring payroll; balances calculated by Member 1; hypothetical only |
| `POST /api/v1/scenarios` | `event_id`, `delay_days` (1–30), optional `horizon_days`; move a server-known expense; no baseline mutation |
| `POST /api/v1/rescue/analyze?horizon_days=14` | Server-owned forecast/evidence; deterministic fallback or explicitly configured AI |
| `GET /api/v1/ledger`, `/api/v1/invoices` | Authenticated, integrity-checked ledger serializer |
| `POST /api/v1/ledger/proposals` | `receivable_id`; amount and currency come from the server, stable idempotency key |
| `POST /api/v1/ledger/{entry_id}/approve` | `expected_sequence`, explicit boolean `confirmed=true`; actor derives from authenticated session |
| `POST /api/v1/invoices` | `entry_id`; approved draft creation only |
| `POST /api/v1/invoices/{entry_id}/send` | Approved send with durable operation claim |
| `GET /api/v1/payments/{entry_id}` | Stored snapshot only; no GET-triggered provider call |
| `POST /api/v1/payments/{entry_id}/verify` | Fresh authoritative PayPal fetch through verification service |
| `POST /api/v1/payments/reconcile` | Reconcile uncertain operations; per-entry outcomes |
| `POST /api/v1/webhooks/paypal` | Public callback only when configured; provider signature verification, deduplication, fresh GET |

When a password is configured, all analysis routes except the explicitly synthetic legacy fixture require sign-in. Without a password, only read-only synthetic analysis is available. Every ledger mutation and configured external AI request requires session + exact Origin + CSRF token. Webhook authentication is PayPal signature verification instead of browser authentication. Private payment and AI flags default off, independently of whether credentials exist in the shell.

Unexpected fields, actor overrides, client amounts, status overrides, malformed dates/JSON and floats for integer input are rejected. Financial writes use stable server-generated operation keys; there is no endpoint for setting status or editing/deleting a ledger event. Database uniqueness, state transitions, and hash integrity remain enforced by the existing ledger service. Error responses follow `{error: {code, message, request_id}}`; no secret/body reflection. The HTTP server disables access logging in documented commands.

Read-only scenarios require Origin too. JSON bodies are bounded to 64 KiB (256 KiB for webhook events) with a ten-second receive deadline. Public HTTPS origins require secure cookies and an administrator password. Browser sessions last thirty minutes, live in memory, and disappear on restart. One worker/instance is supported. The frontend validates response shapes and hides stale values on failed refresh.

Forecast receipts are assumptions in a fixed synthetic snapshot. Verified recovery is displayed separately and is never added a second time to forecast cash. Rescue analysis excludes ledger states that cannot safely map to Member 2's schema and suppresses collection advice for verified paid items. Partial/offline/refunded results cannot become verified cash. No model is in the payment verification path.

The payer reference `demo_payer` is resolved privately by the server. It maps only to the configured Sandbox test payer; do not change that association for an existing approved entry. This demo does not accept arbitrary customer emails or external invoice IDs from a browser.

## Member 4 frontend and split hosting

The `frontend` branch supplies the UI. Browser adapters map uppercase Member 3 ledger states without merging partial/offline/refunded states into verified completion. Empty ledgers are valid; malformed responses and outages never become demo payments. Only server totals that agree with verified entries are displayed.

The forecast response exposes daily integer-cent values plus `details.forecast_id`; internal floating-point model-error statistics stay in Member 1's Python results rather than the dashboard response. Scenario controls translate to `calculate_balances`; they never modify baseline or ledger data. The existing expense-move endpoint is retained.

`CASHFLOW_PUBLIC_ORIGIN` is the exact Vercel HTTPS origin. `CASHFLOW_BACKEND_HOST` adds only the exact backend DNS name to trusted hosts. The Vercel configuration proxies `/api/*` and `/health` before SPA routes, preserving browser Origin, cookies and CSRF headers. No CORS wildcard or client-held payment credential is introduced. Public deployment acceptance must verify this forwarding behavior on the actual hosts.
