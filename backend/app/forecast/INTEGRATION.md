# Financial Engine integration handoff

This module supplies Python services and validated Pydantic contracts. It does not
verify bank or PayPal records, implement authentication, execute payments, or
install FastAPI routes. JV's existing `/api/v1/forecast` and
`/api/v1/forecast/demo` still return their labelled fixtures until JV wires the
engine. All monetary inputs and authoritative balances use integer cents.

## JV: application calls and responses

Resolve `business_id` from the authenticated business context; authorize every
forecast, scenario, monitoring, model and retraining operation against that
context. An identifier supplied in a request is not authorization. Configure
registry and monitoring paths in backend code, outside customer-upload storage;
never accept a storage path from the frontend.

| Task | Call | Validated contract / result |
|---|---|---|
| Parse and aggregate CSV | `prepare_history(PreparationRequest(...))` | `PreparedHistory.source` retains transactions/raw fields; `.history` contains daily cents |
| Compare forecasting methods | `forecast_baselines(history, horizon_days=..., ml_config=...)` | `ForecastResult`; optional ML configuration enables eligible candidates |
| Train reusable models | `train_forecast_model(history, business_id=..., model_version=..., trained_at=..., horizon_days=..., config=..., ml_config=...)` | `TrainedForecastModel` with Pydantic `ModelMetadata` and retained estimators |
| Infer without training | `forecast_trained_model(model, history=..., horizon_days=..., as_of=...)` | `ForecastResult`; history must preserve the trained prefix |
| Produce financial projections | `forecast_cash_flow(CashForecastRequest(...), trained_model=optional_model)` | `CashForecastResult` |
| Issue a business-scoped snapshot | `issue_forecast(ForecastIssueRequest(...), trained_model=optional_model)` | `IssuedCashForecast`, including business, UTC issuance timestamp and direction model versions |
| Compare a hypothetical change | `simulate_scenario(financial_request, ScenarioRequest(...), baseline=issued.forecast)` | `ScenarioComparison`; supplying baseline avoids another training operation |
| Record and evaluate accuracy | `monitor.record_forecast(issued)`, `monitor.record_actual(actual)`, `monitor.evaluate(business_id, config=...)` | `MonitoringReport`, errors, missing actuals and deterioration evidence |
| Save / load models | `registry.save_candidate(model)`, `registry.load(business_id, version, expected_currency=...)` | Immutable version and validated trusted model |
| Evaluate retraining / promotion | `retrain_model(registry, RetrainingRequest(...), monitoring=optional_report)` | `RetrainingDecision`; previous active model is retained when guards fail |

The package exports these operations. Their defining files are `interfaces.py`,
`financial_schemas.py`, `scenario_schemas.py`, `trained.py`, `persistence.py`,
`monitoring.py`, `monitoring_schemas.py`, and `retraining_schemas.py`.
Persist and return the complete `IssuedCashForecast`: its `issuance_id`,
`business_id`, `generated_at`, direction-specific model versions and nested
`forecast.forecast_id` associate later actuals with the original prediction.
When a trained artifact is supplied, `forecast.model_artifact_id` and
`forecast.model_version` identify that exact artifact; direction versions are
null where statistical predictions were suppressed. Forecasts computed without a
saved artifact retain null artifact/version fields; do not invent a deployed
version for them. Reusing an issuance ID requires identical stored content.
`reconcile_history` is the preparation boundary for reusable **residual** models:
train on its returned history when the financial request excludes scheduled
categories. A model trained on gross history cannot be reused as a residual model.
Training and retraining must preserve the same cash-target basis and immutable
historical prefix; changing category coverage can require a separately trained
version rather than appending incompatible targets.

Use strict request schemas as FastAPI body types and response schemas as
`response_model`. Pydantic errors should produce field-specific 422 responses.
Map service `ValueError`/`IngestionError` into a documented validation response
without exposing raw financial records; distinguish unavailable/corrupt service
artifacts from bad customer inputs. Perform bounded training/retraining outside
the event-loop thread. CSV requests have an enforced byte limit; apply HTTP
upload limits before reading the whole body and retain authorized uploads only.

Preserve the full issued response, including warnings, assumptions,
reconciliation, uncertainty and evidence. A compatibility adapter for the current
shared `ForecastDay` maps:

| Existing API field | Financial result field |
|---|---|
| `date` | `day.date.isoformat()` |
| `opening_balance_cents` | `day.opening_balance_cents` |
| `receipts_cents` | `day.projected_receipts_cents` |
| `expenses_cents` | `day.projected_payments_cents` |
| `closing_balance_cents` | `day.projected_closing_balance_cents` |

That older response lacks the new warnings/evidence contract; JV must approve an
extension or expose a separate full response. Its default `is_demo=True` and
fixture disclaimer must be set explicitly by the adapter. Real uploaded business
forecasts remain estimates even when `is_demo=False`; synthetic examples remain
labelled demo. This module has not changed the shared contract or those defaults.

Python cents can exceed JavaScript's exact `Number` range (`2**53 - 1`). JV must
parse oversized integers losslessly before any `Number` conversion, or agree an
adapter transport using decimal strings and `BigInt`. A normal `JSON.parse`
followed by `BigInt` conversion cannot recover cents already rounded. If the
frontend supports only `Number`, reject out-of-range amounts explicitly rather
than silently rounding. Keep this transport decision coordinated with the shared
API schema; the engine's authoritative financial values remain integers.

### Dates and evidence

`generated_at`, `trained_at`, `observed_at` and retraining `now` are aware **UTC**
timestamps. Transaction/event dates are strict `YYYY-MM-DD` business-calendar
dates. Convert provider timestamps to the configured IANA `business_timezone`
before aggregation. The opening cash date equals `forecast_start_date` and means
verified cash immediately before that day's movements. Complete history includes
confirmed zero-activity days; absence of records alone does not prove a zero.
Do not issue a forecast before its historical information was available.

Requested horizons are 1–30 days; selected models retain a configured maximum,
and validated horizons/reliability must be surfaced. Returned days do not by
themselves prove reliable predictions for every lead. Short history, gaps,
unverified receipts, unresolved category overlap and missing annual seasons must
remain visible in the UI.

### Minimal service example

This uses synthetic data. The caller supplies the business identity, times,
opening evidence and category-coverage attestation.

```python
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from backend.app.forecast import (
    CashForecastRequest, ForecastIssueRequest, PreparationRequest,
    VerifiedOpeningBalance, LocalForecastMonitor, LocalModelRegistry,
    MoveEventOperation, ScenarioRequest, issue_forecast, prepare_history,
    simulate_scenario, train_forecast_model,
)
from backend.app.forecast.financial_schemas import (
    CategoryScheduleCoverage, ScheduledCashEvent,
)
from backend.app.forecast.reconciliation import reconcile_history

start = date(2026, 10, 13)
rows = ["transaction_id,date,amount_cents,direction,currency,category,payment_status"]
for offset in range(42):
    day = start - timedelta(days=42 - offset)
    rows.extend([
        f"sale_{offset},{day},100,inflow,USD,sales,settled",
        f"expense_{offset},{day},20,outflow,USD,operations,settled",
        f"supplier_{offset},{day},30,outflow,USD,suppliers,settled",
    ])
prepared = prepare_history(PreparationRequest(
    csv_data="\n".join(rows), coverage_start=start - timedelta(days=42),
    coverage_end=start - timedelta(days=1), complete_coverage=True,
))
financial = CashForecastRequest(
    history=prepared.history, historical_transactions=prepared.source,
    opening_balance=VerifiedOpeningBalance(balance_cents=1000, currency="USD",
        balance_date=start, evidence_id="synthetic-bank-snapshot"),
    forecast_start_date=start, forecast_horizon_days=2, safety_reserve_cents=800,
    known_events=(ScheduledCashEvent(event_id="bill", source_id="supplier-bill",
        direction="outflow", amount_cents=1400, currency="USD",
        status="scheduled_expense", category="suppliers",
        expected_date=start + timedelta(days=1)),),
    category_coverage=(CategoryScheduleCoverage(category="suppliers", direction="outflow",
        evidence_id="synthetic-full-supplier-schedule", complete_for_forecast_window=True),),
)
residual, _ = reconcile_history(financial)
trained_at = datetime(2026, 10, 13, tzinfo=timezone.utc)
model = train_forecast_model(residual, business_id="synthetic-shop", model_version="v1",
    trained_at=trained_at, horizon_days=2)
registry = LocalModelRegistry(Path("service-state/models"))  # Configure trusted absolute roots in deployment.
registry.save_candidate(model)  # Does not promote or replace an active model.
loaded = registry.load("synthetic-shop", "v1", expected_currency="USD")
issued = issue_forecast(ForecastIssueRequest(issuance_id="issue-001",
    business_id="synthetic-shop", generated_at=trained_at, financial=financial),
    trained_model=loaded)
monitor = LocalForecastMonitor(Path("service-state/monitoring"))
monitor.record_forecast(issued)
comparison = simulate_scenario(financial, ScenarioRequest(scenario_id="defer-bill",
    operations=(MoveEventOperation(operation_id="move-bill", event_id="bill",
        expected_date=start + timedelta(days=3),
        assumption="Assume supplier approval of the new payment date."),)),
    baseline=issued.forecast)
print(issued.model_dump_json())
print(comparison.model_dump_json())
```

