import type { ForecastDay } from '../../types/forecast.ts';
import type { LedgerEntry } from '../../types/ledger.ts';
import { isStrictlyVerified } from '../ledger/ledger-math.ts';

export interface CashFlowAnalyticsResult {
  /** Total projected cash inflow in integer cents across the period */
  total_inflow_cents: number;
  /** Total projected cash outflow (expenses) in integer cents across the period */
  total_outflow_cents: number;
  /** Net cash flow (inflow - outflow) in integer cents */
  net_cash_flow_cents: number;
  /** Average daily cash inflow in integer cents */
  avg_daily_inflow_cents: number;
  /** Average daily cash burn (expenses) in integer cents */
  avg_daily_burn_cents: number;
  /** Net daily burn delta (avg inflow - avg burn) in integer cents */
  net_daily_delta_cents: number;
  /** Estimated days until cash reaches zero based on current burn rate, or null if burn <= 0 */
  runway_zero_days: number | null;
  /** Estimated days until cash breaches safety reserve, or null if burn <= 0 (0 if already breached) */
  runway_reserve_breach_days: number | null;
  /** Earliest calendar date when closing balance drops below safety reserve */
  earliest_forecast_breach_date: string | null;
  /** Lowest closing balance projected in the period in integer cents */
  min_projected_balance_cents: number;
  /** Highest closing balance projected in the period in integer cents */
  max_projected_balance_cents: number;
  /** Current closing cash balance at the end of the period */
  current_balance_cents: number;
  /** Configured safety reserve target in integer cents */
  safety_reserve_cents: number;
  /** Total days in analyzed horizon */
  horizon_days: number;
  /** Verified recovered cash from provider-verified ledger in integer cents */
  verified_recovered_cents: number;
  /** Total tracked pipeline volume from ledger in integer cents */
  total_tracked_ledger_cents: number;
  /** Recovery conversion percentage, or null if total tracked is 0 */
  recovery_efficiency_pct: number | null;
}

/**
 * Computes deterministic cash-flow analytics and performance metrics.
 *
 * Rules:
 * 1. Strict integer cents for all monetary values (Math.round avoids floating-point drift).
 * 2. Does not mutate the input forecast days or ledger entries.
 * 3. Handles zero/negative burn rates, empty arrays, and edge cases safely.
 * 4. Separates runway until zero cash from runway until safety reserve breach.
 * 5. Recovery efficiency calculates strictly from provider-verified ledger entries.
 */
