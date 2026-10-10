# CashFlow AI 2.0 — Master Team Work Plan

**Project:** CashFlow AI 2.0  
**Team size:** 4 members  
**Purpose:** Build a reliable AI-powered cash-flow forecasting and recovery assistant for small businesses.

---

# 1. Project Objective

Build a working application that helps a small business:

1. Understand its current cash position.
2. Forecast upcoming cash inflows, expenses, and daily balances.
3. Identify when cash may fall below its safety reserve.
4. Understand why a shortage is projected.
5. Explore what-if scenarios before choosing an action.
6. Receive evidence-based recommendations for recovering cash.
7. Create and manage invoices through PayPal Sandbox.
8. Verify payment status using PayPal's authoritative responses.
9. Track proposed recovery actions separately from actual, verified payments.

The final application must demonstrate a complete workflow from the dashboard to a forecast, explanation, scenario, recovery action, and payment-status verification.

**Important financial rule:** Forecasts and AI estimates are projections, not confirmed cash receipts. Only verified payment information may be recorded as an actual completed payment.

# 2. Team Roles and Ownership

| Member | Role | Primary ownership |
|---|---|---|
| Member 1 | Financial Engine Developer | `backend/app/forecast/` |
| Member 2 | AI Rescue Agent Developer | `backend/app/rescue_ai/` |
| Member 3 | PayPal & Recovery Ledger Developer | `backend/app/payments/`, `backend/app/ledger/` |
| Member 4 | Frontend & Integration Lead | `frontend/`, `backend/app/api/`, `tests/e2e/` |

Each member is responsible for implementing, testing, documenting, and debugging their own module.

Member 4 coordinates integration but is not responsible for independently writing every other member's module.

# 3. Shared Repository Structure

```text
CASHFLOW AI/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── features/
│   │   │   ├── dashboard/
│   │   │   ├── forecast/
│   │   │   ├── rescue/
│   │   │   ├── scenarios/
│   │   │   └── payments/
│   │   ├── api/
│   │   ├── types/
│   │   └── App.tsx
│   └── package.json
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── forecast/
│   │   ├── rescue_ai/
│   │   ├── payments/
│   │   ├── ledger/
│   │   ├── models/
│   │   ├── config.py
│   │   └── main.py
│   ├── tests/
│   │   ├── forecast/
│   │   ├── rescue_ai/
│   │   ├── payments/
│   │   └── ledger/
│   └── requirements.txt
├── contracts/
│   ├── fixtures/
│   ├── forecast-response.example.json
│   ├── rescue-response.example.json
│   ├── scenario-request.example.json
│   └── payment-ledger.example.json
├── tests/
│   └── e2e/
├── .env.example
├── .gitignore
├── TEAM_WORKPLAN.md
├── README.md
└── LICENSE
```

This is the target structure. Members may add files within their owned modules when needed. Agree on any changes that affect shared interfaces before implementing them.

# 4. Member 1 — Financial Engine Developer

## Mission

Build the deterministic financial calculation engine. All monetary calculations and forecasts must be produced by application code, not invented by an AI model.

## Owned files

```text
backend/app/forecast/
backend/tests/forecast/
```

Coordinate changes to shared Pydantic models with Member 4.

## Tasks

### A. Define financial data models

- Define cash-flow inputs, receipts, expenses, opening balance, safety reserve, and forecast-day output.
- Use integer cents for money.
- Use ISO 8601 dates.
- Validate that amounts, dates, currencies, and required identifiers are valid.
- Document how missing or uncertain payment dates are handled.

### B. Implement the forecasting engine

- Calculate daily opening balances, receipts, expenses, and closing balances.
- Support configurable forecast horizons, with an agreed maximum of 30 days for the initial demo.
- Calculate the first date the projected closing balance falls below the safety reserve.
- Handle days with no transactions.
- Avoid counting the same receipt twice.
- Clearly distinguish scheduled or expected receipts from money already received.
- Make forecast results reproducible for the same inputs.

