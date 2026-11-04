# Rescue module integration handoff

This guide describes the Member 2 callable interface and remaining joint checks.
It does not register a route or modify another member's code. The module's local
implementation, mocked-provider behavior and offline examples can be verified
independently. Shared contracts below must be reviewed by affected teammates.

## Public entry point

```python
from backend.app.rescue_ai.schemas import RescueAnalysisRequest
from backend.app.rescue_ai.service import analyze_rescue

async def analyze_for_api(payload: dict) -> dict:
    request = RescueAnalysisRequest.model_validate(payload)
    result = await analyze_rescue(request)
    return result.model_dump(mode="json")
```

This runs with no provider and no credentials. The existing service signature is:

```python
async def analyze_rescue(
    request: RescueAnalysisRequest,
    provider: RescueProvider | None = None,
    *,
    timeout_seconds: float = 15.0,
) -> RescueResponse:
    ...
```

Use await inside an existing FastAPI async route, not asyncio.run. The proposed
POST /api/v1/rescue/analyze route remains Member 4's responsibility. It is not
currently registered by this package. No API response is proof of payment.

## Request mapping

| Field | Meaning and responsibility |
| --- | --- |
| as_of_date | Explicit business analysis date, such as 2026-10-26; no hidden system clock |
| forecast_id | Stable evidence ID for this forecast snapshot |
| forecast | Currency, reserve, first breach date, daily balances and demo metadata |
| invoices | Relevant invoice evidence; defaults to an empty list |
| transactions | Relevant receipt/expense evidence; defaults to an empty list |

The integration lead should construct one coherent snapshot, enforce access to
that business's records, and preserve identifiers. IDs must be nonempty strings
without whitespace and unique across forecast, invoice and transaction evidence.
All monetary values are strict integer cents. Every evidence record uses the
forecast currency. Keep the MVP in USD until minor-unit rules are extended.
Dates are supplied as ISO calendar dates, not locale-specific display strings.

Forecast fields:

- currency: uppercase three-letter code; the schema checks shape, not membership.
- safety_reserve_cents: non-negative integer.
- first_reserve_breach_date: required date or null; null means no closing balance
  in the supplied snapshot is below the reserve, not that missing data is safe.
- days: zero to 30 daily records containing date, opening_balance_cents,
  receipts_cents, expenses_cents and closing_balance_cents.
- is_demo: defaults false; explicitly set true for sample data.
- disclaimer: optional explanatory text; not sent to the AI provider.

Days must be consecutive and ordered, carry forward correctly, and satisfy
closing = opening + receipts - expenses. Receipts and expenses are non-negative;
opening and closing cash may be negative. Do not append transaction evidence as
additional forecast cash. The module accepts Member 1's projections rather than
rebuilding that engine. If no eligible dates remain after as_of_date, risk is unknown.

Invoice fields:

- invoice_id, currency, outstanding_amount_cents, due_date, status.
- status is one of unpaid, pending, paid, cancelled.
- paid requires zero outstanding amount. This is a structural rule only; Member 3
  must establish authoritative verification before representing a payment as paid.
- Only positive, unpaid invoices with due_date earlier than as_of_date are proposed
  for follow-up. Pending is not completed and is not proposed for collection here.
- Partial payments need an agreed mapping to the remaining outstanding amount;
  do not pass the original total as outstanding. Preserve raw provider status in
  Member 3's ledger, which is outside this module.

Transaction fields:

- transaction_id, currency, amount_cents, date, direction, status, discretionary.
- direction: receipt or expense. status: projected, verified or cancelled.
- discretionary defaults false. Verified/cancelled events are excluded from expense
  change proposals. Marking an event verified does not independently verify it.
- The current contract lacks an explicit link from a transaction to a forecast
  event. Do not claim an individually attributed cause or incremental saving.

Other fields are rejected. Adapt richer database/provider records explicitly
rather than forwarding their entire dictionaries or customer contact details.

## Response mapping

Original shared example fields remain supported:

- summary: computed explanation, optionally supplemented by selected fixed text.
- risk_level: low, medium, high or unknown, based on the assessed daily balances.
- evidence_ids: supporting supplied snapshot/record identifiers.
- recommended_actions: action_id, title, estimated_impact_cents and assumptions.

Additional proposed fields for API/frontend review:

- Action: explanation, evidence_ids, currency, priority and requires_approval.
- Response: currency, assumptions, source and is_demo.
- estimated_impact_cents can be null when not calculable; do not render null as 0.
- Priorities start at 1; a smaller number is displayed earlier. They do not claim
  a mathematically optimal or guaranteed business outcome.
- Action IDs are follow_up:<invoice_id> or review_expense:<transaction_id>. Treat
  them as opaque identifiers. Use evidence_ids/your record lookup to navigate;
  avoid depending on ad hoc string splitting when IDs may themselves contain colons.
- source is deterministic or ai. ai means accepted constrained selections, not
  AI-calculated figures. The demo ai_selection case is simulated and separately labelled.

