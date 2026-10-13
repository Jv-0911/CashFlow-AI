# Financial Forecasting Engine — Phases 1–5

This package validates historical CSV exports, aggregates settled cash activity,
and calculates balances from supplied daily cash flows. Phase 2 adds historical
baseline predictions and chronological evaluation. Phase 3 adds opt-in ML comparison.
Phase 4 adds explicit scheduled-event reconciliation, conditional daily cash projections,
shortage evidence, and approximate empirical uncertainty ranges. Phase 5 adds deterministic
scenarios, trusted local model persistence, forecast-versus-actual monitoring, controlled
retraining, and business-scoped issuance contracts. Provider verification and calibrated
coverage guarantees remain application responsibilities or documented limitations.
The demo fixture under `backend/tests/forecast/fixtures/` is synthetic data.
Public operations and teammate-specific wiring are documented in [INTEGRATION.md](INTEGRATION.md).

## Local setup

Python 3.11+; from the repository root:

```sh
python3 -m venv .venv
./.venv/bin/pip install -r backend/app/forecast/requirements-dev.txt
./.venv/bin/python -m pytest backend/tests/forecast -q
./.venv/bin/python -m pytest backend/tests -q
```

Phase 1/2 use Pydantic 2 and standard-library processing. Phase 3 additionally uses
NumPy and scikit-learn (including its threadpoolctl dependency). Phase 5 explicitly
declares joblib for trusted local persistence; file locking requires POSIX. Shared dependency
declarations need JV's review. pandas is unnecessary for this daily-history contract.

## CSV contract

UTF-8 (optional BOM), comma-separated with a header. Required columns:
`date`, `amount_cents`, `direction`, `currency`. Currency may instead be an explicit
`currency=` import argument. Optional columns: `transaction_id`, `category`,
`description`, `payment_status`, and any business-specific covariates.
Imports default to a 5 MiB UTF-8 byte limit. `ingest_csv`, `read_csv`, and
`PreparationRequest.max_bytes` accept an explicit positive integer limit; the backend
must enforce its own upload limit before reading an HTTP request into memory.

```csv
transaction_id,date,amount_cents,direction,currency,category,payment_status
demo_1,2026-10-10,1234,inflow,USD,sales,settled
```

Header case and spaces are normalized. Supported aliases:

| Canonical | Alternatives |
| --- | --- |
| date | transaction_date, posted_date |
| transaction_id | id, txn_id |
| amount_cents | cents |
| amount | transaction_amount |
| direction | transaction_type, type |
| currency | currency_code |
| description | memo |
| payment_status | status |

`amount` replaces `amount_cents` and denotes major currency units with at most
two decimal places, converted exactly to cents. Both columns together are rejected.
Amounts must be nonnegative; direction explicitly specifies inflow/outflow.
No rounding, signed-amount inference, thousands separators, scientific notation,
or monetary imputation occurs. Zero and unusually large amounts are allowed.
Directions accept income/receipt/credit and expense/payment/debit respectively.
Dates must be real `YYYY-MM-DD` dates; timestamps and ambiguous local formats
are rejected. A future adapter can normalize these using an explicit convention.

Supported currencies: USD, EUR, GBP, CAD, AUD, INR, SGD, NZD, CHF, HKD, CNY.
All have two decimal places. Unsupported currencies, empty currency cells,
and mixed currencies are rejected; no conversion occurs.

Status aliases paid/completed/received map to settled; unverified and
pending_verification map to pending. Failed and cancelled records are retained
but excluded from actual cash aggregation, as are pending records. If the status
column is absent, the historical export is assumed settled with an explicit warning.
This classification reflects the CSV source and is never PayPal verification.
Blank or unknown values in a supplied status column are errors.

## Validation, duplicates, and provenance

Imports are atomic: any invalid record rejects the entire import through
`IngestionError.issues`, including CSV record numbers (header is record 1).
Blank records are skipped with warnings. Duplicate headers/aliases, malformed CSV,
and mismatched row widths are rejected. No rows are dropped as statistical outliers.

Matching explicit IDs are counted once with warnings; conflicting IDs reject the
import. Optional covariate differences count as conflicts. Missing IDs are generated
from the source SHA-256 and record number, reproducible for an identical file.
They are not stable across edited exports. Identical records without IDs are
ambiguous and reject the import; distinct legitimate transactions need distinct IDs.
This importer handles one export, not cross-upload reconciliation.

`read_csv` never changes the original file. Retain it outside Git. Results include
the source checksum, original column values, record numbers, normalized transactions,
and warnings. Retaining the source plus these rules makes cleaning reproducible.
Unknown columns and covariates are preserved, not selected or used as features yet.
Do not commit actual customer exports or diagnostics containing customer information.

## Daily aggregation and balances

```python
from datetime import date
from backend.app.forecast import read_csv, aggregate_daily, calculate_balances

data = read_csv("backend/tests/forecast/fixtures/demo_history.csv")
history = aggregate_daily(
    data, coverage_start=date(2026, 10, 10), coverage_end=date(2026, 10, 12),
    complete_coverage=True,
)
result = calculate_balances(
    history.days, start_date=date(2026, 10, 10), horizon_days=3,
    opening_balance_cents=1000, safety_reserve_cents=500, currency="USD",
)
print(result.model_dump_json(indent=2))
```

Without explicit complete export coverage, aggregation returns observed settled
dates only and warns that missing days are unknown. Confirmed coverage fills missing
dates with zeros, including entirely empty settled activity. Transactions outside
the coverage are errors. Completeness must come from the source, not the model.