The baseline's final cash is `-240` cents with a `1040`-cent shortfall. The
scenario's final cash is `1160` cents: the bill remains in the scenario event
record on October 16, outside this two-day window. Deferral is an assumption,
not a completed financial action. Use a new immutable model version and issuance
ID for different saved content; retry identical issuance content idempotently.

A scenario request JSON accepted by `ScenarioRequest.model_validate(...)` is:

```json
{
  "scenario_id": "defer-bill",
  "operations": [{
    "operation": "move_event",
    "operation_id": "move-bill",
    "event_id": "bill",
    "expected_date": "2026-10-16",
    "assumption": "Assume supplier approval of the new payment date."
  }]
}
```

Other operations are `change_expense_amount`, `change_projection`, `add_event`
and `remove_event`. Each operation needs an ID and explicit assumption. One
event may change once per scenario; a directional daily projection may change
once. Added events require literal `hypothetical: true` and distinct event/source
identities. Existing modifications require a baseline-included future event with
no historical/verification identity. Moving cash beyond the horizon retains the
event and warns about zero contribution in this window. Historical records and
payment statuses are never modified. Do not record scenario projections as issued
accuracy forecasts or send scenario outputs to payment APIs.

## Hem: evidence for explanations

Read `forecast.shortage_evidence` for breach-day IDs, verified opening evidence,
closing cash, reserve shortfall and cumulative `known_event_effects`. Each effect
references `event_id`, `source_id`, original status and expected date, with signed
cash impact and closing cash if that event alone were omitted. These are
arithmetic comparisons while other estimates are held fixed, not causal findings;
individual shortfall effects are not additive. Use `reconciliation.event_dispositions`
to explain included, excluded or unresolved events. Use the scenario comparison's
changed events/projections and explicit assumptions to discuss hypothetical recovery.

Residual forecasts are estimates; known expected receipts are also conditional
when unpaid/pending. Empirical uncertainty envelopes use held-out errors and
complete historical paths; they are not calibrated confidence percentages, omit
uncertain payment timing and may be null. Scenario envelopes shift the original
errors conditional on assumed changes. Do not invent amounts, collection dates,
provider verification, probabilities, confidence percentages, causal causes or
actions that supposedly occurred. Keep original warnings and evidence references
in explanations.

## Vedant: ledger and status boundary

Map provider statuses into the following local contract using verified ledger
evidence. The engine performs no provider-status mapping itself.

| Local event status | Future cash behavior |
|---|---|
| `verified_completed` | Excluded; requires `verification_evidence_id` |
| `cancelled`, `failed` | Excluded; never treated as future paid cash |
| `invoice_unpaid`, `overdue_receivable` | Inflow only; needs explicit expected date and collection assumption |
| `pending_verification` | Conditional future cash only with expected date and assumption |
| `scheduled_expense` | Outflow only; supplied expected payment date, never proof of actual payment |

Do not infer a collection date from `due_date`. Use stable event/source IDs;
duplicate source IDs or historical links are rejected. Once verified actual cash
is settled, append it to historical records with a stable transaction ID and link
the corresponding event via `historical_transaction_id` where identities differ.
Already represented settled cash is excluded from future additions. Keep failed,
cancelled and pending statuses distinct. CSV records lacking status use the
documented settled assumption and warning; this is not provider verification.