### C. Implement scenario calculations

- Allow a scenario to add, remove, or change an eligible future cash-flow event.
- Recalculate the daily balances and reserve-breach date.
- Return the baseline and scenario results for comparison.
- Show the projected effect of each change on closing cash.
- Never silently change the original baseline data.
- Identify assumptions and the events changed by the scenario.

### D. Write automated tests

Test at least:

- Normal inflows and outflows.
- No transactions.
- Balance remaining above the reserve.
- Balance crossing below the reserve.
- Balance exactly equal to the reserve.
- Large amounts and zero-value amounts where allowed.
- Invalid inputs and unsupported forecast horizons.
- Multiple events on the same day.
- Scenario changes and recalculation.
- Duplicate event handling.
- Correct currency and date validation.

### E. Deliverables

- Working forecasting module.
- Scenario calculation function.
- Validated data models.
- Unit tests.
- Sample input fixtures.
- API integration notes.
- README section explaining the calculation assumptions.

### Definition of Done

- Forecast calculations pass automated tests.
- Money uses integer cents internally.
- The same input produces the same output.
- Reserve-breach detection is correct.
- Scenarios return recalculated results without altering the baseline.
- Member 4 can call the module through the agreed API contract.

# 5. Member 2 — AI Rescue Agent Developer

## Mission

Build an AI-assisted explanation and recommendation module that uses actual application data to explain cash-flow risks and propose practical recovery actions.

## Owned files

```text
backend/app/rescue_ai/
backend/tests/rescue_ai/
```

## Tasks

### A. Build the rescue analysis interface

- Accept forecast results, relevant transactions, invoices, and reserve-breach information.
- Accept evidence identifiers so recommendations can be traced to source records.
- Define a structured request and response model.
- Keep AI-provider configuration outside source code.

### B. Implement shortage diagnosis

- Explain the principal causes of a projected shortage.
- Reference supporting transaction, invoice, or forecast identifiers.
- Distinguish confirmed facts from assumptions.
- Avoid claiming that a forecasted event definitely will occur.
- Return a clear explanation when there is insufficient evidence.

### C. Implement ranked recovery actions

Examples include:

- Following up on an overdue invoice.
- Requesting payment earlier, where appropriate.
- Reviewing discretionary expenses.
- Simulating a change in a future expense.
- Reviewing upcoming payment obligations.

Each recommendation must include:

- Stable action identifier.
- Title and explanation.
- Supporting evidence identifiers.
- Estimated financial impact, when calculable.
- Assumptions and uncertainty.
- Suggested priority.
- Any action requiring human approval.

### D. Integrate the AI provider safely

- Use a configurable provider interface so the application is not tied unnecessarily to one provider.
- Validate model responses against a schema.
- Handle timeouts, provider errors, malformed responses, and rate limits.
- Provide a deterministic fallback response if AI is unavailable.
- Keep API keys in environment variables.
- Do not send unnecessary sensitive business information to the provider.

### E. Financial and action safety

- Never let the AI invent transaction records, invoice amounts, or payment statuses.
- Calculate monetary impacts using deterministic code or validated financial-engine outputs.
- Never mark a payment as completed.
- Do not send invoices, execute payments, or make irreversible financial changes without the required user approval.
- Label estimates clearly as estimates.

### F. Write automated tests

Test:

- Valid analysis output.
- Empty or insufficient evidence.
- Unsupported evidence identifiers.
- Invalid model output.
- AI provider timeout.
- Provider unavailable.
- Fallback response.
- Recommendations with explicit assumptions.
- No fabricated financial figures.
- Correct handling of projected versus verified receipts.

### G. Deliverables

- AI rescue analysis module.
- Structured request and response schemas.
- Provider adapter and fallback.
- Unit tests.
- Example responses.
- Configuration documentation.
- Short explanation of model limitations.

### Definition of Done