The opening balance is cash immediately before `start_date`. Closing cash equals
opening cash plus receipts minus expenses; the next day's opening is that closing.
A breach is strictly below the reserve; equality is safe. Daily shortfall equals
`max(0, reserve - closing)`. Negative balances are allowed; reserves are nonnegative.
The calculation window is 1–30 days. Omitted days have zero **supplied** activity,
explicitly documented in the result. This does not assert that actual activity is zero.
Duplicate daily dates or evidence IDs, mismatched currencies, and out-of-window
cash rows are rejected. Supplied objects are not mutated. Money rejects floats,
strings, and booleans at the calculation boundary.

## Phase 1 calculation boundary

Internal schemas remain separate from JV's API schemas; no existing route or
shared contract changes in Phase 1. Daily totals expose evidence IDs for later rescue
explanations. Results explicitly identify deterministic calculation and uncertainty
as `not_estimated`. JV should review an API adapter and input transport before wiring
this module into `/api/v1/forecast`; that endpoint currently serves demo data.

Only one already-reconciled daily activity stream enters the calculator. Phase 1
does not combine ML estimates with invoices or scheduled obligations. That future
combination needs an explicit residual-activity policy to prevent double-counting;
duplicate-ID checks alone cannot establish semantic reconciliation.

## Phase 2 baseline forecasting

```python
from datetime import date, timedelta
from backend.app.forecast import BaselineConfig, DailyCash, DailyHistory, forecast_baselines

# SYNTHETIC DEMO: weekday receipts 1,000 cents, weekend receipts 5,000 cents.
start = date(2026, 9, 7)
days = tuple(DailyCash(
    date=start + timedelta(days=i), currency="USD",
    inflow_cents=5000 if (start + timedelta(days=i)).weekday() >= 5 else 1000,
    outflow_cents=200 if i % 2 else 0,
) for i in range(56))
history = DailyHistory(currency="USD", days=days, complete_coverage=True,
                       coverage_start=start, coverage_end=days[-1].date)
result = forecast_baselines(history, config=BaselineConfig(moving_average_window=2))
print(result.model_dump_json(indent=2))
```

Public functions:

- `predict_baseline(history, method=..., horizon_days=2, config=..., as_of=...)`:
  run a specified algorithm with explicit per-day fallback labels.
- `rolling_origin_backtest(history, horizon_days=2, config=...)`: evaluate all
  three methods on identical historical origins and known target dates.
- `calculate_metrics(actual, predicted, wape_minimum_actual_cents=100)`: score
  nonnegative integer-cent predictions against actual values.
- `forecast_baselines(history, horizon_days=2, config=..., as_of=...)`: compare
  methods, independently select inflow/outflow baselines, and predict future days.

### Algorithms and missing-data policy

`recent_value` repeats the last known daily inflow/outflow. `moving_average`
uses the trailing 7 calendar days by default, requiring every day to be known.
It falls back to recent_value when the window is short or contains an unknown
date. `seasonal_naive` averages the most recent 2 known matching weekdays for
each future date. If too few exist, it falls back to the available moving average
or recent_value. Configuration adjusts both windows. Each prediction identifies
the requested and effective method; warnings explain fallback. Means are computed
with exact integer arithmetic and rounded to cents, half up. No negative prediction
or recursively fabricated training observation is possible.

The input is one business's `DailyHistory`, in one currency. Callers must partition
exports by business before ingestion; category alone is not a business identifier.
Daily dates must be unique and chronological. Complete-coverage histories must
contain every declared date, including confirmed zeros. Unknown dates are never
filled by forecasting or backtesting. Unconfirmed coverage remains an explicit
limitation even when observed dates happen to be contiguous. Non-settled CSV rows
do not become actual observations.

Forecasts begin on the day after the last observed date, or after explicit `as_of`.
An as_of before any supplied observation is rejected; slice the history explicitly.
A later as_of preserves the requested dates but warns about stale data. Backtests
at ordinary observed origins cannot validate that extra gap. Empty history returns
`insufficient_data` and no predictions, retaining the requested horizon and supplied
as_of. Confirmed zero-activity history produces zero predictions and real zero MAE.

### Chronological evaluation and selection

The common minimum training count is
`max(minimum_history_days, moving_average_window, 7 * weekday_samples)`:
14 known days by default. Origins advance chronologically, using prefixes that
end before the target. Each lead +1 through +30 is scored separately, only if its
actual date exists. Unknown or unavailable targets are skipped and counted; a zero
actual is scored. Training coverage metadata is truncated to the origin. Defaults
use a daily origin step and at most the latest 60 eligible origins. Configuration
can alter these limits without any random splitting or parameter search.

Every method sees the same origins and targets. Backtest points retain origin,
target, lead, actual, prediction, and effective algorithm. A horizon has minimum
evidence after 3 scored windows by default; this is an engineering threshold,
not a guarantee of useful accuracy. Counts below that threshold can still have
descriptive scores, but do not qualify for model selection. Empty scores are null.

Selection pools held-out observations from the requested horizons that have
minimum evidence, weighting each scored observation equally. A method requiring
fallback on those observations or on the requested future dates is ineligible;
its diagnostic scores are still visible. Choose lowest MAE separately for each
direction. Within `max(1 cent, 2% of best MAE)`, compare absolute bias, then
dispersion of absolute errors, using the same tolerance. If differences remain
negligible, prefer recent_value, then moving_average, then seasonal_naive.
The output records candidate eligibility, scores, configuration, and reasons.
No usable comparison means an explicitly unvalidated recent_value fallback.

