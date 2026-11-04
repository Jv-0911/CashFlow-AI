import type { ForecastDay } from '../../types/forecast';
import type { ScenarioModifiers, ScenarioComparison } from '../../types/scenario';

export interface CalculatedScenarioDay extends ForecastDay {
  baseline_closing_cents: number;
  scenario_closing_cents: number;
  variance_cents: number;
  baseline_receipts_cents: number;
  scenario_receipts_cents: number;
  baseline_expenses_cents: number;
  scenario_expenses_cents: number;
  is_scenario_breach: boolean;
  is_baseline_breach: boolean;
}

export interface ScenarioCalculationResult {
  days: CalculatedScenarioDay[];
  comparison: ScenarioComparison;
  uncollected_delayed_receipts_cents: number;
  currency: string;
  safety_reserve_cents: number;
  first_reserve_breach_date: string | null;
  baseline_first_reserve_breach_date: string | null;
  is_demo: boolean;
  disclaimer: string;
}

export const DEMO_SCENARIO_DISCLAIMER =
  'DEMO SCENARIO FALLBACK MODEL: Calculated on the client using isolated deterministic integer-cent arithmetic. Not the authoritative backend deterministic engine.';

/**
 * Calculates a scenario projection from baseline forecast days and modifier parameters.
 *
 * Rules:
 * 1. Strict integer cents throughout (Math.round avoids floating-point drift).
 * 2. Receipts and expenses are bounded at minimum 0 (non-negative).
 * 3. Delayed receivables shift receipts to exact future dates. Receipts shifted
 *    beyond the horizon are tracked as uncollected within the period.
 * 4. Closing balance rolls strictly: closing = opening + receipts - expenses.
 */
