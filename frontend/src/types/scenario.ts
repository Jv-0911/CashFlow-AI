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
}
