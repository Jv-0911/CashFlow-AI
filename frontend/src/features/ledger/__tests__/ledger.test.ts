import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  calculateLedgerSummary,
  filterLedgerEntries,
  getStatusBadgeMetadata,
  isStrictlyVerified,
} from '../ledger-math.ts';
import {
  getLedgerEntries,
  normalizeLedgerResponse,
} from '../../../api/ledger.ts';
import type { LedgerEntry } from '../../../types/ledger.ts';

describe('Payments & Recovery Ledger — Unit & Behavioral Tests', () => {
  const mockEntries: LedgerEntry[] = [
    {
      ledger_entry_id: 'ledger_001',
      invoice_id: 'invoice_001',
      amount_cents: 50000, // $500.00
      currency: 'USD',
      status: 'verified_completed',
      provider: 'paypal_sandbox',
      verified_at: '2026-10-12T14:30:00Z',
      created_at: '2026-10-11T09:00:00Z',
      notes: 'Customer paid invoice #INV-001 in full via PayPal Sandbox',
    },
    {
      ledger_entry_id: 'ledger_002',
      invoice_id: 'invoice_002',
      amount_cents: 75000, // $750.00
      currency: 'USD',
      status: 'pending_verification',
      provider: 'paypal_sandbox',
      verified_at: null,
      created_at: '2026-10-14T10:15:00Z',
      notes: 'Dispatched to customer; awaiting webhook notification',
    },
    {
      ledger_entry_id: 'ledger_003',
      invoice_id: 'invoice_003',
      amount_cents: 120000, // $1,200.00
      currency: 'USD',
      status: 'invoice_sent',
      provider: 'paypal_sandbox',
      verified_at: null,
      created_at: '2026-10-15T11:45:00Z',
      notes: 'Invoice sent to client with net-30 terms',
    },
    {
      ledger_entry_id: 'ledger_004',
      invoice_id: 'invoice_004',
      amount_cents: 35000, // $350.00
      currency: 'USD',
      status: 'failed',
      provider: 'paypal_sandbox',
      verified_at: null,
      created_at: '2026-10-09T16:20:00Z',
      notes: 'Card authorization failed; insufficient funds',
    },
    {
      ledger_entry_id: 'ledger_005',
      invoice_id: 'invoice_005',
      amount_cents: 45000, // $450.00
      currency: 'USD',
      status: 'verified_completed',
      provider: 'paypal_sandbox',
      verified_at: '2026-10-13T16:50:00Z',
      created_at: '2026-10-13T08:10:00Z',
      notes: 'Settlement confirmed by provider',
    },
    {
      ledger_entry_id: 'ledger_006',
      invoice_id: 'invoice_006',
      amount_cents: 60000, // $600.00
      currency: 'USD',
      status: 'cancelled',
      provider: 'paypal_sandbox',
      verified_at: null,
      created_at: '2026-10-08T12:00:00Z',
      notes: 'Customer disputed invoice; cancelled by finance team',
    },
  ];

  // --------------------------------------------------------------------------
  // 1. Integer-Cent Calculations & Verification Rule
  // --------------------------------------------------------------------------
  describe('Integer-Cent Financial Aggregates', () => {
    it('accurately sums verified, pending, and unresolved amounts strictly in integer cents', () => {
      const summary = calculateLedgerSummary(mockEntries);

      // Verified: ledger_001 ($500) + ledger_005 ($450) = $950 (95000 cents)
      assert.equal(summary.verified_recovered_cents, 95000);
      assert.equal(summary.verified_entries, 2);

      // Pending: ledger_002 ($750) + ledger_003 ($1,200) = $1,950 (195000 cents)
      assert.equal(summary.pending_verification_cents, 195000);
      assert.equal(summary.pending_entries, 2);

      // Unresolved: ledger_004 ($350) + ledger_006 ($600) = $950 (95000 cents)
      assert.equal(summary.unresolved_failed_cents, 95000);
      assert.equal(summary.unresolved_entries, 2);

      // Total tracked: 95000 + 195000 + 95000 = 385000 cents ($3,850.00)
      assert.equal(summary.total_tracked_cents, 385000);
      assert.equal(summary.total_entries, 6);
    });

    it('prevents floating-point drift with odd cent amounts', () => {
      const oddEntries: LedgerEntry[] = [
        {
          ledger_entry_id: 'odd_01',
          invoice_id: 'inv_odd_01',
          amount_cents: 33333, // $333.33
          currency: 'USD',
          status: 'verified_completed',
          provider: 'paypal_sandbox',
          verified_at: '2026-10-12T10:00:00Z',
        },
        {
          ledger_entry_id: 'odd_02',
          invoice_id: 'inv_odd_02',
          amount_cents: 11111, // $111.11
          currency: 'USD',
          status: 'verified_completed',
          provider: 'paypal_sandbox',
          verified_at: '2026-10-13T10:00:00Z',
        },
      ];

      const summary = calculateLedgerSummary(oddEntries);
      assert.equal(summary.verified_recovered_cents, 44444);
      assert.equal(Number.isInteger(summary.verified_recovered_cents), true);
      assert.equal(summary.total_tracked_cents, 44444);
    });
  });

  // --------------------------------------------------------------------------
  // 2. Strict Verification Requirements & Timestamp Validation
  // --------------------------------------------------------------------------
  describe('Authoritative Verification Requirements', () => {
    it('isStrictlyVerified accepts only valid parseable timestamps', () => {
      // Valid ISO timestamp
      assert.equal(
        isStrictlyVerified({
          ledger_entry_id: 'v1',
          invoice_id: 'inv_v1',
          amount_cents: 1000,
          currency: 'USD',
          status: 'verified_completed',
          provider: 'paypal_sandbox',
          verified_at: '2026-10-12T14:30:00Z',
        }),
        true
      );

      // Valid date only
      assert.equal(
        isStrictlyVerified({
          ledger_entry_id: 'v2',
          invoice_id: 'inv_v2',
          amount_cents: 1000,
          currency: 'USD',
          status: 'verified_completed',
          provider: 'paypal_sandbox',
          verified_at: '2026-10-12',
        }),
        true
      );
    });

    it('rejects invalid date strings, whitespace, null, and missing timestamps', () => {
      // Invalid date string
      assert.equal(
        isStrictlyVerified({
          ledger_entry_id: 'inv_d1',
          invoice_id: 'i1',
          amount_cents: 1000,
          currency: 'USD',
          status: 'verified_completed',
          provider: 'paypal_sandbox',
          verified_at: 'not-a-valid-date',
        }),
        false
      );

      // Nonsense date string
      assert.equal(
        isStrictlyVerified({
          ledger_entry_id: 'inv_d2',
          invoice_id: 'i2',
          amount_cents: 1000,
          currency: 'USD',
          status: 'verified_completed',
          provider: 'paypal_sandbox',
          verified_at: 'invalid',
        }),
        false
      );

      // Whitespace only
      assert.equal(
        isStrictlyVerified({
          ledger_entry_id: 'inv_d3',
          invoice_id: 'i3',
          amount_cents: 1000,
          currency: 'USD',
          status: 'verified_completed',
          provider: 'paypal_sandbox',
          verified_at: '    ',
        }),
        false
      );

      // Null timestamp
      assert.equal(
        isStrictlyVerified({
          ledger_entry_id: 'inv_d4',
          invoice_id: 'i4',
          amount_cents: 1000,
          currency: 'USD',
          status: 'verified_completed',
          provider: 'paypal_sandbox',
          verified_at: null,
        }),
        false
      );
    });

    it('never counts verified_completed with invalid timestamp into verified recovered cash', () => {
      const corruptEntries: LedgerEntry[] = [
        {
          ledger_entry_id: 'corrupt_1',
          invoice_id: 'inv_c1',
          amount_cents: 100000, // $1,000.00
          currency: 'USD',
          status: 'verified_completed',
          provider: 'paypal_sandbox',
          verified_at: 'corrupt-string',
        },
        {
          ledger_entry_id: 'corrupt_2',
          invoice_id: 'inv_c2',
          amount_cents: 50000, // $500.00
          currency: 'USD',
          status: 'verified_completed',
          provider: 'paypal_sandbox',
          verified_at: '   ',
        },
      ];

      const summary = calculateLedgerSummary(corruptEntries);

      // Both corrupt entries must be excluded from verified cash
      assert.equal(summary.verified_recovered_cents, 0);
      assert.equal(summary.verified_entries, 0);

      // Both should be routed into pending
      assert.equal(summary.pending_verification_cents, 150000);
      assert.equal(summary.pending_entries, 2);
    });

    it('never counts proposed, pending, invoice_sent, failed, or cancelled as verified', () => {
      const pendingAndFailedEntries: LedgerEntry[] = [
        {
          ledger_entry_id: 'e1',
          invoice_id: 'i1',
          amount_cents: 50000,
          currency: 'USD',
          status: 'proposed',
          provider: 'paypal_sandbox',
          verified_at: null,
        },
        {
          ledger_entry_id: 'e2',
          invoice_id: 'i2',
          amount_cents: 50000,
          currency: 'USD',
          status: 'invoice_created',
          provider: 'paypal_sandbox',
          verified_at: null,
        },
        {
          ledger_entry_id: 'e3',
          invoice_id: 'i3',
          amount_cents: 50000,
          currency: 'USD',
          status: 'pending_verification',
          provider: 'paypal_sandbox',
          verified_at: null,
        },
        {
          ledger_entry_id: 'e4',
          invoice_id: 'i4',
          amount_cents: 50000,
          currency: 'USD',
          status: 'expired',
          provider: 'paypal_sandbox',
          verified_at: null,
        },
      ];

      const summary = calculateLedgerSummary(pendingAndFailedEntries);
      assert.equal(summary.verified_recovered_cents, 0);
      assert.equal(summary.verified_entries, 0);
    });
  });

  // --------------------------------------------------------------------------
  // 3. Filtering & Search Matching
  // --------------------------------------------------------------------------
  describe('Filtering & Search Logic', () => {
    it('filters by category tab accurately using strict verification helper', () => {
      // Tab: verified_completed
      const verifiedOnly = filterLedgerEntries(mockEntries, 'verified_completed', '');
      assert.equal(verifiedOnly.length, 2);
      assert.ok(verifiedOnly.every((e) => isStrictlyVerified(e)));

      // Tab: pending_verification
      const pendingOnly = filterLedgerEntries(mockEntries, 'pending_verification', '');
      assert.equal(pendingOnly.length, 1);
      assert.equal(pendingOnly[0].ledger_entry_id, 'ledger_002');

      // Tab: invoices
      const invoicesOnly = filterLedgerEntries(mockEntries, 'invoices', '');
      assert.equal(invoicesOnly.length, 1);
      assert.equal(invoicesOnly[0].ledger_entry_id, 'ledger_003');

      // Tab: unresolved
      const unresolvedOnly = filterLedgerEntries(mockEntries, 'unresolved', '');
      assert.equal(unresolvedOnly.length, 2);
      assert.ok(unresolvedOnly.some((e) => e.status === 'failed'));
      assert.ok(unresolvedOnly.some((e) => e.status === 'cancelled'));

      // Tab: all
      const allEntries = filterLedgerEntries(mockEntries, 'all', '');
      assert.equal(allEntries.length, 6);
    });

    it('searches by invoice_id, ledger_entry_id, provider, and notes case-insensitively', () => {
      // Search by invoice ID
      const byInvoice = filterLedgerEntries(mockEntries, 'all', 'INVOICE_001');
      assert.equal(byInvoice.length, 1);
      assert.equal(byInvoice[0].ledger_entry_id, 'ledger_001');

      // Search by ledger entry ID
      const byLedgerId = filterLedgerEntries(mockEntries, 'all', 'ledger_004');
      assert.equal(byLedgerId.length, 1);
      assert.equal(byLedgerId[0].status, 'failed');

      // Search by notes keyword
      const byNotes = filterLedgerEntries(mockEntries, 'all', 'disputed');
      assert.equal(byNotes.length, 1);
      assert.equal(byNotes[0].ledger_entry_id, 'ledger_006');

      // Unmatched search query
      const noMatch = filterLedgerEntries(mockEntries, 'all', 'non_existent_reference_xyz');
      assert.equal(noMatch.length, 0);
    });
  });

  // --------------------------------------------------------------------------
  // 4. Status Badging & Display Metadata
  // --------------------------------------------------------------------------
  describe('Status Badge Metadata', () => {
    it('returns verified variant when status is verified_completed with valid timestamp', () => {
      const meta = getStatusBadgeMetadata('verified_completed', '2026-10-12T14:30:00Z');
      assert.equal(meta.variant, 'verified');
      assert.equal(meta.isVerified, true);
      assert.equal(meta.label, 'Verified Completed');
    });

    it('returns pending variant when verified_completed is missing or has invalid timestamp', () => {
      const nullMeta = getStatusBadgeMetadata('verified_completed', null);
      assert.equal(nullMeta.variant, 'pending');
      assert.equal(nullMeta.isVerified, false);
      assert.equal(nullMeta.label, 'Awaiting Proof');

      const invalidMeta = getStatusBadgeMetadata('verified_completed', 'not-a-date');
      assert.equal(invalidMeta.variant, 'pending');
      assert.equal(invalidMeta.isVerified, false);
      assert.equal(invalidMeta.label, 'Awaiting Proof');
    });

    it('returns appropriate variants for remaining statuses', () => {
      assert.equal(getStatusBadgeMetadata('pending_verification', null).variant, 'pending');
      assert.equal(getStatusBadgeMetadata('invoice_sent', null).variant, 'invoice');
      assert.equal(getStatusBadgeMetadata('invoice_created', null).variant, 'invoice');
      assert.equal(getStatusBadgeMetadata('failed', null).variant, 'failed');
      assert.equal(getStatusBadgeMetadata('cancelled', null).variant, 'failed');
      assert.equal(getStatusBadgeMetadata('expired', null).variant, 'failed');
      assert.equal(getStatusBadgeMetadata('proposed', null).variant, 'proposed');
    });
  });

  // --------------------------------------------------------------------------
  // 5. Response Normalization & Schema Validation
  // --------------------------------------------------------------------------
  describe('API Response Normalization', () => {
    it('normalizes raw array of LedgerEntry items', () => {
      const rawArray = [
        {
          ledger_entry_id: 'arr_01',
          invoice_id: 'inv_01',
          amount_cents: 25000,
          currency: 'USD',
          status: 'verified_completed' as const,
          provider: 'paypal_sandbox',
          verified_at: '2026-10-12T10:00:00Z',
        },
      ];

      const normalized = normalizeLedgerResponse(rawArray, false);
      assert.equal(normalized.entries.length, 1);
      assert.equal(normalized.entries[0].ledger_entry_id, 'arr_01');
      assert.equal(normalized.summary.verified_recovered_cents, 25000);
      assert.equal(normalized.currency, 'USD');
    });

    it('normalizes object with entries array', () => {
      const rawObject = {
        entries: [
          {
            ledger_entry_id: 'obj_01',
            invoice_id: 'inv_02',
            amount_cents: 40000,
            currency: 'USD',
            status: 'pending_verification' as const,
            provider: 'paypal_sandbox',
            verified_at: null,
          },
        ],
        currency: 'USD',
      };

      const normalized = normalizeLedgerResponse(rawObject, true);
      assert.equal(normalized.entries.length, 1);
      assert.equal(normalized.is_demo, true);
      assert.equal(normalized.summary.pending_verification_cents, 40000);
    });

    it('rejects malformed responses without silently converting to empty array', () => {
      assert.throws(() => normalizeLedgerResponse(null), /Malformed ledger response/);
      assert.throws(() => normalizeLedgerResponse('invalid string'), /Malformed ledger response/);
      assert.throws(() => normalizeLedgerResponse({ unexpected_field: 123 }), /Malformed ledger response/);
      assert.throws(() => normalizeLedgerResponse({ entries: 'not-an-array' }), /Malformed ledger response/);
    });
  });

  // --------------------------------------------------------------------------
  // 6. API Fallback & Unmasked Disclaimer Handling
  // --------------------------------------------------------------------------
  describe('API Fallback & Demo Disclaimer Handling', () => {
    it('getLedgerEntries rejects outages instead of inventing demo payments', async () => {
      await assert.rejects(getLedgerEntries(), /Connection interrupted/);
    });
  });

  // --------------------------------------------------------------------------
  // 7. Non-Mutation of Input Collections
  // --------------------------------------------------------------------------
  describe('Immutability & Non-Mutation', () => {
    it('does not mutate the source entries array or entry objects during calculation or filtering', () => {
      const snapshot = JSON.parse(JSON.stringify(mockEntries));

      calculateLedgerSummary(mockEntries);
      filterLedgerEntries(mockEntries, 'verified_completed', 'invoice');
      filterLedgerEntries(mockEntries, 'unresolved', '');

      // Verify deep equality: mockEntries has not been mutated
      assert.deepEqual(mockEntries, snapshot);
    });
  });
});