- Responses validate against the agreed schema.
- Recommendations cite available evidence.
- Financial facts are not invented.
- Provider failure does not crash the dashboard.
- All critical tests pass.
- Member 4 can integrate the module through the agreed API.

# 6. Member 3 — PayPal & Recovery Ledger Developer

## Mission

Build the payment integration and recovery ledger, using PayPal Sandbox for the demo. Payment statuses must come from authoritative provider verification, not from an AI response or a browser redirect alone.

## Owned files

```text
backend/app/payments/
backend/app/ledger/
backend/tests/payments/
backend/tests/ledger/
```

## Tasks

### A. Implement PayPal Sandbox configuration

- Configure the Sandbox API base URL.
- Read client credentials from environment variables.
- Implement OAuth access-token acquisition and safe token handling.
- Set appropriate request timeouts.
- Handle authentication errors, rate limits, network errors, and provider failures.
- Ensure demo configuration cannot accidentally target live payment processing.

### B. Implement invoice operations

- Define the local invoice model and identifiers.
- Support creating invoices using the agreed provider workflow.
- Support sending or issuing invoices through Sandbox where the chosen API supports it.
- Store the relevant provider invoice identifier.
- Return the provider-approved invoice URL when available.
- Validate invoice amounts and currency.
- Handle repeated requests safely to avoid duplicate operations where supported.

### C. Verify payment status

- Retrieve invoice or payment information from PayPal.
- Normalize provider statuses into documented application states without losing the original provider status.
- Verify payment completion using the provider's authoritative response.
- Handle pending, cancelled, failed, expired, and unverified cases as applicable.
- If webhooks are used, validate their authenticity and handle duplicate or out-of-order events.
- Never treat a redirect to a success page as proof of payment.

### D. Implement the recovery ledger

Track:

- Ledger entry ID.
- Invoice or payment identifier.
- Amount in integer cents.
- Currency.
- Provider.
- Application status.
- Provider status and identifier.
- Creation and update timestamps.
- Verification timestamp, when applicable.
- Idempotency or correlation key, where appropriate.

Distinguish:

- Proposed recovery action.
- Invoice created or issued.
- Payment pending.
- Payment status awaiting verification.
- Verified completed payment.
- Failed, cancelled, or otherwise unresolved payment.

A proposed action must not be recorded as actual recovered cash. Prevent duplicate ledger entries for repeated notifications or requests.

### E. Write automated tests

- Valid invoice request.
- Invalid amount or currency.
- Authentication failure.
- Provider timeout.
- Invoice creation failure.
- Repeated request and idempotency.
- Pending payment.
- Verified completed payment.
- Failed or cancelled payment.
- Invalid webhook signature, if webhooks are implemented.
- Duplicate webhook event.
- Ledger consistency and duplicate prevention.
- No false completed-payment status.

Use mocked provider responses for unit tests. Use Sandbox credentials only for explicit integration tests.

### F. Deliverables

- PayPal Sandbox adapter.
- Invoice service.
- Payment-status verification service.
- Recovery ledger module.
- Unit tests and documented Sandbox test steps.
- Environment configuration documentation.
- Error handling and idempotency notes.

### Definition of Done

- Sandbox operations work using test credentials.
- Payment status is verified from the provider.
- Failures are represented honestly.
- Duplicate operations are controlled.
- Ledger states distinguish estimates from verified payments.
- No credentials are committed to Git.
- Member 4 can integrate invoice and ledger operations through the agreed API.

# 7. Member 4 — Frontend & Integration Lead

## Mission

Create the user-facing application, integrate all backend modules, coordinate contracts and Git workflow, and deliver a reliable end-to-end demonstration.

## Owned files

```text
frontend/
backend/app/api/
tests/e2e/
README.md
TEAM_WORKPLAN.md
```

Shared configuration changes must be coordinated with the team.

## Tasks

### A. Frontend foundation