Show summary, evidence, action assumptions, response assumptions, demo labels and
estimated-impact uncertainty. Preserve approval flags and implement enforcement
in the external action workflow. These are proposals, never actual ledger recoveries.
Each amount must be displayed with its currency. Unknown risk is not a green/safe
state. Invoice potential impacts must not be summed into current cash or treated
as improvement to the forecast without Member 1's scenario/reconciliation logic.

## Optional provider configuration

No provider is created unless the caller supplies one. No .env file is read by
this module. The adapter reads process environment only when from_env is called.
Arrange credentials outside version control under the team's approved setup.

| Variable | Meaning |
| --- | --- |
| AI_BASE_URL | Full HTTPS API base; adapter appends /chat/completions |
| AI_MODEL | Model identifier accepted by the chosen endpoint |
| AI_API_KEY | Secret credential; never include in demo JSON, frontend or logs |
| AI_TIMEOUT_SECONDS | Optional adapter deadline, default 15 seconds, maximum 60 |

The endpoint must support the JSON chat-completions protocol used in provider.py,
including response_format json_object and the configured token-limit parameter.
This is not a universal adapter: native provider APIs with another protocol need
a separate RescueProvider implementation. No particular live endpoint or model
has been verified. A request may incur usage costs and sends candidate metadata
outside the local machine; external calls are not part of local verification.

After authorization for external calls, an integration owner may configure the
adapter explicitly. This setup snippet itself makes no network request:

```python
from backend.app.rescue_ai.provider import ChatCompletionsProvider, ProviderError

try:
    configured_provider = ChatCompletionsProvider.from_env()
except ProviderError:
    configured_provider = None  # caller can record a sanitized configuration event
```

Pass configured_provider to analyze_rescue. Use a separately validated service
timeout_seconds value in (0, 60]; its default is 15 seconds. A longer adapter
setting does not override the service's shorter deadline. Construction errors
occur before analyze_rescue and must be handled by the caller as above.

HTTP behavior: no redirects or automatic retries; 429, authentication/server
failures, connection errors and malformed bodies become sanitized ProviderError
codes. Input context is limited to 200 candidates and 64000 encoded bytes; output
to 128000 bytes. The adapter sends risk, demo flag, allowed codes and candidate
IDs/kinds/impact/currency/priority. Names, emails, notes and full financial records
are excluded, but IDs themselves may be business information. Use opaque IDs.
HTTPX trust_env is false, so environment proxy configuration is not inherited.

Service fallback covers provider failures and rejected/failed output assembly.
It preserves trusted facts and adds a generic notice. Input validation and invalid
service-timeout configuration are not disguised as provider outages. Cancellation
propagates. Deadlines require cooperative async providers; blocking code cannot
be forcibly interrupted. Avoid logging raw provider exception text or bodies.

## Error mapping and compatibility

Member 4 must map Pydantic ValidationError to the application's agreed error shape
and handle server configuration errors separately. Do not add an alternative
unversioned error format in the UI. Provider outages normally return a valid
RescueResponse with source deterministic and an explanatory assumption.

Python 3.11+, Pydantic v2 and HTTPX are runtime dependencies. pytest is needed only
for tests. No new dependency was installed by this handoff. The root README,
shared requirements, .env.example, API schemas, routes and contracts were not edited.
Confirm the additional metadata and null-impact meaning before using a strict
shared API response model that might drop or reject those fields.

## Example data and local acceptance

example_data.json contains each request and its actual expected response. Extract
a record's request field before passing it to RescueAnalysisRequest; the outer
scenario/provider_mode wrapper is demonstration metadata, not the API contract.

The example runner and test command are in README.md. A paid_invoice example
shows that changing invoice status alone does not increase opening cash. A test
supplies a separately refreshed forecast after a fictional verified receipt and
checks the changed risk. This tests the module contract, not PayPal verification.

## Joint checklist

Member 1:
- [ ] Map real forecast output to ForecastEvidence and provide a snapshot ID.
- [ ] Confirm horizon, dates, reserve policy and receipt assumptions.
- [ ] Verify no double counting after a payment and use the scenario engine for timing.

Member 3:
- [ ] Agree invoice status and partial-payment mappings; preserve authoritative status.
- [ ] Supply outstanding balances and stable IDs from accessible business records.
- [ ] Keep proposed actions separate from pending/verified ledger outcomes.
- [ ] Verify payment independently before refreshing cash/forecast records.

Member 4:
- [ ] Build one coherent request and await analyze_rescue inside the API layer.
- [ ] Register the agreed route and error mapping; do not discard added metadata.
- [ ] Show uncertainty, demo state, evidence and approval controls in the UI.
- [ ] Configure an optional compatible provider and sanitized operational reporting.
- [ ] Run actual API/frontend integration tests in addition to the isolated suite.

Whole team:
- [ ] Test shortage, safe/boundary, missing/stale data and provider outage in the app.
- [ ] Test forecast -> recommendation -> approval -> sandbox action -> verified
      payment -> refreshed forecast -> new rescue analysis.
- [ ] Separate simulated demonstrations from any claimed live AI/PayPal result.
- [ ] Record agreed dependencies and setup instructions in shared files through
      their owners; those files remain untouched by this module handoff.

Completion of this local package does not check these boxes automatically.
