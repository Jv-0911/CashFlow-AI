# CashFlow AI rescue module

Member 2's module explains supplied cash-flow forecasts and returns proposed
recovery actions. It works without an AI connection. An optional provider may
select supported explanation points and reorder existing actions; Python retains
control of financial facts, evidence and approval requirements.

This package is a local handoff, not a claim that the shared API, frontend,
PayPal workflow or a live model has been integrated. See [INTEGRATION.md](INTEGRATION.md).

## Files and responsibilities

| File | Responsibility |
| --- | --- |
| schemas.py | Validate request, forecast, invoice, transaction and response data |
| fallback.py | Diagnose reserve risk and build deterministic action candidates |
| provider.py | Optional compatible HTTP adapter and constrained AI decision validation |
| service.py | Public async entry point; protect trusted facts and handle provider failure |
| examples.py | Offline command-line demonstrations with fixed fictional records |
| example_data.json | Eight saved request/response examples produced by the runner |
| INTEGRATION.md | Input/output contract, configuration and teammate handoff checklist |
| ../../tests/rescue_ai/ | Schema, fallback, provider, service and example tests |

Existing __init__.py remains unchanged. Import the public function directly from
backend.app.rescue_ai.service rather than relying on package-level exports.

## Run locally

Run commands in PowerShell from the CashFlow-AI repository root, not from this
module's folder. Use the existing virtual environment; no activation is required.

```powershell
& ".\backend\.venv-win\Scripts\python.exe" -B -m backend.app.rescue_ai.examples --scenario shortage --pretty
```

Run all eight demos:

```powershell
& ".\backend\.venv-win\Scripts\python.exe" -B -m backend.app.rescue_ai.examples --scenario all --pretty
```

Run the isolated rescue suite without shared conftest files or cache writes:

```powershell
& ".\backend\.venv-win\Scripts\python.exe" -B -m pytest backend/tests/rescue_ai --noconftest -p no:cacheprovider -q
```

The -B option disables Python bytecode writes. Tests do not install dependencies,
change source data, contact providers, or require a running API server. The runner
prints JSON to the terminal and does not save files. Tests use local fixtures,
fake providers and HTTPX MockTransport. The shared backend conftest is intentionally
excluded; these results do not verify the rest of the team application.

Runtime requirements are Python 3.11 or newer (asyncio.timeout), Pydantic v2 and
HTTPX. Tests additionally require pytest. The existing local environment was
verified with Python 3.14.2, Pydantic 2.14.1, HTTPX 0.28.1 and pytest 9.1.1.
No shared dependency file was created or changed. Ask the integration lead to
record agreed dependency versions in the shared project configuration.

If the environment executable is missing, use the team's documented setup.
If imports fail, check that the terminal is in the repository root. Do not copy
or recreate teammate modules inside rescue_ai to resolve an import problem.

## Business example

A fictional business has USD 1,200 in available cash, expects USD 200 tomorrow,
and owes USD 800 in wages tomorrow. A separate USD 800 customer invoice is overdue.
The owner wants a USD 1,000 safety reserve.

```text
Projected closing balance = 1,200 + 200 - 800 = USD 600
Reserve gap               = 1,000 - 600       = USD 400
```

The supplied forecast therefore indicates a reserve risk. It does not say the
business has zero cash or cannot cover wages under those assumptions. The
uncertain overdue invoice is not automatically counted as received cash.

The shortage demo returns high risk, a summary including USD 400.00 below the
reserve, a proposal to review the overdue invoice, and a proposal to review the
upcoming expense. Invoice collection is estimated at its outstanding USD 800,
not a guaranteed improvement to the forecast. Expense impact is null because
there is no scenario-engine calculation. Every action requires approval.

Reviewing wages is not permission to delay them. No reminder is sent, invoice
issued, wage paid, status changed or cash credited by this module. An invoice
collected after the shortage date may not prevent that earlier shortage.

## Demo scenarios

Dates are fixed at October 26-28, 2026, so the examples remain reproducible even
when run later. All inputs and outputs carry demo flags.

| Scenario | Expected result |
| --- | --- |
| shortage | USD 600 closing cash, USD 400 reserve gap, high risk, two proposals |
| safe | USD 1,800 closing cash, low risk, no proposals |
| reserve_boundary | USD 1,000 closing cash, medium risk, no margin above reserve |
| insufficient_evidence | No daily forecast; unknown risk and no proposals |
| stale | Only past forecast data; unknown risk and no proposals |
| paid_invoice | Paid invoice excluded from follow-up; supplied forecast remains unchanged |
| provider_failure | A simulated provider fails; deterministic result with generic notice |
| ai_selection | Simulated selections reorder actions and append supported sentences |