export function calculateCashFlowAnalytics(
  days: ForecastDay[] = [],
  safetyReserveCents = 100000,
  ledgerEntries: LedgerEntry[] = []
): CashFlowAnalyticsResult {
  const safeReserve = Math.max(0, Math.round(safetyReserveCents || 0));

  if (!days || days.length === 0) {
    return {
      total_inflow_cents: 0,
      total_outflow_cents: 0,
      net_cash_flow_cents: 0,
      avg_daily_inflow_cents: 0,
      avg_daily_burn_cents: 0,
      net_daily_delta_cents: 0,
      runway_zero_days: null,
      runway_reserve_breach_days: null,
      earliest_forecast_breach_date: null,
      min_projected_balance_cents: 0,
      max_projected_balance_cents: 0,
      current_balance_cents: 0,
      safety_reserve_cents: safeReserve,
      horizon_days: 0,
      verified_recovered_cents: 0,
      total_tracked_ledger_cents: 0,
      recovery_efficiency_pct: null,
    };
  }

  const horizonDays = days.length;
  let totalInflow = 0;
  let totalOutflow = 0;
  let minBalance = days[0].closing_balance_cents;
  let maxBalance = days[0].closing_balance_cents;
  let earliestBreachDate: string | null = null;

  for (const day of days) {
    const receipts = Math.max(0, Math.round(day.receipts_cents || 0));
    const expenses = Math.max(0, Math.round(day.expenses_cents || 0));
    const closing = Math.round(day.closing_balance_cents || 0);

    totalInflow += receipts;
    totalOutflow += expenses;

    if (closing < minBalance) {
      minBalance = closing;
    }
    if (closing > maxBalance) {
      maxBalance = closing;
    }
    if (!earliestBreachDate && closing < safeReserve) {
      earliestBreachDate = day.date;
    }
  }

  const netCashFlow = totalInflow - totalOutflow;
  const avgDailyInflow = Math.round(totalInflow / horizonDays);
  const avgDailyBurn = Math.round(totalOutflow / horizonDays);
  const netDailyDelta = avgDailyInflow - avgDailyBurn;

  const currentBalance = days[days.length - 1].closing_balance_cents;

  // Runway to zero cash
  // If avg burn is 0 or negative, runway is infinite (sustainable)
  let runwayZeroDays: number | null = null;
  if (avgDailyBurn > 0 && currentBalance > 0) {
    runwayZeroDays = Math.floor(currentBalance / avgDailyBurn);
  } else if (currentBalance <= 0) {
    runwayZeroDays = 0;
  }

  // Runway to safety reserve breach
  let runwayReserveBreachDays: number | null = null;
  if (currentBalance <= safeReserve) {
    runwayReserveBreachDays = 0; // Already breached or at reserve
  } else if (avgDailyBurn > 0) {
    const bufferCents = currentBalance - safeReserve;
    runwayReserveBreachDays = Math.floor(bufferCents / avgDailyBurn);
  }

  // Ledger recovery efficiency calculation
  let verifiedRecoveredCents = 0;
  let totalTrackedLedgerCents = 0;

  for (const entry of ledgerEntries) {
    const amt = Math.max(0, Math.round(entry.amount_cents || 0));
    totalTrackedLedgerCents += amt;
    if (isStrictlyVerified(entry)) {
      verifiedRecoveredCents += amt;
    }
  }

  let recoveryEfficiencyPct: number | null = null;
  if (totalTrackedLedgerCents > 0) {
    recoveryEfficiencyPct = Math.round(
      (verifiedRecoveredCents / totalTrackedLedgerCents) * 100
    );
  }

  return {
    total_inflow_cents: totalInflow,
    total_outflow_cents: totalOutflow,
    net_cash_flow_cents: netCashFlow,
    avg_daily_inflow_cents: avgDailyInflow,
    avg_daily_burn_cents: avgDailyBurn,
    net_daily_delta_cents: netDailyDelta,
    runway_zero_days: runwayZeroDays,
    runway_reserve_breach_days: runwayReserveBreachDays,
    earliest_forecast_breach_date: earliestBreachDate,
    min_projected_balance_cents: minBalance,
    max_projected_balance_cents: maxBalance,
    current_balance_cents: currentBalance,
    safety_reserve_cents: safeReserve,
    horizon_days: horizonDays,
    verified_recovered_cents: verifiedRecoveredCents,
    total_tracked_ledger_cents: totalTrackedLedgerCents,
    recovery_efficiency_pct: recoveryEfficiencyPct,
  };
}

/**
 * Summarizes period-over-period comparison between earlier and later halves of the forecast window.
 */
export function calculatePeriodComparison(days: ForecastDay[] = []) {
  if (!days || days.length < 2) {
    return null;
  }

  const mid = Math.floor(days.length / 2);
  const firstHalf = days.slice(0, mid);
  const secondHalf = days.slice(mid);

  const firstInflows = firstHalf.reduce((sum, d) => sum + d.receipts_cents, 0);
  const firstOutflows = firstHalf.reduce((sum, d) => sum + d.expenses_cents, 0);
  const secondInflows = secondHalf.reduce((sum, d) => sum + d.receipts_cents, 0);
  const secondOutflows = secondHalf.reduce((sum, d) => sum + d.expenses_cents, 0);

  const inflowVarianceCents = secondInflows - firstInflows;
  const outflowVarianceCents = secondOutflows - firstOutflows;

  return {
    first_half_inflow_cents: firstInflows,
    first_half_outflow_cents: firstOutflows,
    second_half_inflow_cents: secondInflows,
    second_half_outflow_cents: secondOutflows,
    inflow_variance_cents: inflowVarianceCents,
    outflow_variance_cents: outflowVarianceCents,
  };
}