Metrics use integer-cent predictions, with fractional-cent diagnostics:

| Metric | Definition |
| --- | --- |
| MAE (cents) | mean of absolute predicted-minus-actual errors |
| Bias (cents) | mean predicted-minus-actual error; positive means overprediction |
| Absolute-error standard deviation (cents) | population dispersion of held-out absolute errors; lower is more stable |
| WAPE (ratio) | sum absolute errors / sum actuals; 0.2 denotes a 20% weighted error, not 80% accuracy |
| Evaluated observations | scored origin/target pairs for the specified lead |

WAPE is null when summed actuals are below a configurable 100-cent threshold
(or there are no observations). A documented reason accompanies null WAPE.
The threshold applies to each currency's cents and each scored set; zero/near-zero
activity still has meaningful MAE and bias. No accuracy percentages are emitted.
If diagnostic float arithmetic cannot represent unusually large integer amounts,
metrics become null with `numeric_range_exceeded`; integer cash arithmetic stays exact
and unavailable metrics cannot establish selection or promotion eligibility.
Daily rolling origins may overlap; sample counts are not independent evidence.
The model-selection backtest is diagnostic, not a separate unbiased holdout of
the complete selection process. Generalization must be monitored on future data.

### Output, reliability, and integration

The internal `ForecastResult` adds currency, requested horizon, as_of, selected
inflow/outflow methods, per-day predictions and actual effective methods,
selection reasons, comparison scores, horizon metrics, the auditable backtest,
warnings, and `uncertainty="not_estimated"`. `inflow_evaluation` contains the
horizon records for the selected inflow model (read their `inflow` metrics);
`outflow_evaluation` contains those for the selected outflow model (read `outflow`).
`evaluated_horizons` identifies leads with the configured minimum scored windows.
Each day's evidence flag additionally requires that its as_of has no stale-data gap.

Every returned forecast has exactly the requested 1–30 days. Longer forecasts may
be computable while lacking backtest evidence for some leads; those leads are
flagged. Reliability is `limited_backtest_evidence` only when every requested lead
has minimum evidence, coverage is confirmed, and data is current at as_of;
otherwise it is `insufficient_evidence`, or `insufficient_data` for empty history.
These labels are not calibrated confidence scores or accuracy guarantees.
No prediction intervals are invented. Baselines cannot establish annual seasonality,
respond to unknown shocks, or compensate for biased/incomplete exports.

No shared API contract or route changed. JV should review an adapter before exposing
this internal result through the API. Predictions can be mapped explicitly to
`DailyCash` and passed to the unchanged Phase 1 calculator, but forecasted receipts
remain projections. No known-obligation reconciliation or payment operations are
implemented in Phase 2.

## Phase 3 opt-in machine learning

The existing interface enables ML through one optional argument:

```python
from backend.app.forecast import MLConfig, forecast_baselines

# `history` is the same validated, single-business DailyHistory used in Phase 2.
result = forecast_baselines(history, horizon_days=2, ml_config=MLConfig())
```

Omitting `ml_config` preserves Phase 2 baseline behavior. No shared API route or
schema has been edited. Internal result fields now accept ML method names and add
eligibility, selected feature reports, fold reports, and timing diagnostics. Existing
fields retain their meanings. Timing diagnostics are observational and can differ
between otherwise reproducible runs; predictions and learned feature choices use
deterministic seeds and settings. Direct estimator inspection is available through
`models.fit_ml_candidate` and `models.predict_ml_candidate`; it does not prove a model
is better than baselines. The comparison entry point makes that decision.

### Features and availability

Calendar features are known ahead: day of week, weekend, month, quarter, ISO week,
day of month, weekday sine/cosine, weekday indicators, and a calendar time index.
The index supports trend learning without inventing industry-specific behavior.
Each predictor considers its own cash direction's lag 1 and 7, rolling means 3/7/14,
7-day volatility and trend, and recent matching-weekday activity. Historical features
use dates strictly earlier than the target; complete rolling windows are required.
Missing lags/windows remain NaN, not zero. Future historical features use only local
recursive predictions. There is one estimator per direction, not 30 fitted models.
Keeping the two directions' activity inputs separate makes separate model choices
consistent during recursion; cross-direction relationships are deferred.

`DailyHistory` does not currently provide covariates with availability timestamps.
Bookings, actual orders/occupancy, business category, promotions, location, holidays,
and other optional original CSV columns therefore remain excluded. Reports explain
this limitation. No raw source column is deleted, and no business metadata or
external seasonal information is fabricated. A future covariate contract must
distinguish preannounced information from outcomes and their revisions.
Phase 5 supplies `KnownAheadCovariate` records with business/date/name/value,
an aware UTC `known_at`, and evidence ID. Issuance rejects foreign-business,
duplicate name/date, nonfinite, or not-yet-known records. `covariate_diagnostics`
retains these records and explicitly reports `model_support_available=false`.
Current estimators do not consume them. A future adapter must apply availability
checks at every training/backtest origin and validate its missing-value policy.

### Training-only feature selection

