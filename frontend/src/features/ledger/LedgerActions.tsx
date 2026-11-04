/** Commands inside Member 4's ledger. All authority remains on the backend. */
import { useEffect, useState } from 'react';
import { apiClient, getSession } from '../../api/client';
import { useAuth } from '../../context';
import type { LedgerEntry } from '../../types/ledger';
import { formatCents } from '../../utils/currency';

interface Receivable { id: string; customer: string; amount_cents: number; ledger_entry: unknown }
export function LedgerActions({ entry, onChanged }: { entry?: LedgerEntry; onChanged: (notice?: string) => Promise<void> }) {
  const { serverAuthenticated } = useAuth();
  const [enabled, setEnabled] = useState(false);
  const [sources, setSources] = useState<Receivable[]>([]);
  const [selected, setSelected] = useState('');
  const [approved, setApproved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    if (serverAuthenticated) {
      getSession().then(s => { if(active) setEnabled(s.payments_enabled); }).catch(() => { if(active) setError('Payment configuration could not be loaded.'); });
      if (!entry) apiClient<{receivables: Receivable[]}>('/api/v1/dashboard').then(r => {
        if(active) {setSources(r.data.receivables); setSelected(r.data.receivables.find(x => !x.ledger_entry)?.id ?? '');}
      }).catch(() => {if(active) setError('Receivables could not be loaded.');});
    }
    return () => { active = false; };
  }, [serverAuthenticated, entry]);
  if (!serverAuthenticated) return null;
  async function command(path: string, body?: object) {
    if(busy) return;
    setBusy(true); setError('');
    try {
      const result = await apiClient<{results?: {error_code: string | null}[]}>(path, {method:'POST', ...(body ? {body:JSON.stringify(body)} : {})});
      const notice = result.data.results?.some(r => r.error_code)
        ? 'Some invoices remain unresolved. Refresh their status before retrying.' : undefined;
      // The page owns this notice because refresh unmounts these controls.
      await onChanged(notice);
    } catch(err) {setError(err instanceof Error ? err.message : 'Action failed. Refresh the ledger before retrying.');}
    finally {setBusy(false);}
  }
  const id = entry ? encodeURIComponent(entry.ledger_entry_id) : '';
  return <section className="drawer-governance-box" aria-label="Payment actions">
    <h3>PayPal Sandbox actions</h3>
    {!enabled && <p>PayPal is not configured. Proposals and approvals can be recorded; invoice creation, sending and verification remain unavailable.</p>}
    {error && <p role="alert">{error}</p>}
    {!entry ? <>
      <label htmlFor="recovery-source">Business receivable to propose</label>
      <select id="recovery-source" value={selected} onChange={e=>setSelected(e.target.value)} disabled={busy}>
        <option value="">Select a receivable</option>
        {sources.filter(x=>!x.ledger_entry).map(x=><option key={x.id} value={x.id}>{x.customer || x.id} — {formatCents(x.amount_cents,'USD')}</option>)}
      </select>
      <button className="drawer-btn-secondary" disabled={busy || !selected} onClick={()=>command('/api/v1/ledger/proposals',{receivable_id:selected})}>Record proposal</button>
      <button className="drawer-btn-secondary" disabled={busy || !enabled} onClick={()=>command('/api/v1/payments/reconcile')}>Reconcile uncertain invoices</button>
    </> : <>
      {entry.backend_status === 'PROPOSED' && <>
        <label><input type="checkbox" checked={approved} onChange={e=>setApproved(e.target.checked)} disabled={busy}/> I approve {formatCents(entry.amount_cents,entry.currency)} for the configured Sandbox test payer. This records approval only.</label>
        <button className="drawer-btn-secondary" disabled={busy || !approved} onClick={()=>command(`/api/v1/ledger/${id}/approve`,{expected_sequence:entry.sequence,confirmed:true})}>Record human approval</button>
      </>}
      {entry.backend_status === 'APPROVED' && <button className="drawer-btn-secondary" disabled={busy || !enabled} onClick={()=>command('/api/v1/invoices',{entry_id:entry.ledger_entry_id})}>Create invoice draft</button>}
      {entry.backend_status === 'INVOICE_DRAFTED' && <button className="drawer-btn-secondary" disabled={busy || !enabled} onClick={()=>command(`/api/v1/invoices/${id}/send`)}>Send approved invoice</button>}
      {entry.invoice_id !== 'Not created' && <button className="drawer-btn-secondary" disabled={busy || !enabled} onClick={()=>command(`/api/v1/payments/${id}/verify`)}>Verify with PayPal</button>}
      {entry.invoice_url && <a href={entry.invoice_url} target="_blank" rel="noreferrer noopener">Open Sandbox invoice</a>}
    </>}
    <p>Only a fresh server-side PayPal response can confirm payment. A proposal, approval or browser redirect is never recovered cash.</p>
  </section>;
}