- Set up React, TypeScript, Vite, and the agreed styling approach.
- Configure the API client and development environment.
- Define frontend types that match the backend contracts.
- Build reusable components for cards, tables, charts, forms, alerts, and loading states.
- Keep API calls out of presentation-only components where practical.
- Provide responsive layouts and accessible controls.

### B. Dashboard

Display:

- Current cash balance, clearly labelled as actual or demo data.
- Configured safety reserve.
- Forecast horizon.
- First projected reserve-breach date, when applicable.
- Daily projected receipts and expenses.
- Daily closing balances.
- Relevant warnings and forecast assumptions.

Use clear visual distinction between verified values, projections, and AI-generated explanations.

### C. Forecast experience

- Fetch forecast data from the backend.
- Display a daily cash-flow chart and a detailed table.
- Handle empty data and invalid responses.
- Show loading indicators and useful error messages.
- Support the agreed forecast horizon.
- Avoid displaying stale values as current when refresh fails.

### D. AI rescue experience

- Show shortage explanations and supporting evidence.
- Display ranked recovery recommendations.
- Show assumptions and estimated impact.
- Clearly label estimates.
- Ask for user approval before actions that require it.
- Handle unavailable AI responses gracefully.

### E. Scenario experience

- Provide controls for agreed what-if changes.
- Submit validated scenario requests.
- Display baseline versus scenario results.
- Show changes to projected balances and reserve-breach dates.
- Make it clear that a simulation does not change real accounts or execute payments.

### F. Payments and ledger experience

- Display invoices and their current statuses.
- Support the agreed invoice workflow.
- Show payment verification status and provider errors.
- Display ledger entries and their timestamps.
- Clearly distinguish pending, failed, and verified completed payments.
- Never show a payment as completed merely because a user clicked a button.

### G. Backend API integration

Coordinate a stable set of routes, including:

- `GET /health`
- `GET /api/v1/dashboard`
- `GET /api/v1/forecast`
- `POST /api/v1/scenarios`
- `POST /api/v1/rescue/analyze`
- `GET /api/v1/invoices`
- `POST /api/v1/invoices` or the agreed invoice creation route
- `POST /api/v1/invoices/{id}/send`
- `GET /api/v1/payments/{id}`
- `GET /api/v1/ledger`

Confirm route names and request/response schemas with the relevant module owners before implementation. The list is the target interface, not a claim that all routes already exist.

### H. Integration tests

- Test dashboard loading from the API.
- Test a forecast with a reserve breach.
- Test a forecast without a reserve breach.
- Test scenario submission and response rendering.
- Test rescue-agent fallback.
- Test invoice creation errors.
- Test pending and verified payment statuses.
- Test malformed API responses and network failures.
- Test the main workflow from forecast to recovery ledger.

### I. Git and coordination

- Maintain the shared integration branch.
- Review API contract changes with the affected members.
- Ensure pull requests contain a clear summary and test results.
- Avoid directly changing another member's module without coordination.
- Keep the main branch stable.
- Track blockers and integration dependencies.
- Ensure the whole team can run the project from the README.

### J. Deliverables

- Complete dashboard and frontend.
- API integration layer.
- Integration and end-to-end tests.
- Working local demo.
- Deployment configuration.
- Setup and troubleshooting documentation.
- Final demonstration script and public demo video, as required by the competition.

### Definition of Done

- Frontend starts reliably.
- All required screens use the agreed API contracts.
- Loading, empty, error, and retry states work.
- Financial values are formatted consistently.
- Projected and verified money are never confused.
- The full demo flow passes end-to-end testing.
- Another teammate can clone the repository and run the app using the documentation.

# 8. Shared API Contract Rules

All members must follow these rules.

1. Money is represented as integer cents in backend contracts.
2. Every monetary value has a currency.
3. Dates use ISO 8601 formatting.
4. Records have stable identifiers.
5. Optional fields and null values have documented meanings.
6. Errors use a consistent structure.
7. Every module documents its input and output.
8. Changes to shared contracts require review by affected members.
9. Demo fixtures must be labelled as demo data.
10. Provider-specific payment statuses are preserved when normalized.
11. AI estimates are never treated as verified payments.
12. API contracts are tested with fixtures or schema validation.