export function calculateScenarioProjection(
  baselineDays: ForecastDay[],
  safetyReserveCents: number,
  modifiers: ScenarioModifiers,
  currency = 'USD'
): ScenarioCalculationResult {
  if (!baselineDays || baselineDays.length === 0) {
    return {
      days: [],
      comparison: {
        baseline_ending_balance_cents: 0,
        scenario_ending_balance_cents: 0,
        baseline_breach_date: null,
        scenario_breach_date: null,
        changes_applied: [],
        net_variance_cents: 0,
        baseline_min_balance_cents: 0,
        scenario_min_balance_cents: 0,
        shortfall_change_cents: 0,
      },
      uncollected_delayed_receipts_cents: 0,
      currency,
      safety_reserve_cents: safetyReserveCents,
      first_reserve_breach_date: null,
      baseline_first_reserve_breach_date: null,
      is_demo: true,
      disclaimer: DEMO_SCENARIO_DISCLAIMER,
    };
  }

  const delayDays = Math.max(0, Math.floor(modifiers.delayed_receivables_days || 0));
  const receiptsPct = Math.max(-100, Math.min(200, modifiers.receipts_modifier_pct || 0));
  const expensesPct = Math.max(-100, Math.min(200, modifiers.expenses_modifier_pct || 0));
  const lumpSumCents = Math.max(0, Math.round(modifiers.lump_sum_expense_cents || 0));
  const recurringPayrollCents = Math.max(0, Math.round(modifiers.recurring_payroll_cents || 0));
  const lumpSumDate = modifiers.lump_sum_date || null;

  // Track delayed receipts mapping.
  // Boundary rule: If target index (i + delayDays) >= baselineDays.length,
  // the receipt falls outside the forecast horizon and is tracked as uncollected.
  const shiftedReceiptsMap = new Map<number, number>();
  let uncollectedDelayedCents = 0;

  for (let i = 0; i < baselineDays.length; i++) {
    const origReceipts = baselineDays[i].receipts_cents;
    if (origReceipts <= 0) continue;

    if (delayDays > 0) {
      const targetDayIdx = i + delayDays;
      if (targetDayIdx < baselineDays.length) {
        const currentTarget = shiftedReceiptsMap.get(targetDayIdx) || 0;
        shiftedReceiptsMap.set(targetDayIdx, currentTarget + origReceipts);
      } else {
        // Receipt shifted at or beyond horizon boundary (targetDayIdx >= baselineDays.length)
        uncollectedDelayedCents += origReceipts;
      }
    } else {
      shiftedReceiptsMap.set(i, origReceipts);
    }
  }

  // Determine lump sum target index
  let lumpSumDayIndex = -1;
  if (lumpSumCents > 0) {
    if (lumpSumDate) {
      lumpSumDayIndex = baselineDays.findIndex((d) => d.date === lumpSumDate);
    }
    if (lumpSumDayIndex === -1) {
      // Default to day 0 if date not matching
      lumpSumDayIndex = 0;
    }
  }

  // Human-readable changes applied
  const changesApplied: string[] = [];
  if (receiptsPct !== 0) {
    changesApplied.push(`Receipts adjusted by ${receiptsPct > 0 ? '+' : ''}${receiptsPct}%`);
  }
  if (expensesPct !== 0) {
    changesApplied.push(`Expenses adjusted by ${expensesPct > 0 ? '+' : ''}${expensesPct}%`);
  }
  if (delayDays > 0) {
    changesApplied.push(`Receivables delayed by ${delayDays} day${delayDays > 1 ? 's' : ''}`);
    if (uncollectedDelayedCents > 0) {
      changesApplied.push(
        `Note: Receipts delayed beyond day ${baselineDays.length} fall outside horizon`
      );
    }
  }
  if (recurringPayrollCents > 0) {
    changesApplied.push(
      `Committed recurring payroll added on Day 1 and every 30 calendar days thereafter`
    );
  }
  if (lumpSumCents > 0) {
    changesApplied.push(
      `One-time capex/expense added on ${
        lumpSumDayIndex >= 0 ? baselineDays[lumpSumDayIndex].date : 'Day 1'
      }`
    );
  }
  if (changesApplied.length === 0) {
    changesApplied.push('Baseline (no what-if modifiers applied)');
  }

  // Iterate days and calculate cumulative balances
  let runningScenarioBalance = baselineDays[0].opening_balance_cents;
  let baselineFirstBreachDate: string | null = null;
  let scenarioFirstBreachDate: string | null = null;

  let baselineMinBalance = baselineDays[0].closing_balance_cents;
  let scenarioMinBalance = baselineDays[0].opening_balance_cents;

  const calculatedDays: CalculatedScenarioDay[] = baselineDays.map((baseDay, idx) => {
    // 1. Calculate baseline metrics
    if (baseDay.closing_balance_cents < baselineMinBalance) {
      baselineMinBalance = baseDay.closing_balance_cents;
    }
    if (!baselineFirstBreachDate && baseDay.closing_balance_cents < safetyReserveCents) {
      baselineFirstBreachDate = baseDay.date;
    }

    // 2. Calculate adjusted receipts with documented integer-cent arithmetic:
    // delta = Math.round((cents * pct) / 100), bounded at min 0.
    const baseDayDelayedReceipts = delayDays > 0 ? shiftedReceiptsMap.get(idx) || 0 : baseDay.receipts_cents;
    let finalReceiptsCents = baseDayDelayedReceipts;
    if (receiptsPct !== 0) {
      const receiptsDeltaCents = Math.round((baseDayDelayedReceipts * receiptsPct) / 100);
      finalReceiptsCents = Math.max(0, baseDayDelayedReceipts + receiptsDeltaCents);
    }

    // 3. Calculate adjusted expenses with documented integer-cent arithmetic:
    // delta = Math.round((cents * pct) / 100), bounded at min 0.
    let finalExpensesCents = baseDay.expenses_cents;
    if (expensesPct !== 0) {
      const expensesDeltaCents = Math.round((baseDay.expenses_cents * expensesPct) / 100);
      finalExpensesCents = Math.max(0, baseDay.expenses_cents + expensesDeltaCents);
    }

    // Add recurring monthly payroll on Day 1 and every 30 days
    if (recurringPayrollCents > 0 && idx % 30 === 0) {
      finalExpensesCents += recurringPayrollCents;
    }

    // Add one-time capex on target day
    if (idx === lumpSumDayIndex) {
      finalExpensesCents += lumpSumCents;
    }

    // 4. Calculate scenario closing balance: opening + receipts - expenses
    const scenarioOpeningCents = runningScenarioBalance;
    const scenarioClosingCents = scenarioOpeningCents + finalReceiptsCents - finalExpensesCents;
    runningScenarioBalance = scenarioClosingCents;


    if (idx === 0 || scenarioClosingCents < scenarioMinBalance) {
      scenarioMinBalance = scenarioClosingCents;
    }
    if (!scenarioFirstBreachDate && scenarioClosingCents < safetyReserveCents) {
      scenarioFirstBreachDate = baseDay.date;
    }

    const varianceCents = scenarioClosingCents - baseDay.closing_balance_cents;

    return {
      date: baseDay.date,
      opening_balance_cents: scenarioOpeningCents,
      receipts_cents: finalReceiptsCents,
      expenses_cents: finalExpensesCents,
      closing_balance_cents: scenarioClosingCents,
      baseline_closing_cents: baseDay.closing_balance_cents,
      scenario_closing_cents: scenarioClosingCents,
      variance_cents: varianceCents,
      baseline_receipts_cents: baseDay.receipts_cents,
      scenario_receipts_cents: finalReceiptsCents,
      baseline_expenses_cents: baseDay.expenses_cents,
      scenario_expenses_cents: finalExpensesCents,
      is_baseline_breach: baseDay.closing_balance_cents < safetyReserveCents,
      is_scenario_breach: scenarioClosingCents < safetyReserveCents,
    };
  });

  const baselineEndingCents = baselineDays[baselineDays.length - 1].closing_balance_cents;
  const scenarioEndingCents = calculatedDays[calculatedDays.length - 1].scenario_closing_cents;
  const netVarianceCents = scenarioEndingCents - baselineEndingCents;

  const baselineShortfallCents = Math.max(0, safetyReserveCents - baselineMinBalance);
  const scenarioShortfallCents = Math.max(0, safetyReserveCents - scenarioMinBalance);
  const shortfallChangeCents = scenarioShortfallCents - baselineShortfallCents;

  return {
    days: calculatedDays,
    comparison: {
      baseline_ending_balance_cents: baselineEndingCents,
      scenario_ending_balance_cents: scenarioEndingCents,
      baseline_breach_date: baselineFirstBreachDate,
      scenario_breach_date: scenarioFirstBreachDate,
      changes_applied: changesApplied,
      net_variance_cents: netVarianceCents,
      baseline_min_balance_cents: baselineMinBalance,
      scenario_min_balance_cents: scenarioMinBalance,
      shortfall_change_cents: shortfallChangeCents,
    },
    uncollected_delayed_receipts_cents: uncollectedDelayedCents,
    currency,
    safety_reserve_cents: safetyReserveCents,
    first_reserve_breach_date: scenarioFirstBreachDate,
    baseline_first_reserve_breach_date: baselineFirstBreachDate,
    is_demo: true,
    disclaimer: DEMO_SCENARIO_DISCLAIMER,
  };
}
