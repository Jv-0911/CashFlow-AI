/**
 * Scenario types matching contracts/scenario-request.example.json.
 */

export interface ScenarioRequest {
  /** Business identifier */
  business_id: string;
  /** Number of days to forecast */
  forecast_days: number;
  /** Safety reserve threshold in integer cents */
  safety_reserve_cents: number;
  /** Evidence/transaction IDs to consider */
  evidence_ids: string[];
  /** ISO 4217 currency code */
  currency: string;
}

/** Scenario comparison result (frontend-side structure for display) */
export interface ScenarioComparison {
  baseline_ending_balance_cents: number;
  scenario_ending_balance_cents: number;
  baseline_breach_date: string | null;
  scenario_breach_date: string | null;
  changes_applied: string[];
  net_variance_cents?: number;
  baseline_min_balance_cents?: number;
  scenario_min_balance_cents?: number;
  shortfall_change_cents?: number;
}

export type ScenarioPresetId =
  | 'delayed_receivables'
  | 'headcount_expansion'
  | 'vendor_price_hike'
  | 'revenue_dip'
  | 'custom';

export interface ScenarioModifiers {
  preset_id?: ScenarioPresetId;
  receipts_modifier_pct: number;
  expenses_modifier_pct: number;
  delayed_receivables_days: number;
  lump_sum_expense_cents: number;
  lump_sum_date?: string | null;
  /** Recurring monthly payroll addition in integer cents */
  recurring_payroll_cents?: number;
}


export interface ScenarioResponse {
  currency: string;
  safety_reserve_cents: number;
  first_reserve_breach_date: string | null;
  days: import('./forecast').ForecastDay[];
  comparison: ScenarioComparison;
  is_demo?: boolean;
  disclaimer?: string;
  backend_unavailable?: boolean;
}