ai_selection does not call a model. Its outer provider_mode is simulated_selection,
and its response assumptions explicitly state that no AI model was called. Its
source field is ai because it exercises that service branch; show the simulation
label whenever presenting it. The reverse ordering demonstrates behavior, not a
claim that expense review is always more important than invoice follow-up.

## Code flow and manual learning guide

1. Construct a RescueAnalysisRequest from a dictionary. Pydantic checks required
   fields, strict integer cents, date parsing and cross-record consistency.
2. Call analyze_rescue. It builds the fallback before attempting AI. Invalid input
   is not hidden by a provider failure handler.
3. analyze_fallback examines supplied closing balances on/after as_of_date. It
   determines the lowest balance and reserve gap without inventing receipts.
4. Eligible overdue invoices and projected expenses become proposals with stable
   IDs, evidence, assumptions and approval flags.
5. With no provider, the service returns that result immediately. With unknown
   risk, it skips the provider even if one was supplied.
6. Otherwise it records the allowed selections and gives the provider a deep copy
   of the baseline under a cooperative async timeout.
7. The returned decision is validated and independently checked during assembly.
   All original actions must occur exactly once. Only supported explanation codes
   can become fixed, code-owned sentences.
8. The output copies original amounts, evidence and approval flags. Only action
   order/priority, selected explanation sentences and source metadata change.
9. Provider, decision or assembly failures return the trusted baseline with a
   generic notice. Caller cancellation propagates instead of being swallowed.

To recreate the core design yourself, implement the reserve-gap calculation first,
then invoice filtering, then sorting. Test those without AI before introducing a
provider interface. Finally write the orchestration branches: absent provider,
valid selection, rejected selection and provider failure. Keep each branch small.

## Calculation and ranking assumptions

Risk is high below the reserve, medium exactly at it, low above it, and unknown
when there are no current/future forecast days. These are application rules, not
statistical risk probabilities. Analysis covers only dates supplied in the snapshot.

The input supports at most 30 consecutive ordered forecast days. Each day's
arithmetic and carry-forward balance must be consistent. The supplied first
breach date must match the whole snapshot, including historical days; analysis
then considers only days on/after as_of_date. Money already received must already
be represented appropriately by the caller's forecast.

Invoice candidates must be unpaid, positive in outstanding amount and strictly
overdue relative to as_of_date. Pending, paid and cancelled invoices are excluded.
The baseline orders invoices by contribution to the reserve gap, overdue age,
outstanding amount and ID. At an exact reserve boundary the gap is zero, so age,
amount and ID break ties.

Projected positive expenses between as_of_date and the first assessed breach
(or lowest day when there is no breach) can be reviewed. Discretionary expenses
sort first, followed by date, amount descending and ID. In the deterministic
baseline, invoice proposals precede expense proposals. AI may change this order;
that order is not an optimization guarantee or authorization to act.

## Limits and data handling

- No bank connection, payment execution, reminder sending, accounting posting,
  authentication, database persistence, free-form chatbot or scenario engine is
  implemented here. API/frontend/payment integration belongs to teammates.
- Evidence IDs make statements traceable, but do not prove payment authenticity.
  The caller must supply authoritative records and enforce business access rights.
- The models reject duplicate request evidence IDs and mismatched currencies.
  Transaction records are context, never extra cash added to a forecast.
- Currency validation checks three uppercase letters, not ISO membership. The MVP
  examples use USD. Display assumes 100 cents per unit; currencies with different
  minor units and exchange conversions require an agreed extension.
- Forecast aggregates support the numerical explanation. Transactions are not
  linked to specific forecast events, so individual causes or incremental recovery
  effects cannot be established from the current contract alone.
- The AI uses constrained codes and action IDs, not free-form financial prose.
  Customer behavior, payment timing and successful recovery are not predicted.
- All generated actions carry uncertainty and require human approval. External
  enforcement of approval belongs to the API/payment workflow.
- The module does not log provider error bodies. Operational metrics and safe
  application-level logging are left to the integration layer.

## Current verification and remaining integration

The local demos and tests do not use a live AI model or PayPal. An optional live
provider check is external work and has not been performed under the local-only
instruction. Do not present a simulated selection as a live AI result.

Member 1's real output mapping, Member 3's verified invoice states, Member 4's API
route/frontend, and the complete payment/reforecast journey still need joint
verification. Follow INTEGRATION.md before declaring the complete product done.