Every outer training prefix reserves its final 7 days for a small inner chronological
comparison. Exactly two groups are tested per direction: calendar-only and calendar
plus that direction's history. Their recursive predictions are scored against the
inner period. Use the larger group only when its inner MAE improvement exceeds
`max(1 cent, 5% of calendar-only MAE)` by default; otherwise prefer calendar-only.
This inner choice never reads the outer test outcomes. It measures group-level
usefulness, not the predictive value or causality of every individual feature.

Within each fit, the sklearn pipeline removes fields with more than 40% training
missingness, constant/unusable fields, and exact duplicate training columns. A median
imputer and Ridge scaler are fitted on those training rows only. Tree models use
filtering and imputation without unnecessary scaling. Final pipelines are refitted
on the entire outer training prefix after group choice. No preprocessing is fitted
on the complete dataset before temporal splitting. Feature reports include selected
names, excluded reasons, availability, inner MAE, training range/count, and training
coefficients or forest impurity importance. Gradient boosting lacks this importance
report. Training importance is diagnostic; it establishes neither causality nor
individual out-of-sample improvement.

### Candidates, eligibility, and bounded work

| Candidate | Default data eligibility | Conservative configuration |
| --- | --- | --- |
| Ridge | 56 known days | alpha 0.1, standardized features |
| Random Forest | 90 known days | 24 trees, depth 5, minimum leaf 3, one worker |
| HistGradientBoosting | 90 known days | 50 iterations, depth 3, 15 leaves, minimum leaf 8; internal random validation disabled |

All candidates require confirmed complete coverage, enough inner training rows
(28 by default), and at least 3 complete outer windows for **every requested lead**.
Eligibility thresholds are configurable engineering defaults, not accuracy promises.
Missing/incomplete history, too few folds, or unsafe numerical amounts retain Phase 2
baselines with explicit eligibility reasons. For ML, monetary observations must lie
within float64's exact integer range; baseline integer arithmetic remains available
for larger amounts. Training and inference use a single CPU thread; no tuning search,
GPU framework, parallel service, persistence, or automatic retraining is introduced.

The registry considers all three eligible ML candidates. Candidates that cannot
complete all common windows are excluded, rather than being compared on a favorable
subset. Outer evaluation uses at most 6 origins, advancing by `max(5, horizon_days)`
by default: disjoint target windows for the prioritized 1/2-day forecasts, with weekday
rotation. The start is the largest admitted model's training requirement, so every
admitted ML candidate and all three baselines see identical origins and target dates.
Consequently enabling more eligible models can change comparison windows and scores;
they should not be compared to baseline-only scores from a different window set.

Gross ML predictions are finite-checked, clipped to zero, and rounded half up to
integer cents. Predictions outside the safe float64 range are rejected. Each later
forecast day sees generated earlier values, never future actuals. Recursive error
can accumulate, particularly on long horizons. If the requested range lacks adequate
ML windows, preserve all requested dates using Phase 2 methods and warnings.

### Cautious model promotion

On the common outer windows, choose the best eligible baseline separately for each
direction using Phase 2 MAE, bias, stability, and simplicity rules. An ML method may
enter selection only if its mean paired origin-level MAE gain exceeds both the
configured `max(1 cent, 5% of baseline MAE)` and twice the standard error of paired
gains. It must improve at least two-thirds of origins, and avoid material regression
in any requested lead, absolute bias, or absolute-error dispersion. The guard is
conservative and heuristic; it is not a calibrated significance test. Eligible
methods are then compared using MAE and the existing tie rules, with complexity
ordered baselines, Ridge, Random Forest, gradient boosting. Computational timings
are recorded; fixed complexity order resolves near-ties rather than noisy timings.
Baseline methods can and do win. Candidate `selection_evidence` records why ML
was admitted or declined for each direction. Missing metrics cannot win as zero error.

Outer scores are unseen by preprocessing and inner feature selection. Choosing the
final model nevertheless uses those outer scores, so they are **not** an independent
final holdout of the complete selection system. Validation on later real business
data remains necessary. History under one year carries an annual-seasonality warning.
The historical forecasting API does not return prediction intervals or invented
confidence percentages. The separate Phase 4 service below adds descriptive,
conditional ranges without altering this API.

## Phase 4 unified financial service

`forecast_cash_flow(CashForecastRequest(...)) -> CashForecastResult` is the new
internal entry point. The Phase 1 calculator and Phase 2/3 forecasting functions
retain their existing contracts. No shared route or teammate module changes.
Omitting `ml_config` uses baselines; passing `MLConfig()` reuses the existing
ML eligibility, chronological evaluation, feature selection, and model promotion.

Inputs include `DailyHistory`, a `VerifiedOpeningBalance` with a source evidence ID,
nonnegative integer-cent reserve, start date, 1–30-day horizon, local status records,
and optional categorized `IngestionResult` and `CategoryScheduleCoverage` records.
The opening balance is verified cash immediately **before** activity on `balance_date`,
which must equal `forecast_start_date`. Verification is the caller's responsibility;
this module does not verify a bank balance or a payment. Historical daily observations
and source transactions must precede the start. Currency conversion is unsupported.

`business_timezone` must be a valid IANA zone. All dates are already normalized
business-calendar dates; timestamps are rejected. An adapter must convert provider
timestamps to that timezone before deriving dates, including around midnight/DST.
An expected date on either forecast boundary is included. Out-of-window events are
excluded with reasons; overdue events are never moved to today automatically.

### Reconciliation contract

The policy is applied separately to inflows and outflows:

1. With no relevant scheduled events or category coverage, apply aggregate historical
   predictions. No known-event amount is added to that direction.