Residual reconciliation requires categorized historical transactions reproducing
the supplied daily totals and an explicit complete category schedule for the
entire forecast window, including intentional zeros. This is stronger than a
list of selected invoices. If completeness is unproven, the affected direction
uses a labelled known-events-only fallback; omitted activity can change cash
risk. Do not describe it as a guaranteed lower or upper cash bound. Cancelling one
event does not automatically rewrite historical statistical patterns.

Supply complete verified daily gross actuals after the business day has ended:

```json
{
  "business_id": "synthetic-shop",
  "observation_id": "actual-2026-10-13",
  "currency": "USD",
  "date": "2026-10-13",
  "inflow_cents": 100,
  "outflow_cents": 20,
  "verified": true,
  "complete": true,
  "verification_evidence_id": "synthetic-settlement-evidence",
  "observed_at": "2026-10-14T00:01:00Z"
}
```

Parse this as `ActualObservation`, call `monitor.record_actual(actual)`, then
`monitor.evaluate(business_id)`. Incomplete/unverified records cannot enter the
accuracy ledger. Replaying identical observation IDs is idempotent; conflicting
IDs or a second actual for the same business day are rejected. Corrections need
a separate application contract. Errors compare issued gross predictions to
verified gross actuals by date, direction and horizon. Residual-category validation
MAE is not a comparable gross reference, so deterioration-reference evidence is
explicitly unavailable for those predictions even when gross accuracy is measurable.

## Trusted models and controlled retraining

The local model registry is a **POSIX** trusted filesystem service. It stores
immutable per-business versions, candidate/active/previous status and retraining
decisions, with atomic JSON updates and cooperating-process locks. Exact Python
and dependency versions, feature schema, business, currency and checksums must
match before trusted joblib loading. Checksums detect corruption; they do not
make attacker-produced pickle safe. Never load customer model uploads. Keep
registry roots service-owned and free of symlinks; application authorization,
storage access control and backups remain integration responsibilities.
Limits are 128 MiB per serialized model, 2 MiB per registry JSON file (including
decision history), and 16 MiB per business monitoring snapshot. The monitor is a
bounded local ledger, not an indefinite history database; its size-limit errors
require authorized archival outside this monitor. Neither store accepts an
arbitrary client path. Both use POSIX filesystem locking and require trusted
service-owned roots; they are not portable Windows storage backends.

`save_candidate` does not deploy a model. `retrain_model` is the scientific
promotion boundary; avoid exposing bare `registry.promote` as a customer action.
`registry.rollback(business_id)` validates and activates the most recent previous
version; authorize it as a backend administration action.

For retraining, construct `RetrainingRequest` with a new `decision_id` and
`candidate_version`, the business's same-basis complete history, explicit
`verified=True`, verification evidence, UTC `now`, requested horizon and optional
`RetrainingPolicy`, `BaselineConfig` and `MLConfig`. Call synchronously or from
JV's chosen bounded application execution mechanism; no cron/queue is installed.
Updated history must append to the active model's exact original daily prefix;
historical replacement/corrections are rejected. With an active model,
`horizon_days` must equal its configured horizon. A horizon change needs a
separately reviewed model rather than this incumbent-comparison operation.
Default triggers include 14 new verified observations, 30-day training age,
changed configuration and sustained comparable deterioration. A trigger permits
evaluation, not automatic promotion.

The operation reserves 3–6 fresh disjoint chronological final windows, trains and
selects a fixed candidate using data ending before their target outcomes, and compares that frozen candidate,
frozen incumbent and baselines on the same history prefixes. It checks paired
error improvement, per-lead errors, bias and stability. Consumed final outcomes
are recorded and are not reused by later decisions. A promoted model is the exact
pre-holdout artifact; it is not refitted on final outcomes. Insufficient evidence,
worse candidates and failed training retain the active version. Surface the
decision's status, triggers, reason and directional evidence; do not replace it
with a claim that more data always improves prediction.

Optional business fields remain in raw ingestion records. `KnownAheadCovariate`
validates business, date, finite value, known-at UTC time and evidence, and
`covariate_diagnostics` reports them as retained **unsupported model inputs**.
Current models do not consume arbitrary user covariates, infer business categories,
fetch holidays or invent external seasonality. Any future adapter must enforce
known-at semantics separately at every backtest origin before claiming support.
