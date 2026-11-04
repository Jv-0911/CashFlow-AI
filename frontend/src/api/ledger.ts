import { apiClient, getSession, type ApiResponse } from './client.ts';
import type { LedgerEntry, LedgerResponse, LedgerSummary } from '../types/ledger.ts';
import {
  calculateLedgerSummary,
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

/** Fetch the authorized ledger; errors never become fixture payments. */
export async function getLedgerEntries(): Promise<ApiResponse<LedgerResponse>> {
  const session=await getSession();
  if(session.read_only_demo && !session.authenticated) return {data:{entries:[],summary:calculateLedgerSummary([]),currency:'USD',is_demo:true,disclaimer:'Read-only demonstration: administrator access is required for the private payment ledger.'},isDemo:true,status:200};
  const response=await apiClient<BackendLedger>('/api/v1/ledger');
  const raw=response.data;
  if(!raw||!Array.isArray(raw.entries)||!Array.isArray(raw.recovered_cash)||typeof raw.is_demo_data!=='boolean') throw new Error('Malformed ledger response.');
  const entries=raw.entries.map(adaptEntry);
  if(new Set(entries.map(e=>e.ledger_entry_id)).size!==entries.length) throw new Error('Malformed duplicate ledger entries.');
  const summary=calculateLedgerSummary(entries);
  const totals=raw.recovered_cash;
  if(!(entries.length===0 && totals.length===0) && (totals.length!==1||totals[0].currency!=='USD'||totals[0].amount_cents!==summary.verified_recovered_cents)) throw new Error('Ledger total does not match authoritative server evidence.');
  return {data:{entries,summary,currency:'USD',is_demo:raw.is_demo_data,disclaimer:'PayPal Sandbox ledger. Only fresh provider-verified entries count as recovered cash.'},isDemo:raw.is_demo_data,status:response.status};
}
export interface BackendEntry {entry_id:string;amount_cents:number;currency:string;status:string;provider:string;provider_invoice_id:string|null;provider_status:string|null;verified_at:string|null;created_at:string;sequence:number;invoice_url:string|null}
interface BackendLedger {entries:BackendEntry[];recovered_cash:{amount_cents:number;currency:string}[];is_demo_data:boolean}
const statuses:Record<string,LedgerEntry['status']>={PROPOSED:'proposed',APPROVED:'approved',INVOICE_DRAFTED:'invoice_created',INVOICE_SENT:'invoice_sent',PAYMENT_PENDING:'pending_verification',AWAITING_VERIFICATION:'pending_verification',PARTIALLY_PAID:'partially_paid',VERIFIED_PAID:'verified_completed',OFFLINE_MARKED_PAID:'offline_marked_paid',CANCELLED:'cancelled',FAILED:'failed',UNRESOLVED:'unresolved',REFUNDED:'refunded'};
export function adaptEntry(raw:BackendEntry):LedgerEntry {
  if(!raw || typeof raw.entry_id!=='string'||typeof raw.provider!=='string'||typeof raw.created_at!=='string'||!Number.isFinite(Date.parse(raw.created_at))||!Number.isSafeInteger(raw.amount_cents)||raw.amount_cents<=0||raw.currency!=='USD'||!Number.isSafeInteger(raw.sequence)||raw.sequence<1||!Object.hasOwn(statuses,raw.status)) throw new Error('Malformed ledger response entry.');
  if(raw.status==='VERIFIED_PAID'&&(!raw.verified_at||!Number.isFinite(Date.parse(raw.verified_at)))) throw new Error('Malformed payment verification evidence.');
  if(raw.invoice_url){const url=new URL(raw.invoice_url);if(url.protocol!=='https:'||url.username||url.password||!['www.sandbox.paypal.com','sandbox.paypal.com','api-m.sandbox.paypal.com'].includes(url.hostname)) throw new Error('Invalid invoice destination.');}
  return {ledger_entry_id:raw.entry_id,invoice_id:raw.provider_invoice_id??'Not created',amount_cents:raw.amount_cents,currency:raw.currency,status:statuses[raw.status],provider:raw.provider,verified_at:raw.verified_at,created_at:raw.created_at,notes:raw.provider_status??'No provider observation',backend_status:raw.status,sequence:raw.sequence,invoice_url:raw.invoice_url};
}