2. To apply residual predictions alongside known events, supply a complete historical
   export whose settled daily totals exactly reproduce `history`. All settled records
   in the affected direction must have categories. Every relevant event must belong
   to an explicitly covered category. Categories match after stripping and case folding.
3. `CategoryScheduleCoverage.complete_for_forecast_window=True` is an explicit caller
   attestation that the supplied events exhaust that category's cash activity over
   the **entire requested window**, including dates with intentionally zero scheduled
   activity. A list of a few known invoices does not establish this assertion. Changing
   the horizon requires the caller to reassess coverage; the service cannot prove it.
4. Remove the actual historical amounts of those covered categories, retain all other
   activity, and forecast that residual history using the existing engine. Add each
   eligible future event once. No estimated overlap is subtracted from a prediction.
5. If separation is unproven, suppress statistical predictions for the affected
   direction and use eligible known events only. `known_only_fallback`, per-direction
   policies, applied-model flags, and warnings expose the limitation. This fallback
   is **not** a lower or upper cash bound: omitted receipts or expenses can change risk.
   With empty history there are no model predictions; known events can still be shown.

Duplicate event IDs, source IDs, category scopes, and historical transaction links
are rejected. Installments and partially settled invoices need a future explicit
contract; assigning multiple events to one source is not supported. Both `source_id`
and any `historical_transaction_id` are checked against settled source transactions
and daily evidence IDs. A payment already represented in history cannot be added
again, even when another supplied link differs. Original inputs are not mutated.

The report lists removed historical IDs, schedule evidence IDs, original event
records, inclusion decisions and reasons. `fully_reconciled` describes component
separation under the caller's coverage assertion; it does not verify future payment.
Unapplied aggregate-model diagnostics remain available but do not describe a
fabricated residual series or the known-only projection.

### Local event statuses and payment-owner handoff

`ScheduledCashEvent` requires stable `event_id` and `source_id`, explicit direction,
nonnegative cents, currency, and one of these internal statuses:

| Status | Future cash rule |
| --- | --- |
| `verified_completed` | Always excluded; requires supplied verification evidence ID. |
| `invoice_unpaid`, `overdue_receivable` | Inflows only; require explicit `expected_date` and `projection_assumption`. |
| `pending_verification` | Either direction; require explicit expected date and assumption; remain pending. |
| `scheduled_expense` | Outflows only; require supplied expected payment date. |
| `cancelled`, `failed` | Always excluded. |

Missing expected dates are never inferred from `due_date`. Unpaid/pending events
without explicit assumptions are excluded, marked unresolved, and warned about.
Inclusion means **expected cash**, never verified completion. These statuses are
not PayPal status mappings. Vedant's adapter must establish trustworthy provider
status, evidence, identity links, timezone-normalized dates, and full category coverage
before constructing the request. No PayPal API calls or status transitions occur here.
Excluding a cancelled event does not by itself remove its category from aggregate
historical patterns; category exclusion still requires the reconciliation evidence.

### Monetary results and evidence for Hem

For every requested date, integer-cent arithmetic computes:

```text
receipts = applied residual inflow + known expected inflow
payments = applied residual outflow + known expected outflow
closing = opening + receipts - payments
next opening = previous closing
shortfall = max(0, reserve - closing)
breach = closing < reserve
```

Negative balances, zero events, multiple events per date, and arbitrarily large
integer event amounts are supported. ML retains its Phase 3 safe-float limits;
financial balances themselves never use binary floating point. Equality to the
reserve is safe. Zero statistical components in a suppressed direction mean
**no applied prediction**, not a forecast that ordinary activity will be zero.

The result includes daily component amounts, source IDs, applied model names,
original model metadata/validation metrics, first breach, minimum closing balance,
maximum shortfall, breach-day count, assumptions, and warnings. Requested long
horizons retain every date while existing evidence flags warn about unsupported leads.
`risk_assessment_complete` is false for unresolved reconciliation, inadequate history
or lead evidence, or included unverified receipts/pending events. A true flag is
not an accuracy or collection guarantee.

Each shortage record references its forecast-day evidence ID and opening-balance
evidence ID. It lists all included events up to that date, their signed balance effect,
closing balance with that one event removed, and the resulting shortfall difference.
Those are arithmetic comparisons holding other components fixed, **not causation**;
shortfall effects are nonlinear and should not be summed. This is factual structured
input for Hem's future agent, without LLM calls, prompts, or recommendations.

### Approximate uncertainty

Only chronological held-out residuals of the selected methods are used, with
`actual - predicted` signed errors. A default minimum of eight disjoint held-out
windows is required per lead (`UncertaintyConfig.minimum_samples`, minimum three).
Daily residual ranges add the observed minimum/maximum error to the current residual
prediction, flooring gross activity bounds at zero. This retains observed asymmetry
and bias; it does not posit a Gaussian distribution or a confidence percentage.

Closing ranges use **complete paired paths** from the same historical origin through
the requested lead. Sum the observed net inflow/outflow errors within each path,
then add the minimum/maximum cumulative path error to the projected closing balance.
Path windows do not overlap. Cross-day and inflow/outflow dependence are preserved;
daily marginal bounds are never summed or assumed independent.

Ranges require current complete history, applicable selected-method evidence, and
enough lead-specific samples. Cumulative ranges also require both predicted directions
and resolved reconciliation. Unsupported ranges have `status="unavailable"` and null
bounds with reasons/counts. Some leads/directions can be available while others are not.
The first two days are evaluated independently of longer unsupported horizons.
Phase 3's default six outer ML origins cannot satisfy the default eight-sample rule,
so ML ranges normally remain unavailable. Lowering the threshold is explicit and
does not create additional evidence.

