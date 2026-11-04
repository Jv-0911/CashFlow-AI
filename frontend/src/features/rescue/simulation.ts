import type { ForecastDay } from '../../types';
import type { RescueAction } from '../../types';

export interface SimulatedForecastDay extends ForecastDay {
  simulated_closing_balance_cents: number;
  simulated_cumulative_impact_cents: number;
}

export interface SimulationResult {
  simulatedDays: SimulatedForecastDay[];
  originalMinBalanceCents: number;
  simulatedMinBalanceCents: number;
  safetyReserveCents: number;
  originalShortfallCents: number;
  simulatedShortfallCents: number;
  shortfallRecoveredCents: number;
  isBreachResolved: boolean;
  totalEstimatedImpactCents: number;
  activeAssumptions: string[];
  simulatedActionsCount: number;
  disclaimer: string;
}

export const HYPOTHETICAL_SIMULATION_DISCLAIMER =
  'HYPOTHETICAL SIMULATION PREVIEW: Projections are analytical mathematical models based on stated assumptions and do not represent actual cash movements, settled transactions, or restored bank reserves.';

/**
 * Runs a deterministic financial recovery simulation on forecast days in strict integer cents.
 *
 * Timing Rule:
 * An action's estimated liquidity impact is applied starting on its effective day
 * (based on breach date alignment and timing_days_offset), rolling forward into subsequent
 * cumulative closing balances. It is NEVER blindly added to historical or prior forecast days.
 */
export function runRecoverySimulation(
  days: ForecastDay[],
  safetyReserveCents: number,
  selectedActions: RescueAction[],
  breachDateStr: string | null
): SimulationResult {
  if (!days || days.length === 0) {
    return {
      simulatedDays: [],
      originalMinBalanceCents: 0,
      simulatedMinBalanceCents: 0,
      safetyReserveCents,
      originalShortfallCents: 0,
      simulatedShortfallCents: 0,
      shortfallRecoveredCents: 0,
      isBreachResolved: true,
      totalEstimatedImpactCents: 0,
      activeAssumptions: [],
      simulatedActionsCount: 0,
      disclaimer: HYPOTHETICAL_SIMULATION_DISCLAIMER,
    };
  }

  // Find breach day index if date is provided
  let breachDayIndex = -1;
  if (breachDateStr) {
    breachDayIndex = days.findIndex((d) => d.date === breachDateStr);
  }
  if (breachDayIndex === -1) {
    // If not matching by date string, check first day where closing balance < reserve
    breachDayIndex = days.findIndex((d) => d.closing_balance_cents < safetyReserveCents);
  }

  // Determine effective start day index for each selected action
  // Default to day index 0 if no breach, or breach index + timing offset (bounded within horizon)
  const actionTimingMap = selectedActions.map((action) => {
    const offset = typeof action.timing_days_offset === 'number' ? action.timing_days_offset : 1;
    let effectiveIndex = 0;
    if (breachDayIndex !== -1) {
      effectiveIndex = Math.max(0, Math.min(days.length - 1, breachDayIndex + offset - 1));
    } else {
      effectiveIndex = Math.max(0, Math.min(days.length - 1, offset - 1));
    }
    return {
      actionId: action.action_id,
      effectiveDayIndex: effectiveIndex,
      impactCents: Math.round(action.estimated_impact_cents),
      assumptions: action.assumptions || [],
    };
  });

  // Calculate cumulative impacts day-by-day
  let originalMin = days[0].closing_balance_cents;
  let simulatedMin = days[0].closing_balance_cents;

  const simulatedDays: SimulatedForecastDay[] = days.map((day, dayIdx) => {
    if (day.closing_balance_cents < originalMin) {
      originalMin = day.closing_balance_cents;
    }

    // Cumulative sum of impacts whose effective day <= dayIdx
    let cumulativeImpactCents = 0;
    for (const item of actionTimingMap) {
      if (dayIdx >= item.effectiveDayIndex) {
        cumulativeImpactCents += item.impactCents;
      }
    }

    const simClosing = Math.round(day.closing_balance_cents + cumulativeImpactCents);

    if (simClosing < simulatedMin) {
      simulatedMin = simClosing;
    }

    return {
      ...day,
      simulated_closing_balance_cents: simClosing,
      simulated_cumulative_impact_cents: cumulativeImpactCents,
    };
  });

  // Original and simulated shortfalls in integer cents
  const originalShortfall = Math.max(0, Math.round(safetyReserveCents - originalMin));
  const simulatedShortfall = Math.max(0, Math.round(safetyReserveCents - simulatedMin));
  const shortfallRecovered = Math.max(0, originalShortfall - simulatedShortfall);

  // Collect unique assumptions from all selected actions
  const activeAssumptions: string[] = [];
  const assumptionSet = new Set<string>();
  for (const item of actionTimingMap) {
    for (const a of item.assumptions) {
      if (!assumptionSet.has(a)) {
        assumptionSet.add(a);
        activeAssumptions.push(a);
      }
    }
  }

  const totalEstimatedImpactCents = actionTimingMap.reduce(
    (sum, item) => sum + item.impactCents,
    0
  );

  return {
    simulatedDays,
    originalMinBalanceCents: originalMin,
    simulatedMinBalanceCents: simulatedMin,
    safetyReserveCents,
    originalShortfallCents: originalShortfall,
    simulatedShortfallCents: simulatedShortfall,
    shortfallRecoveredCents: shortfallRecovered,
    isBreachResolved: simulatedMin >= safetyReserveCents,
    totalEstimatedImpactCents,
    activeAssumptions,
    simulatedActionsCount: selectedActions.length,
    disclaimer: HYPOTHETICAL_SIMULATION_DISCLAIMER,
  };
}
