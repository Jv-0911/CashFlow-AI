import type { ForecastResponse, RescueResponse, LedgerEntry, ScenarioRequest } from '../types';

/**
 * Fallback demo fixtures strictly derived from /contracts/*.example.json.
 * These ensure the UI can render realistic, faithful mock states
 * when the backend API is disconnected or running in demo mode.
 */

export const DEMO_FORECAST: ForecastResponse = {
  currency: 'USD',
  safety_reserve_cents: 100000,
  first_reserve_breach_date: null,
  days: [
    {
      date: '2026-10-10',
      opening_balance_cents: 400000,
      receipts_cents: 0,
      expenses_cents: 0,
      closing_balance_cents: 400000,
    },
    {
      date: '2026-10-11',
      opening_balance_cents: 400000,
      receipts_cents: 75000,
      expenses_cents: 20000,
      closing_balance_cents: 455000,
    },
    {
      date: '2026-10-12',
      opening_balance_cents: 455000,
      receipts_cents: 12000,
      expenses_cents: 110000,
      closing_balance_cents: 357000,
    },
    {
      date: '2026-10-13',
      opening_balance_cents: 357000,
      receipts_cents: 180000,
      expenses_cents: 45000,
      closing_balance_cents: 492000,
    },
    {
      date: '2026-10-14',
      opening_balance_cents: 492000,
      receipts_cents: 0,
      expenses_cents: 150000,
      closing_balance_cents: 342000,
    },
    {
      date: '2026-10-15',
      opening_balance_cents: 342000,
      receipts_cents: 95000,
      expenses_cents: 30000,
      closing_balance_cents: 407000,
    },
    {
      date: '2026-10-16',
      opening_balance_cents: 407000,
      receipts_cents: 40000,
      expenses_cents: 50000,
      closing_balance_cents: 397000,
    },
  ],
  is_demo: true,
  disclaimer: 'DEMO FORECAST DATA: The deterministic financial engine will be implemented in backend/app/forecast by Member 1.',
};

export const DEMO_RESCUE: RescueResponse = {
  summary: 'Projected cash may fall below the configured safety reserve.',
  risk_level: 'high',
  evidence_ids: ['txn_demo_001'],
  recommended_actions: [
    {
      action_id: 'action_demo_001',
      title: 'Follow up on an overdue invoice',
      estimated_impact_cents: 50000,
      assumptions: ['The customer pays the invoice in full'],
    },
  ],
};

export const DEMO_SCENARIO_REQUEST: ScenarioRequest = {
  business_id: 'demo_shop_001',
  forecast_days: 30,
  safety_reserve_cents: 100000,
  evidence_ids: ['txn_demo_001'],
  currency: 'USD',
};

export const DEMO_LEDGER_ENTRIES: LedgerEntry[] = [
  {
    ledger_entry_id: 'ledger_demo_001',
    invoice_id: 'invoice_demo_001',
    amount_cents: 50000,
    currency: 'USD',
    status: 'pending_verification',
    provider: 'paypal_sandbox',
    verified_at: null,
  },
];