These are descriptive **empirical envelopes**, not calibrated prediction intervals.
The same backtest scores select the final model, so this is not a separate final
calibration dataset. `calibrated_coverage` is null. Bounds hold known-event payment
and timing assumptions fixed; collection risk is explicitly **excluded**. Short
seasonal coverage, regime changes, and zero historical error can make them optimistic.
Authoritative projected balances and uncertainty metadata remain separate.

### Executable synthetic example

The following complete category schedule and small, constant history are synthetic
arithmetic examples, not evidence of real business forecasting accuracy:

```python
from datetime import date, timedelta
from backend.app.forecast import (
    CashForecastRequest, CategoryScheduleCoverage, ScheduledCashEvent,
    VerifiedOpeningBalance, aggregate_daily, forecast_cash_flow, ingest_csv,
)

start = date(2026, 10, 13)
first = start - timedelta(days=42)
rows = ["transaction_id,date,amount_cents,direction,currency,category,payment_status"]
for i in range(42):
    day = (first + timedelta(days=i)).isoformat()
    for prefix, amount, direction, category in (
        ("sale", 100, "inflow", "sales"),
        ("paid_invoice", 50, "inflow", "invoices"),
        ("operating", 20, "outflow", "operations"),
        ("paid_supplier", 30, "outflow", "suppliers"),
    ):
        rows.append(f"{prefix}_{i},{day},{amount},{direction},USD,{category},settled")
source = ingest_csv("\n".join(rows))
history = aggregate_daily(source, coverage_start=first,
    coverage_end=start - timedelta(days=1), complete_coverage=True)
request = CashForecastRequest(
    history=history, historical_transactions=source,
    opening_balance=VerifiedOpeningBalance(balance_cents=1000, currency="USD",
        balance_date=start, evidence_id="bank_snapshot"),
    safety_reserve_cents=800, forecast_start_date=start, business_timezone="America/Chicago",
    known_events=(
        ScheduledCashEvent(event_id="invoice_future", source_id="inv_future",
            direction="inflow", amount_cents=500, currency="USD", category="invoices",
            status="invoice_unpaid", expected_date=start,
            projection_assumption="Projected customer collection; still unpaid."),
        ScheduledCashEvent(event_id="supplier_future", source_id="bill_future",
            direction="outflow", amount_cents=1400, currency="USD", category="suppliers",
            status="scheduled_expense", expected_date=start + timedelta(days=1)),
    ),
    category_coverage=tuple(CategoryScheduleCoverage(category=category, direction=direction,
        evidence_id=f"schedule_{category}", complete_for_forecast_window=True)
        for category, direction in (("invoices", "inflow"), ("suppliers", "outflow"))),
)
result = forecast_cash_flow(request)
assert [day.projected_closing_balance_cents for day in result.days] == [1580, 260]
assert result.first_reserve_breach_date == date(2026, 10, 14)
assert result.maximum_reserve_shortfall_cents == 540
```

The residual forecast is 100 cents in and 20 out per day, excluding historical
invoice/supplier activity of 50/30 cents. October 13 adds the conditional 500-cent
receipt, closing at 1,580. October 14 includes the 1,400-cent bill, closing at 260
with a 540-cent shortfall below the 800-cent reserve. The invoice remains unpaid;
`risk_assessment_complete` is false. Constant synthetic history can produce equal
empirical lower/upper bounds, which do not establish real-world certainty.

JV's API adapter and Vedant's verification/provider mappings stay outside this owned
module. Independent uncertainty calibration, partial-settlement support, and uncertain
collection timing remain unsupported capabilities, explicitly surfaced in diagnostics.

## Phase 5 public operations and issuance

Use `prepare_history(PreparationRequest)` to return `PreparedHistory(source, history)`.
Use the existing `forecast_baselines` for stateless model selection/daily predictions,
or `train_forecast_model` followed by `forecast_trained_model` to reuse a selected model.
`forecast_cash_flow(CashForecastRequest, trained_model=...)` reconciles known events
and calculates balances. `issue_forecast(ForecastIssueRequest, trained_model=...)`
wraps that result in `IssuedCashForecast` with business ID, issuance ID, aware UTC
generation time, and separate applied inflow/outflow model versions.

The financial result includes residual predictions, eligible known cash, opening and
closing balances, reserve breaches/shortfall, selected methods, reliability, uncertainty,
source/category reconciliation, assumptions, event IDs and verification evidence.
Stored-model results add `model_artifact_id`, `model_version`, and `request_fingerprint`.
Their forecast ID incorporates the artifact/version and predicted path. Stateless
results retain request-derived IDs and null stored-model versions. Monitoring uses
issuance ID to distinguish separate issuances of the same request. Version labels
cannot conflict with stored metadata or identify a direction whose model was suppressed.

An issued forecast must have consecutive target dates, matching currencies, and a
training origin available by issuance that precedes its targets. Application code must
derive business ID and generation time from its authenticated server context. These
Python schemas do not authenticate a user, verify a bank snapshot, or query PayPal.
The read-only diagnostics are on the returned result, metadata, `covariate_diagnostics`,
monitor report, and retraining decision; no global cross-business report is maintained.

### Cold starts and forecast horizons

