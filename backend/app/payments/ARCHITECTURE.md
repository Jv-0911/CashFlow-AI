# Member 3 security decisions

Sources read in full: root `TEAM_WORKPLAN.md`, `M3README.md`, and
`M3ARCHITECTURE.md`. The user authorised resolving their conflicts on
2026-10-12. Root source documents and shared API routes remain unchanged.

## Decisions applied to the ledger foundation

1. **Recovered totals use only current VERIFIED_PAID entries.** Partial and
   offline-marked payments contribute zero. A refunded entry leaves this
   total entirely; the function is not a net-receipts accounting report and
   does not add partial amounts or subtract a refund twice. This overrides
   the partial-payment accounting in the root module documents, following
   the user's stricter rule. Member 4 must use the same meaning in the UI.
2. **Provider invoice bindings are separate immutable rows.** No placeholder
   provider ID on an entry is updated later. Binding insertion is atomic
   with the hashed invoice-created event. Unique constraints prevent an entry
   or PayPal invoice from being bound twice. Every binding must match its
   hashed creation or recovery event or integrity verification fails.
3. **PAYMENT_PENDING may go directly to VERIFIED_PAID.** INVOICE_SENT may
   also go directly to PARTIALLY_PAID. A payer need not pass through a partial
   payment. Both require verification, and every downstream invoice/payment
   state requires a prior human approval. No new states were introduced.
4. **Uncertain states cannot invent human approval.** Their exits are limited
   to provider-derived states, through verification only. A fetched invoice
   cannot generate a PROPOSED or APPROVED event. Repeated observations of a
   provider state are reserved for verification, never workflow callers.
5. **Previously verified entries cannot be changed by workflow callers.** A
   fresh inconsistent provider response may flag UNRESOLVED; a verified
   refund may produce REFUNDED. An outage must do neither. CANCELLED, FAILED,
   and REFUNDED have no forward workflow transitions. Corrections are new
   approved recovery items, not mutation of terminal history.
6. **Actor labels do not grant verification authority.** The public service
   has only proposal and approval write methods. The store likewise has no
   public generic paid-state append method. The transition checker is a pure
   policy function, not proof that PayPal was contacted. A private, single-use
   observation minted by fresh-fetch verification expires after 30 seconds.
   Persistence requires it and rechecks sequence and financial evidence. Python
   process code is trusted; Python privacy cannot contain hostile backend code.
7. **Approval is stronger than just a send-time check.** A human approval is
   required before draft creation as in the documented primary workflow.
   Authentication and authorisation of that human remain API-layer duties.

## Payment services and trust boundaries

- Timeouts, unavailable PayPal, and ambiguous create/send responses preserve
  the previous state. Only definite rejection can be considered for FAILED;
  a transport failure is not evidence that the operation did not happen.
- Missing/unknown provider statuses map to UNRESOLVED. Malformed identity,
  currency, amount, or response structure can never produce verified cash.
- A crash before storing the newly created provider ID cannot be resolved by
  fetching an ID that was never saved. Persist an outbound operation identity
  before the call. Reconciliation searches the saved stable invoice number,
  fetches candidates, and binds exactly one matching invoice. It never reposts
  an ambiguous create, even with the same key: provider retention/support is
  API-specific. Missing or multiple matches require operator review.
- PayPal host pinning and TLS must apply to token, invoice, webhook-signature,
  retry, and pagination/link paths alike. No redirect or provider-supplied URL
  may select a different API host.
- Production-looking client-ID heuristics are not a proven security control.
  Sandbox mode and exact hardcoded Sandbox destination checks provide the
  enforceable environment boundary; no invented credential pattern is used.
- Verified and partial payments require matching PayPal transaction sums and
  remaining balance, with no refund amount. External/offline payments cannot
  count. Refund statuses remove an entry from recovered totals conservatively;
  this is not a net cash accounting report. No refund API is implemented.

## Durable operations and concurrency

`payment_operations` holds immutable create/send claims, request UUIDs, payload
hashes, and their hashed event IDs. Unique constraints cover request UUID,
operation key, and `(entry_id, kind)`. Claim, completion, and error events use
SQLite transactions; network calls run outside those transactions. Expected
sequences reject stale results. Ambiguous timeouts keep the last state.

