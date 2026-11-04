import type { LedgerEntry, LedgerSummary, LedgerStatus } from '../../types/ledger.ts';

export const DEMO_LEDGER_DISCLAIMER =
  'DEMO LEDGER DATA: Conforms strictly to contracts/payment-ledger.example.json. Transactions represent synthetic demo entries; PayPal Sandbox integration will be provided by backend/app/ledger by Member 3.';

/**
 * Assesses whether a ledger entry represents an authoritatively verified cash recovery.
 *
 * Requirements:
 * 1. Status must be exactly 'verified_completed'.
 * 2. verified_at must be a non-empty string.
 * 3. verified_at must parse to a valid calendar timestamp (rejecting invalid date strings, whitespace, null).
 */
export function isStrictlyVerified(entry: LedgerEntry): boolean {
  if (entry.status !== 'verified_completed') return false;
  if (typeof entry.verified_at !== 'string') return false;
  const trimmed = entry.verified_at.trim();
  if (trimmed.length === 0) return false;
  const parsedTime = Date.parse(trimmed);
  return !isNaN(parsedTime);
}

/**
 * Calculates financial aggregates for a collection of ledger entries.
 *
 * Rules:
 * 1. Strictly maintains integer cents (no floating-point drift).
 * 2. Verified Recovered Cash ONLY includes entries passing `isStrictlyVerified(entry)`.
 * 3. Pending, failed, cancelled, expired, proposed entries, or entries with invalid/missing
 *    timestamps must NEVER count as verified recovery.
 */
export function calculateLedgerSummary(entries: LedgerEntry[]): LedgerSummary {
  let verifiedCents = 0;
  let pendingCents = 0;
  let unresolvedCents = 0;
  let verifiedCount = 0;
  let pendingCount = 0;
  let unresolvedCount = 0;

  for (const entry of entries) {
    const amount = Math.max(0, Math.round(entry.amount_cents || 0));

    if (isStrictlyVerified(entry)) {
      verifiedCents += amount;
      verifiedCount++;
    } else if (
      entry.status === 'failed' ||
      entry.status === 'cancelled' ||
      ['expired', 'unresolved', 'offline_marked_paid', 'refunded'].includes(entry.status)
    ) {
      unresolvedCents += amount;
      unresolvedCount++;
    } else {
      // 'pending_verification', 'invoice_sent', 'invoice_created', 'proposed',
      // or unverified 'verified_completed' missing/invalid timestamp
      pendingCents += amount;
      pendingCount++;
    }
  }

  return {
    verified_recovered_cents: verifiedCents,
    pending_verification_cents: pendingCents,
    unresolved_failed_cents: unresolvedCents,
    total_tracked_cents: verifiedCents + pendingCents + unresolvedCents,
    total_entries: entries.length,
    verified_entries: verifiedCount,
    pending_entries: pendingCount,
    unresolved_entries: unresolvedCount,
  };
}

export type LedgerFilterTab =
  | 'all'
  | 'verified_completed'
  | 'pending_verification'
  | 'invoices'
  | 'unresolved';

/**
 * Filter ledger entries by category tab and text search query.
 */
export function filterLedgerEntries(
  entries: LedgerEntry[],
  tab: LedgerFilterTab,
  searchQuery: string
): LedgerEntry[] {
  const query = (searchQuery || '').trim().toLowerCase();

  return entries.filter((entry) => {
    // 1. Tab status match
    if (tab === 'verified_completed') {
      if (!isStrictlyVerified(entry)) return false;
    } else if (tab === 'pending_verification') {
      if (entry.status !== 'pending_verification') return false;
    } else if (tab === 'invoices') {
      if (entry.status !== 'invoice_sent' && entry.status !== 'invoice_created') return false;
    } else if (tab === 'unresolved') {
      if (
        entry.status !== 'failed' &&
        entry.status !== 'cancelled' &&
        !['expired', 'unresolved', 'offline_marked_paid', 'refunded'].includes(entry.status)
      )
        return false;
    }

    // 2. Text search query match (IDs or notes)
    if (query) {
      const entryId = (entry.ledger_entry_id || '').toLowerCase();
      const invoiceId = (entry.invoice_id || '').toLowerCase();
      const provider = (entry.provider || '').toLowerCase();
      const notes = (entry.notes || '').toLowerCase();

      const matches =
        entryId.includes(query) ||
        invoiceId.includes(query) ||
        provider.includes(query) ||
        notes.includes(query);

      if (!matches) return false;
    }

    return true;
  });
}

/**
 * Returns human-readable label and style metadata for a given ledger status.
 */
export function getStatusBadgeMetadata(status: LedgerStatus, verifiedAt: string | null) {
  if (status === 'verified_completed') {
    const isValid =
      typeof verifiedAt === 'string' &&
      verifiedAt.trim().length > 0 &&
      !isNaN(Date.parse(verifiedAt.trim()));

    if (isValid) {
      return {
        label: 'Verified Completed',
        variant: 'verified' as const,
        description: 'Provider-verified settlement completed',
        isVerified: true,
      };
    }
    return {
      label: 'Awaiting Proof',
      variant: 'pending' as const,
      description: 'Marked completed but missing valid provider verification timestamp',
      isVerified: false,
    };
  }

  switch (status) {
    case 'approved':
      return { label: 'Approved', variant: 'pending' as const, description: 'Human approval recorded; no verified payment', isVerified: false };
    case 'partially_paid':
      return { label: 'Partially Paid', variant: 'pending' as const, description: 'Partial payment; excluded from verified recovered cash', isVerified: false };
    case 'offline_marked_paid':
      return { label: 'Offline Marked Paid', variant: 'failed' as const, description: 'Manual marking is not PayPal-verified cash', isVerified: false };
    case 'refunded':
      return { label: 'Refunded', variant: 'failed' as const, description: 'Refunded; excluded from verified recovered cash', isVerified: false };
    case 'unresolved':
      return { label: 'Unresolved', variant: 'failed' as const, description: 'Status requires fresh PayPal verification', isVerified: false };

    case 'pending_verification':
      return {
        label: 'Pending Verification',
        variant: 'pending' as const,
        description: 'Dispatched to provider; server verification pending',
        isVerified: false,
      };
    case 'invoice_sent':
      return {
        label: 'Invoice Sent',
        variant: 'invoice' as const,
        description: 'Invoice issued to client; awaiting payment action',
        isVerified: false,
      };
    case 'invoice_created':
      return {
        label: 'Invoice Created',
        variant: 'invoice' as const,
        description: 'Draft invoice created in sandbox; not yet dispatched',
        isVerified: false,
      };
    case 'proposed':
      return {
        label: 'Proposed Recovery',
        variant: 'proposed' as const,
        description: 'AI-suggested rescue action; not yet issued',
        isVerified: false,
      };
    case 'failed':
      return {
        label: 'Payment Failed',
        variant: 'failed' as const,
        description: 'Card or bank transfer declined by provider',
        isVerified: false,
      };
    case 'cancelled':
      return {
        label: 'Cancelled',
        variant: 'failed' as const,
        description: 'Invoice or payment cancelled by merchant/client',
        isVerified: false,
      };
    case 'expired':
      return {
        label: 'Expired',
        variant: 'failed' as const,
        description: 'Payment window timed out without authorization',
        isVerified: false,
      };
    default:
      return {
        label: status,
        variant: 'pending' as const,
        description: 'Status unrecognized',
        isVerified: false,
      };
  }
}