The default forecast horizon is two days; supported calculations are 1–30 days.
Baseline and ML results label the leads supported by chronological evidence. Extending
the numerical horizon does not establish its reliability: JV should offer longer
forecasts only when returned evaluation supports every requested lead. Stored artifacts
cannot forecast beyond their configured horizon; adaptive retraining compares the same
horizon as the active artifact. A different horizon needs a separately reviewed artifact.

Fewer than 14 known days use explicitly unvalidated simple fallbacks plus verified
opening cash and eligible known events. Between 14 and 55 days, prefer eligible simple
baselines. Ridge starts at 56 usable days by default; tree models start at 90. These
configurable minimums do not override complete coverage, usable training rows, adequate
common backtest windows, or feature availability. Missing dates are never presumed zero.
Summer observations do not validate winter or annual seasonality. No industry patterns,
holidays, weather, or external priors are invented.

## Deterministic what-if scenarios

`simulate_scenario(financial_request, ScenarioRequest, baseline=...)` accepts unique,
explicitly justified operations to move an included future receipt/expense, change an
expense amount, replace a dated residual projection, add a hypothetical incremental
event, or remove an included scheduled event. It returns `ScenarioComparison` with both
daily forecasts, breach dates, minimum balances, maximum shortfall changes, daily deltas,
changed events and assumptions. It never performs a provider action or changes history.

Supply the original baseline to reuse its fixed predictions without fitting models.
Each event can be edited once per request and each date/direction projection once.
Settled, cancelled, failed, past, excluded, unknown, or duplicate event edits fail
validation. Added events need unique IDs, `hypothetical=true`, and an explicit
incremental-cash assumption. Moving an event past the horizon retains it in changed-event
evidence with an explicit warning and zero contribution inside this window. Moving it
before the forecast start is rejected. Removing an event is only a hypothetical removal.

The baseline is never mutated. Scenario amounts and balances remain integer cents.
Any inherited empirical ranges are shifted conditionally on the changed cash path;
they are not new model validation. Scenario reconciliation/risk completeness is false,
and scenarios must not be recorded as forecasts for measuring actual model accuracy.

## Trusted local models and registry

`train_forecast_model` returns a `TrainedForecastModel` containing separate direction
metadata, the training history and selected fitted pipelines. Metadata records business,
currency, immutable version, UTC training time, range/count/fingerprint, feature schema,
selected features, hyperparameters, configurations, validation scores, eligibility,
reliability, warnings, dependency versions and promotion evidence.

`LocalModelRegistry` provides `save_candidate`, `load`, `get_status`, `promote`,
`mark_failed`, `rollback`, and `get_decisions`. Versions are immutable and tenant-scoped.
Loading checks identity, currency, expected metadata, feature/dependency compatibility,
and artifact SHA-256 before joblib deserialization. Exact dependency versions are required.
Checksums detect corruption; they do not authenticate an artifact from an untrusted party.
Joblib is executable serialization: only load artifacts created by this trusted backend.
Keep uploads and artifact roots separate, and keep those roots service-owned.

Identifiers permit 1–64 ASCII letters, digits, underscores and hyphens. Traversal,
symlinks and nonregular files are rejected. Atomic writes and POSIX locks protect local
updates. Limits are 128 MiB per serialized artifact and 2 MiB per registry JSON file.
Rollback validates the previous artifact before switching. A failed candidate cannot
overwrite the active pointer. Direct `promote` is an administrative mechanism;
`retrain_model` supplies the scientific promotion gate.

Inference with a loaded pipeline never refits it. Appended history must preserve its
exact validated historical prefix and currency; corrections require a separate reviewed
replacement artifact. Fixed-baseline inference rejects a switch to a fallback algorithm.
Appended observations can update baseline/history features, but old validation scores
remain historical diagnostics and newly issued lead evidence is cleared until evaluated.
Train on the reconciled residual history when category isolation is used. An aggregate
artifact cannot silently be reused as a residual artifact.

## Verified forecast performance

`LocalForecastMonitor.record_forecast` stores the original issued snapshot;
`record_actual(ActualObservation)` stores complete, explicitly verified daily cash with
evidence and an aware UTC observation time after the business day ended. `evaluate`
matches business, currency and target date, retaining issuance time, target lead, model,
version, predicted/actual cents and signed error. Missing actuals produce no accuracy score.
Identical ingestion is idempotent; conflicting IDs or duplicate business dates fail.

Reports separate directions, leads and versions, with MAE, bias, dispersion and WAPE
where meaningful. Only fully reconciled applied forecasts have accuracy errors. Gross
actuals include known cash; aggregate backtest references are usable only when their
basis matches those actuals. Residual-category references are explicitly unavailable.
Duplicate issuances targeting one date do not count as independent deterioration evidence.
Default deterioration requires two consecutive windows of five distinct dates exceeding
historical MAE by both 25% and one cent. Those thresholds are configurable.

Local snapshots are atomic, locked, tenant-scoped JSON with a 16 MiB limit. Exceeding
the limit fails without overwriting the old snapshot. Long-running deployments need an
application-managed retention/archive strategy; this MVP has no database or background job.

## Explicit adaptive retraining

Call `retrain_model(registry, RetrainingRequest, monitoring=report)` with complete verified
appended history and verification evidence. Defaults trigger on at least 14 new observations,
30 days of model age, changed configuration, no active model, or sustained deterioration
for the active version. None of these automatically deploys a candidate. Passing no ML
configuration inherits the active configuration; explicit ML removal needs a replacement
artifact workflow. Future or foreign-business monitoring evidence is rejected.

