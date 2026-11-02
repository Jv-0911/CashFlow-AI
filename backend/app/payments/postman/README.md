# Private Sandbox diagnostics

Check Postman's Devpost page for the hackathon's actual sponsor offer before
using it. These files were authored locally and have not been executed against
PayPal. Seven offline JavaScript checks execute guard logic with a fake pm object;
actual Postman import/runtime validation is still outstanding.
Import `paypal-sandbox.collection.json` and the EMPTY
`sandbox.empty.environment.json` into a private local workspace. Never sync or
export a populated environment, response history, or request logs publicly or
to Git. Secret field labels are not access controls.

Populate credentials locally, keep SSL certificate verification enabled, and
disable automatic redirect following. All URLs are pinned to PayPal Sandbox.
The collection exports `strictSSL: true`, `followRedirects: false`, and
`disableCookies: true`. Use a Postman version supporting `pm.execution.skipRequest`;
invalid guards explicitly skip requests instead of relying on thrown exceptions.
Never switch this collection to the live PayPal host. Avoid the request console
or saved response examples when they would retain credentials or payer data.

Use a local collection-runner session with OAuth first and select only the
desired subsequent requests. OAuth stores the access token in runner-local
`pm.variables`, never persistent environment variables. A separate manual Send
session may not retain that local token; do not fix that by exporting a token.

| Request | Private input / prerequisite |
|---|---|
| OAuth | Sandbox client ID and secret |
| Create draft | Reviewed one-cent USD ledger approval, matching entry ID, stable invoice number and create request UUID, Sandbox payer |
| Send | Actual approval event ID and matching invoice ID; explicit local attestation; stable send request UUID |
| Get invoice | Existing Sandbox invoice ID |
| Verify signature | Genuine captured Sandbox transmission headers, registration ID, and original event object; never store the body in this repository |

The create example is exactly USD 0.01; its ledger approval must match the amount
and payer. Create and send attestation variables are operator reminders, not proof of
authorization. These diagnostic requests cannot query or enforce the local
ledger's approval by themselves. Do not expose them as application endpoints.
The application must create/send through `InvoiceService`, which records durable
operation identities and performs approval checks automatically.

Do not mix a direct Postman create/send and an application create/send for the
same entry: Postman does not record the application's operation claim or bind
the returned invoice. Use separate approved diagnostic entries and keep their
cash totals unverified. A collection response must never be copied into a
VERIFIED_PAID write. Only the application's fresh verification service can do
that for an application-bound invoice.

Reuse an operation's UUID only for that same operation. After a timeout, inspect
the existing invoice rather than rerunning all requests or choosing a new key.
PayPal idempotency support/retention varies by API; a stable header is not an
unlimited guarantee of safe replay. Keep create/send unselected during routine
read-only diagnostics. Clear populated private environment/history after use.

Export only the original secret-free collection and empty environment template.
No populated environment, credentials, tokens, webhook bodies, or payer emails
belong in a submission artifact. Use the application
[Sandbox runbook](../SANDBOX_RUNBOOK.md) to validate the complete ledger flow.

Guard references: Postman's [skipRequest documentation](https://learning.postman.com/v11/docs/tests-and-scripts/write-scripts/postman-sandbox-reference/pm-execution)
and [protocol-profile settings](https://github.com/postmanlabs/postman-runtime/blob/develop/docs/protocol-profile-behavior.md).