Example API error:

```json
{
  "error": {
    "code": "PAYMENT_STATUS_UNAVAILABLE",
    "message": "Payment status could not be verified.",
    "request_id": "req_demo_123"
  }
}
```

# 9. Git Workflow

## Branches

- `main`: stable, tested code.
- `integration`: shared development and integration.
- `feat/forecast-engine`: Member 1.
- `feat/ai-rescue-agent`: Member 2.
- `feat/paypal-ledger`: Member 3.
- `feat/frontend-integration`: Member 4.

## Rules

1. Each member works on their assigned feature branch.
2. Commit small, meaningful changes.
3. Pull or fetch updates before beginning new work.
4. Open a pull request into `integration`.
5. Run relevant tests before requesting review.
6. Review contract changes with affected owners.
7. Do not commit `.env`, credentials, access tokens, or real customer data.
8. Do not use force-push to overwrite shared history.
9. Merge into `main` only after the complete application passes the agreed release checks.

# 10. Testing Strategy

## Unit tests

Each module owner tests their own calculations, validation, error handling, and edge cases.

## Contract tests

Validate representative requests and responses against the agreed API schemas.

## Integration tests

Verify that the API layer correctly connects the frontend with the financial engine, rescue agent, payment service, and ledger.

## End-to-end tests

Verify the complete user journey:

1. Open the dashboard with seeded demo data.
2. Review the cash-flow forecast.
3. Identify a projected reserve breach.
4. Inspect the explanation and supporting evidence.
5. Run a what-if scenario.
6. Review a recommended recovery action.
7. Create or issue a Sandbox invoice.
8. Retrieve and verify the payment status.
9. Confirm that the ledger reflects the actual verified outcome.

## Security and reliability checks

- Confirm no secrets are tracked by Git.
- Validate inputs and error handling.
- Test provider outages and timeouts.
- Verify that duplicate operations do not create duplicate records.
- Confirm that AI cannot assert payment completion.
- Run a clean-clone installation test before release.

# 11. Delivery Milestones

## Milestone 1 — Foundation

- Repository and branch workflow established.
- Team ownership documented.
- Shared contracts agreed.
- Backend and frontend skeletons run locally.

## Milestone 2 — Independent modules

- Member 1 completes forecast calculations and tests.
- Member 2 completes structured rescue analysis and fallback.
- Member 3 completes Sandbox adapter and ledger.
- Member 4 establishes frontend screens and API client.

## Milestone 3 — First integration

- Forecast endpoint connected to the dashboard.
- Scenario endpoint connected to the scenario screen.
- Rescue analysis displayed with evidence.
- Payment operations connected to the ledger.

## Milestone 4 — End-to-end demo

- Complete demo workflow runs successfully.
- Integration and failure-path tests pass.
- Sandbox credentials and configuration are documented.

## Milestone 5 — Release preparation

- Feature freeze.
- Critical bug fixes.
- Clean-clone test.
- README and license reviewed.
- Deployment verified.
- Demo video recorded and checked.
- Submission materials reviewed before the official deadline.

# 12. Definition of Project Complete

The project is considered complete only when:

- The frontend and backend run from documented instructions.
- Forecast and scenario calculations pass tests.
- AI recommendations are validated and evidence-based.
- PayPal Sandbox operations work with test credentials.
- Payment completion is verified through the provider.
- The ledger separates projections from verified outcomes.
- The primary end-to-end workflow passes.
- Important errors and provider failures are handled.
- No secrets are committed.
- The public repository, license, README, deployment, and demo meet the competition requirements.

**Team principle:** Build the smallest reliable end-to-end application first. Add optional visual effects or advanced AI features only after the critical workflow is working and tested.