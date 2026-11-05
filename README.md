# CashFlow AI

Cash-flow planning and recovery for a small business: forecast a reserve shortfall, understand the evidence, compare a what-if scenario, and approve an invoice workflow whose payment status comes only from PayPal.

The integrated website uses a **clearly labelled fictional Juniper Studio dataset**. Forecasts and scenarios run Member 1's financial engine; recovery runs Member 2's evidence-based analysis; invoices and the append-only ledger run Member 3's services. Member 4's frontend (merged from the `frontend` branch) and the authenticated API connect these modules. The earlier replacement UI has been removed.



## What to try

1. Review opening **demo** cash, the reserve, projected low point, and breach date.
2. Open Forecast and change the horizon between 7, 14, and 30 days.
3. In Scenarios, change receipt timing, revenue/expense percentages, or additional expenses. Compare the resulting balances; no account is changed.
4. In AI Rescue, run analysis. Review explanations, evidence IDs, and assumptions. With no external AI configured, the interface explicitly shows deterministic analysis.
5. After administrator sign-in, open Payments & Ledger and record a receivable proposal. Its ledger state is `PROPOSED`, with zero recovered cash.
6. Inspect the ledger row and explicitly approve the amount and administrator-configured test payer. Approval alone sends nothing.
7. When PayPal is privately configured, create a draft, send it, then verify. Only a fresh matching PayPal response can yield `VERIFIED_PAID`.

A failed refresh hides old financial values. An uncertain payment request displays an honest error; refresh and reconcile rather than generating a new operation key. Partial, offline-marked, refunded, and unresolved entries do not contribute to verified recovered cash.