Selection/training uses a prefix before 3–6 fresh, complete, disjoint final paths by default.
The fixed candidate and incumbent are then compared on the same final paths with ordinary
baselines. Promotion requires no material MAE, bias, dispersion or per-lead regression,
plus defensible paired improvement for at least one direction when an incumbent exists.
The paired gain must exceed the 5%/one-cent and two-standard-error guard, with improvement
in at least two-thirds of paths. Initial deployment must pass baseline safeguards.

Final windows are reserved before training and never reused by later promotion attempts,
including after failures. Decisions are idempotent by request/evidence fingerprint and
decision ID, with structured evaluation evidence. A per-business lock serializes this
workflow. The exact pre-holdout candidate is deployed without refitting or reselecting
after observing final outcomes. Insufficient evidence, equal/worse candidates and failures
retain the active model. Training cost is bounded by existing model limits and at most
ten final windows; no scheduler, exhaustive search, worker, or external ML platform is added.

## Example JSON contracts

This executed preparation request is valid JSON with CSV content embedded as a string:

```json
{
  "csv_data": "transaction_id,date,amount_cents,direction,currency,payment_status\nsale_1,2026-10-12,1234,inflow,USD,settled",
  "coverage_start": "2026-10-12",
  "coverage_end": "2026-10-12",
  "complete_coverage": true
}
```

`prepare_history(...).history.model_dump(mode="json")` returns:

```json
{
  "currency": "USD",
  "days": [{"date": "2026-10-12", "currency": "USD", "inflow_cents": 1234,
            "outflow_cents": 0, "evidence_ids": ["sale_1"]}],
  "coverage_start": "2026-10-12",
  "coverage_end": "2026-10-12",
  "complete_coverage": true,
  "warnings": []
}
```

`PreparedHistory.source` also retains normalized transactions and original fields.
See [INTEGRATION.md](INTEGRATION.md) for an executed complete public Python workflow,
forecast response serialization, scenario input JSON, and verified actual input JSON.
Map `IngestionError.issues` and Pydantic field errors to actionable frontend errors.
Service validation raises `ValueError`; storage failures must be surfaced without
reporting success or silently switching models. Shared FastAPI routes remain JV's.

## Executed synthetic workflow and benchmark

Run from the repository root:

```sh
./.venv/bin/python -m backend.app.forecast.demo
```

The demo prepares 365 complete days / 1,460 transactions / 90,245 CSV bytes, selects
Ridge separately for both directions, saves/reloads a model, and issues a two-day
reconciled forecast. Starting at 500,000 cents with a 200,000-cent reserve, a conditional
40,000-cent invoice and a 950,000-cent supplier bill yield closing balances
`[619874, -245141]` and a 445,141-cent shortfall on October 14, 2026. Hypothetically
moving that bill beyond the two-day horizon yields `[619874, 704859]` and no breach
inside the window; the bill remains an obligation in scenario evidence. Four direction
errors match two forecast targets to verified synthetic actuals. Fourteen new days
trigger an independent retraining evaluation that retains v1 in this run. Empirical
uncertainty is unavailable because the ML comparison has fewer than eight disjoint paths.

Actual single-run measurements on this development host (warm imports, Python 3.14):

| Operation | Seconds |
| --- | ---: |
| Data preparation | 0.009320 |
| Model training and selection | 2.599474 |
| Model save/reload | 0.038873 |
| Financial forecast generation | 0.023233 |
| Scenario simulation | 0.012669 |
| Retraining evaluation | 2.816482 |

These measurements establish this synthetic workflow's observed cost, not production
throughput or real-business predictive accuracy. Demo artifacts use temporary directories
and no network requests. Existing small unit tests remain separate from public-interface,
real-ML persistence, promotion and end-to-end integration tests.

The final Phase 5 gate on this host passed all 498 forecast tests in 9.92 seconds
and all 504 backend tests in 9.87 seconds, with zero failures. The only test warning
was joblib's physical-core detection falling back to logical cores. Public imports,
Pydantic schemas, documentation JSON round-trips, compilation, dependency consistency,
and whitespace checks passed. No formatter, linter or type-checker is configured in
this repository, so no separate tool result is claimed.

## Integration responsibilities and remaining limits

JV supplies authenticated tenant IDs, authoritative server timestamps, upload/response
transport, safe storage locations, upload size limits, privacy/retention policies and HTTP
error mapping. Reject unsafe JavaScript integer conversions for cents beyond
`Number.MAX_SAFE_INTEGER`; use lossless parsing or a separately reviewed string transport.
Hem consumes evidence IDs, component assumptions and conditional ranges; an unpaid invoice,
scenario deferral or projected shortage must never be represented as a verified payment,
executed recovery action or invented probability. Vedant supplies verified complete actuals,
normalized authoritative statuses, stable ledger IDs and complete category schedule evidence.
See [INTEGRATION.md](INTEGRATION.md) for exact fields and wiring sequence.

Arbitrary covariate learning, holiday/external signals, currency conversion, partial
settlements, revised historical prefixes, calibrated coverage, uncertain collection
timing, application authentication, provider execution and distributed storage are not
implemented. None is presented as working functionality. Validated simple fallbacks and
explicit known-event assumptions keep limited-data behavior usable. The financial engine
is an integration-ready hackathon MVP; synthetic tests do not prove real-world accuracy.