Read-only eligibility checks precede OAuth and send preflight. A trusted
`before_dispatch` callback commits the final claim after OAuth succeeds and
before the first create/send POST. It repeats eligibility checks atomically;
concurrent callers may perform preflight reads but only one can claim the write.
The callback runs once, retaining its saved request ID through the existing
single 401 refresh. Preliminary failures leave no claim or financial event, so
retrying the same key is safe. A crash after claim commit remains uncertain even
if dispatch did not happen; old claims are never reset.

An approval records an opaque payer reference. A trusted server resolver maps
it to an email only for the outbound request. Creation binds its fingerprint;
send and verification require the same recipient. Do not allow reassignment of
an approved reference to another payer. No email is stored in the ledger.

Recovered bindings append `INVOICE_RECOVERED` while retaining APPROVED, then
require another fresh verification GET. Consequently APPROVED can transition
directly to provider-observed draft/sent/pending/partial/paid/offline states
through verification after a recovered binding. This explicitly resolves crash
recovery without manufacturing intermediate workflow states. No new state was
introduced. The root plan's shared contracts remain unchanged.

Unknown/malformed statuses still map to UNRESOLVED. If the current state is
terminal and that transition is disallowed, verification raises RecoveryRequired
without writing. Evidence expiry is checked after the write lock and integrity
scan, so waiting cannot extend its 30-second validity. Invalid OAuth data is an
authentication error, not invoice evidence, and cannot change payment state.

## Webhook receipts and reconciliation

The handler validates bounded bytes/headers, requests PayPal signature
verification, then inserts a unique provider event ID. It ignores the webhook's
payment status and amount and fetches the bound invoice afresh. Certificate URLs
are validated as Sandbox metadata and never fetched locally.

Receipts have their own append-only hash chain, linked to an existing financial
event. They cannot write a VERIFIED_PAID event. A receipt may commit before a
failed fetch, so periodic reconciliation is mandatory: duplicate delivery is
acknowledged without replaying the failed fetch. The sweep also revisits verified
entries to detect refunds. Terminal cancelled/failed/refunded entries require
operator review rather than automatic resurrection.

Integrity checks validate schemas, triggers, canonical hashes, references,
operation/event correspondence, receipt chains, and state/evidence semantics.
The optional checkpoint covers the financial chain only. Receipt-tail deletion,
rollback before an unanchored head, and consistent administrator rewrites cannot
be detected without separately trusted anchors/backups. Older schemas fail
closed; there is no destructive automatic migration.

## Contract and ownership boundary

`audit.SafePaymentLogFilter` retains only enum event/state labels, discarding
free text, arguments, exceptions, stacks and custom fields. Use isolated
`make_payment_logger(stream)` or attach the filter to every payment log handler.
The shared server must separately protect its request/access logs; the module
does not configure global logging automatically.

No HTTP routes are implemented here. On 2026-11-02 the user authorized selecting
the tested `contracts/payment-ledger.example.json` and `payments/contracts.py`
implementation format for integration; see `CONTRACT_HANDOFF.md`. This does not
claim that HTTP/UI wiring or external review is complete. `PaymentRuntime.from_env` is the internal
composition entrypoint, not an authentication or authorization layer.

Deployment configuration and API authentication belong to their owners. The
user explicitly authorized a root `.gitignore` during handoff preparation; its
rules are supplied/tested and must be verified in the team's actual repository.
Postman assets can live under the owned payments
module rather than the out-of-scope root `docs/` directory. Render deployment
must use a persistent disk or hosted database. Check each sponsor's Devpost
page before adopting its tools. Local Postman templates are prepared; no hosted
service or live payment integration has been run.

## Provider references

- [PayPal Invoicing schema](https://developer.paypal.com/api/invoicing/v2/schema.json)
- [PayPal idempotency](https://developer.paypal.com/api/rest/reference/idempotency/)
- [Webhook signature verification](https://developer.paypal.com/api/webhooks/v1/verify-webhook-signature-post)

Strict parsing intentionally fails closed when responses do not meet the schema
assumptions. Credentialed Sandbox testing is still required to validate those
assumptions against actual responses.
