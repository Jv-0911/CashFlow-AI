/**
 * Forecast types matching contracts/forecast-response.example.json
 * and backend/app/api/schemas.py (ForecastDay, ForecastResponse).
 *
 * All monetary amounts are in integer cents to match the backend contract.
 */

export interface ForecastDay {
  /** ISO 8601 date string, e.g. "2026-10-10" */
  date: string;
  /** Opening cash balance in integer cents */
  opening_balance_cents: number;
  /** Projected incoming cash receipts in integer cents */
  receipts_cents: number;
  /** Projected outgoing cash expenses in integer cents */
  expenses_cents: number;
  /** Projected closing cash balance in integer cents */
  closing_balance_cents: number;
}

export interface ForecastResponse {
  /** ISO 4217 currency code */
  currency: string;
  /** Configured safety reserve threshold in integer cents */
  safety_reserve_cents: number;
  /** First ISO 8601 date when closing balance drops below safety reserve, or null */
  first_reserve_breach_date: string | null;
  /** List of daily cash-flow forecast projections */
  days: ForecastDay[];
  /** Explicit flag indicating this response is demo fixture data */
  is_demo: boolean;
  /** Notice confirming no business calculations have been performed */
  disclaimer: string;
}
