/**
 * Ledger types matching contracts/payment-ledger.example.json.
 *
 * Payment statuses must reflect the actual provider-verified state.
 * The frontend must never show a payment as verified solely because
 * a UI action was performed.
 */

export type LedgerStatus =
  | 'proposed'
  | 'invoice_created'
  | 'invoice_sent'
  | 'pending_verification'
  | 'verified_completed'
  | 'failed'
  | 'cancelled'
  | 'expired';

export interface LedgerEntry {
  /** Unique ledger entry identifier */
  ledger_entry_id: string;
  /** Associated invoice identifier */
  invoice_id: string;
  /** Amount in integer cents */
  amount_cents: number;
  /** ISO 4217 currency code */
  currency: string;
  /** Current application status */
  status: LedgerStatus;
  /** Payment provider (e.g. "paypal_sandbox") */
  provider: string;
  /** ISO 8601 timestamp when payment was verified, or null */
  verified_at: string | null;
}
