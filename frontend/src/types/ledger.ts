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
  /** ISO 8601 creation timestamp, if available */
  created_at?: string | null;
  /** Explicit descriptor or audit label */
  notes?: string | null;
}

export interface LedgerSummary {
  verified_recovered_cents: number;
  pending_verification_cents: number;
  unresolved_failed_cents: number;
  total_tracked_cents: number;
  total_entries: number;
  verified_entries: number;
  pending_entries: number;
  unresolved_entries: number;
}

export interface LedgerResponse {
  entries: LedgerEntry[];
  summary: LedgerSummary;
  currency: string;
  is_demo?: boolean;
  disclaimer?: string;
  backend_unavailable?: boolean;
}
