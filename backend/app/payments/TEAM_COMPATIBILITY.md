# Member 3 adapters for forecast and rescue evidence

`evidence_exports.py` produces dictionaries accepted by the existing Member 1
`ScheduledCashEvent` and Member 2 `InvoiceEvidence` models. It does not change
their schemas, the proposed payment JSON, HTTP routes, ledger schema or state
machine. It has no third-party dependencies and performs no network calls or
writes. Shared application code must authenticate the user, authorize the entry,
and provide the trusted `LedgerService`; do not expose a database path or accept
a client-supplied snapshot.

## Inputs and meaning

```python
from datetime import date
from backend.app.payments.evidence_exports import forecast_event, rescue_invoice

# ledger and entry_id come from authorized server context.
event = forecast_event(
    ledger, entry_id,
    expected_date=date(2026, 10, 15),
    projection_assumption="Assume collection on the planned date.",
    category="receivables",
)
invoice = rescue_invoice(ledger, entry_id, due_date=date(2026, 10, 14))
```

Dates in the example are synthetic. Date arguments must be `datetime.date`
objects, not timestamps or strings. A due date is never used as a collection
date. Forecast timing/assumptions may be omitted; the forecast engine then
excludes the unresolved event. The rescue schema requires a due date, which
the current ledger does not store: resolve it from trusted invoice records or
do not export that invoice. Never substitute today's date or a creation time.

An unpaid/pending export requires a stored `PAYPAL_VERIFIED` observation with
zero paid/refunded amounts and the full approved amount outstanding. A send
acknowledgement, unknown remaining amount or partial balance is insufficient.
Use the existing verification service to obtain an observation when provider
access is available. These adapters do not refresh it. The exports describe
the **last recorded evidence**, and cannot establish that PayPal has not changed
since then. Keep observation age and refresh failures visible in the existing
payment view; the peer schemas have no observation-age field.

## State mapping

| Ledger state | Forecast event | Rescue invoice |
|---|---|---|
| `INVOICE_SENT` with full unpaid observation | `invoice_unpaid` | `unpaid`, full approved outstanding cents |
| `PAYMENT_PENDING` with full unpaid observation | `pending_verification` | `pending`, full approved outstanding cents |
| `VERIFIED_PAID` | `verified_completed`, ledger verification event ID | `paid`, zero outstanding cents |
| `CANCELLED` | `cancelled`, excluded by forecast | Unavailable: no invented remaining balance |
| `FAILED` | `failed`, excluded by forecast | Unavailable: no matching rescue status |
| `PROPOSED`, `APPROVED`, `INVOICE_DRAFTED`, `AWAITING_VERIFICATION`, `PARTIALLY_PAID`, `OFFLINE_MARKED_PAID`, `UNRESOLVED`, `REFUNDED` | Unavailable | Unavailable |

Unavailable exports raise `EvidenceUnavailable`, a sanitized `PaymentError`
with code `PAYMENT_EVIDENCE_UNAVAILABLE`. The existing `error_view` envelope can
serialize it. Do not silently discard failed exports and call the resulting
analysis complete. Display unavailable/incomplete evidence and preserve the
original ledger state. Adding full support for the remaining states requires
an explicit shared-contract decision, not a forced mapping to paid or unpaid.

Forecast `event_id` and `source_id`, and rescue `invoice_id`, use the stable ledger
entry ID. Re-exporting does not create a new identity. `verification_evidence_id`
comes from the verified ledger event and is null for other states. No payer
email, recipient fingerprint, approval identity, token or raw provider body is
included. Caller-provided category, collection assumption and optional
`historical_transaction_id` must be authorized, non-sensitive planning metadata.
They are never written back to the ledger.

## Boundaries that remain explicit

- A verified invoice is excluded from future receipts by Member 1. It is not
  automatically added to a bank balance or transaction history by this adapter.
- `ledger.recovered_cash()` is the total of current fully verified recovery
  entries, not a verified opening bank balance, daily gross settlement total,
  net-of-fees amount or a complete business cash report. Do not use it to attest
  Member 1's `VerifiedOpeningBalance`, `ActualObservation.complete`, category
  completeness, or settled CSV history.
- Actual settlement dates, fees, complete daily transactions and business-timezone
  conversion need authoritative account data. The ledger verification timestamp
  records when evidence was observed, not necessarily when settlement occurred.
- Member 2 actions remain recommendations. Their estimated impacts and action
  IDs must not automatically create/send another invoice for an already bound
  receivable. Existing invoice follow-up is not authorization to rebill it.
- Forecast and scenario outputs are not accepted as payment evidence. USD is
  still the only payment currency even though teammates' schemas support others.
- Historical links must point to the same already represented receipt. Arbitrary
  links can suppress projections; only trusted server data may supply them.

## Tests

The standalone, credential-free suite includes adversarial adapter tests:

```powershell
python -B -m backend.tests.payments.run_tests
```

With the unchanged teammate modules installed in the same checkout, run the
separate offline compatibility suite:

```sh
python -B -m backend.tests.payments.team_compatibility
```

The compatibility suite validates both real Pydantic schemas and executes the
actual forecast/reconciliation and deterministic rescue functions. It checks
conditional unpaid/pending projections, missing timing, duplicate rejection,
paid exclusions, approval-only recommendations, and no payment side effects.
It uses synthetic PayPal transport responses and blocks network access.

Member 1's package currently imports POSIX `fcntl` and needs Linux for its full
public imports/storage tests. For all teammates' pytest suites, use
`--import-mode=importlib`: forecast and payments both have `test_reconciliation.py`.
No shared pytest configuration or teammate source was changed to resolve this.
