import { test, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { adaptEntry, getLedgerEntries, type BackendEntry } from '../ledger.ts';
import { getForecast } from '../forecast.ts';
import { getRescue } from '../rescue.ts';
import { calculateLedgerSummary } from '../../features/ledger/ledger-math.ts';
import { apiClient } from '../client.ts';

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });
const entry: BackendEntry = {entry_id:'entry_fixture',amount_cents:320000,currency:'USD',status:'PAYMENT_PENDING',provider:'paypal_sandbox',provider_invoice_id:'INV2-FIXTURE',provider_status:'PAYMENT_PENDING',verified_at:null,created_at:'2026-11-02T10:00:00Z',sequence:4,invoice_url:null};
function respond(data: unknown, status=200) { return new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}}); }
function scriptLedger(data: unknown) {
  globalThis.fetch = async input => String(input).endsWith('/session') ? respond({authenticated:true,read_only_demo:false,password_configured:true,payments_enabled:false,csrf_token:'test-csrf'}) : respond(data);
}
test('all unverified provider states stay excluded from recovered cash', () => {
  for(const status of ['PROPOSED','APPROVED','INVOICE_DRAFTED','INVOICE_SENT','PAYMENT_PENDING','AWAITING_VERIFICATION','PARTIALLY_PAID','OFFLINE_MARKED_PAID','CANCELLED','FAILED','UNRESOLVED','REFUNDED']) {
    const mapped=adaptEntry({...entry,status,verified_at:'2026-11-02T12:00:00Z'});
    assert.equal(calculateLedgerSummary([mapped]).verified_recovered_cents,0,status);
  }
  assert.throws(()=>adaptEntry({...entry,status:'PAID'}),/Malformed/);
  assert.throws(()=>adaptEntry({...entry,status:'VERIFIED_PAID'}),/evidence/);
});
test('server total and verified evidence must agree', async () => {
  const paid={...entry,status:'VERIFIED_PAID',verified_at:'2026-11-02T12:00:00Z'};
  scriptLedger({entries:[paid],recovered_cash:[{currency:'USD',amount_cents:320000}],is_demo_data:true});
  assert.equal((await getLedgerEntries()).data.summary.verified_recovered_cents,320000);
  scriptLedger({entries:[entry],recovered_cash:[{currency:'USD',amount_cents:320000}],is_demo_data:true});
  await assert.rejects(getLedgerEntries(),/authoritative/);
  scriptLedger({entries:[entry,entry],recovered_cash:[{currency:'USD',amount_cents:0}],is_demo_data:true});
  await assert.rejects(getLedgerEntries(),/duplicate/);
});
test('invalid money and invoice destinations fail closed', () => {
  for(const amount of [0,-1,1.5,Number.MAX_SAFE_INTEGER+1]) assert.throws(()=>adaptEntry({...entry,amount_cents:amount}));
  for(const url of ['http://sandbox.paypal.com/a','https://paypal.com/a','https://sandbox.paypal.com.evil.test/a','https://user@sandbox.paypal.com/a']) assert.throws(()=>adaptEntry({...entry,invoice_url:url}));
});
test('unauthorized and unavailable responses never become fixture financial results', async () => {
  for(const status of [401,403,429,500,503]) {
    globalThis.fetch=async()=>respond({error:{message:'Unavailable'}},status);
    await assert.rejects(getLedgerEntries());
    await assert.rejects(getForecast());
    await assert.rejects(getRescue());
  }
});
test('forecast adapter rejects broken arithmetic instead of plotting it', async () => {
  globalThis.fetch=async()=>respond({currency:'USD',safety_reserve_cents:100,days:[{date:'2026-11-02',opening_balance_cents:100,receipts_cents:50,expenses_cents:0,closing_balance_cents:200}]});
  await assert.rejects(getForecast());
});
test('write transport sends in-memory CSRF token and same-origin cookie policy', async () => {
  const seen: RequestInit[]=[];
  globalThis.fetch=async (input, options)=>{
    if(String(input).endsWith('/session')) return respond({authenticated:true,read_only_demo:false,password_configured:true,payments_enabled:false,csrf_token:'test-csrf'});
    seen.push(options!);return respond({ok:true});
  };
  await apiClient('/api/v1/ledger/proposals',{method:'POST',body:JSON.stringify({receivable_id:'fixture'})});
  assert.equal(seen[0].credentials,'same-origin');
  assert.equal(new Headers(seen[0].headers).get('X-CSRF-Token'),'test-csrf');
  await assert.rejects(apiClient('https://external.test/api/v1/ledger'),/Unsupported/);
});

test('a new empty ledger is valid and has zero recovered cash', async () => {
  scriptLedger({entries:[],recovered_cash:[],is_demo_data:true});
  const result=await getLedgerEntries();
  assert.equal(result.data.entries.length,0);
  assert.equal(result.data.summary.verified_recovered_cents,0);
});
