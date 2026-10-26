import { apiClient, type ApiResponse } from './client.ts';
import type { LedgerEntry, LedgerResponse, LedgerSummary } from '../types/ledger.ts';
import { DEMO_LEDGER_ENTRIES } from '../data/demo-fixtures.ts';
import {
  calculateLedgerSummary,
  DEMO_LEDGER_DISCLAIMER,
} from '../features/ledger/ledger-math.ts';

/**
 * Normalizes raw backend ledger responses into a consistent LedgerResponse structure.
 *
 * Supported formats:
 * 1. Documented object payload: { entries: LedgerEntry[], summary?: LedgerSummary, currency?: string, ... }
 * 2. Raw array payload: LedgerEntry[]
 *
 * Validation:
 * If the response is not an array and does not contain a valid `entries` array (e.g. primitives,
 * empty object without entries, or unexpected JSON schema), an explicit error is thrown.
 * Malformed responses are NEVER silently converted into an empty ledger.
 */
export function normalizeLedgerResponse(
  raw: unknown,
  isDemo = false
): LedgerResponse {
  if (!raw || typeof raw !== 'object') {
    throw new Error('Malformed ledger response: response body must be an object or array.');
  }

  // Case 1: Raw array of entries
  if (Array.isArray(raw)) {
    const entries = raw as LedgerEntry[];
    return {
      entries,
      summary: calculateLedgerSummary(entries),
      currency: entries[0]?.currency || 'USD',
      is_demo: isDemo,
    };
  }

  // Case 2: Object containing entries array
  const rawObj = raw as Record<string, unknown>;
  if (Array.isArray(rawObj.entries)) {
    const entries = rawObj.entries as LedgerEntry[];
    const currency =
      typeof rawObj.currency === 'string'
        ? rawObj.currency
        : entries[0]?.currency || 'USD';
    const summary =
      rawObj.summary && typeof rawObj.summary === 'object'
        ? (rawObj.summary as LedgerSummary)
        : calculateLedgerSummary(entries);

    return {
      entries,
      summary,
      currency,
      is_demo: Boolean(isDemo || rawObj.is_demo),
      disclaimer: typeof rawObj.disclaimer === 'string' ? rawObj.disclaimer : undefined,
      backend_unavailable: Boolean(rawObj.backend_unavailable),
    };
  }

  // Reject malformed objects that lack entries array
  throw new Error(
    'Malformed ledger response: expected array of ledger entries or object with "entries" array.'
  );
}

/**
 * Fetch payments & recovery ledger entries.
 *
 * Requirements:
 * 1. Attempts to query backend route `GET /api/v1/ledger`.
 * 2. Normalizes both `{ entries: [...] }` and `LedgerEntry[]` response formats without
 *    masking malformed payloads.
 * 3. If the backend endpoint is unreachable or returns 404, gracefully falls back
 *    to the grounded demo fixtures matching `contracts/payment-ledger.example.json`.
 * 4. Does not treat client-side filters as authorization boundaries; multi-tenant
 *    isolation must be enforced by the backend before real financial data is rendered.
 * 5. Clearly tags fallback responses with `backend_unavailable: true` and `is_demo: true`
 *    so the UI displays an unmasked disclaimer and retry mechanism.
 */
export async function getLedgerEntries(): Promise<ApiResponse<LedgerResponse>> {
  try {
    const res = await apiClient<unknown>('/api/v1/ledger');
    const normalized = normalizeLedgerResponse(res.data, res.isDemo);
    return {
      data: normalized,
      isDemo: Boolean(normalized.is_demo ?? res.isDemo),
      status: res.status,
    };
  } catch (error) {
    // If the HTTP request succeeded but returned a malformed response, rethrow
    if (error instanceof Error && error.message.startsWith('Malformed ledger response')) {
      throw error;
    }

    console.warn(
      'Backend ledger endpoint (/api/v1/ledger) unavailable. Falling back to demo fixture:',
      error
    );

    const summary = calculateLedgerSummary(DEMO_LEDGER_ENTRIES);

    const fallbackResponse: LedgerResponse = {
      entries: DEMO_LEDGER_ENTRIES,
      summary,
      currency: DEMO_LEDGER_ENTRIES[0]?.currency || 'USD',
      is_demo: true,
      disclaimer: DEMO_LEDGER_DISCLAIMER,
      backend_unavailable: true,
    };

    return {
      data: fallbackResponse,
      isDemo: true,
      status: 200,
    };
  }
}
