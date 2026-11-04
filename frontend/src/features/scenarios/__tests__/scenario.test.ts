import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  calculateScenarioProjection,
  DEMO_SCENARIO_DISCLAIMER,
} from '../scenario-math.ts';
import { simulateScenario } from '../../../api/scenario.ts';
import type { ForecastDay } from '../../../types/forecast.ts';
import type { ScenarioModifiers } from '../../../types/scenario.ts';

describe('Scenario Simulation — Unit & Behavioral Tests', () => {
  const mockBaselineDays: ForecastDay[] = [
    {
      date: '2026-10-10',
      opening_balance_cents: 400000, // $4,000.00
      receipts_cents: 100000,        // $1,000.00
      expenses_cents: 50000,         // $500.00
      closing_balance_cents: 450000, // $4,500.00
    },
    {
      date: '2026-10-11',
      opening_balance_cents: 450000,
      receipts_cents: 50000,         // $500.00
      expenses_cents: 200000,        // $2,000.00
      closing_balance_cents: 300000, // $3,000.00
    },
    {
      date: '2026-10-12',
      opening_balance_cents: 300000,
      receipts_cents: 0,
      expenses_cents: 150000,        // $1,500.00
      closing_balance_cents: 150000, // $1,500.00
    },
    {
      date: '2026-10-13',
      opening_balance_cents: 150000,
      receipts_cents: 0,
      expenses_cents: 100000,        // $1,000.00
      closing_balance_cents: 50000,  // $500.00 (Breach below $1,000 reserve)
    },
  ];

  const safetyReserveCents = 100000; // $1,000.00

  // --------------------------------------------------------------------------
  // 1. Presets & Parameter Validation
  // --------------------------------------------------------------------------
  describe('What-If Presets & Modifiers', () => {
    it('models Revenue Dip preset (-20% receipts) with strict integer-cent math', () => {
      const modifiers: ScenarioModifiers = {
        preset_id: 'revenue_dip',
        receipts_modifier_pct: -20,
        expenses_modifier_pct: 0,
        delayed_receivables_days: 0,
        lump_sum_expense_cents: 0,
      };

      const result = calculateScenarioProjection(
        mockBaselineDays,
        safetyReserveCents,
        modifiers
      );

      // Day 0: 100000 * 0.8 = 80000 receipts (-20000)
      assert.equal(result.days[0].scenario_receipts_cents, 80000);
      assert.equal(result.days[0].scenario_closing_cents, 430000); // 400000 + 80000 - 50000
      assert.equal(result.days[0].variance_cents, -20000);

      // Day 1: 50000 * 0.8 = 40000 receipts (-10000)
      assert.equal(result.days[1].scenario_receipts_cents, 40000);
      assert.equal(result.days[1].scenario_closing_cents, 270000); // 430000 + 40000 - 200000
      assert.equal(result.days[1].variance_cents, -30000); // Cumulative net divergence

      // Total ending balance variance
      const expectedVariance = -30000;
      assert.equal(result.comparison.net_variance_cents, expectedVariance);
      assert.equal(
        result.comparison.scenario_ending_balance_cents,
        50000 + expectedVariance
      );
    });

    it('models Vendor Cost Hike preset (+15% expenses) with integer rounding', () => {
      const modifiers: ScenarioModifiers = {
        preset_id: 'vendor_price_hike',
        receipts_modifier_pct: 0,
        expenses_modifier_pct: 15,
        delayed_receivables_days: 0,
        lump_sum_expense_cents: 0,
      };

      const result = calculateScenarioProjection(
        mockBaselineDays,
        safetyReserveCents,
        modifiers
      );

      // Day 0: expenses 50000 * 1.15 = 57500 (+7500)
      assert.equal(result.days[0].scenario_expenses_cents, 57500);
      assert.equal(result.days[0].scenario_closing_cents, 442500);

      // Day 1: expenses 200000 * 1.15 = 230000 (+30000)
      assert.equal(result.days[1].scenario_expenses_cents, 230000);
    });

    it('models Headcount Expansion preset as recurring monthly payroll', () => {
      const modifiers: ScenarioModifiers = {
        preset_id: 'headcount_expansion',
        receipts_modifier_pct: 0,
        expenses_modifier_pct: 0,
        delayed_receivables_days: 0,
        lump_sum_expense_cents: 0,
        recurring_payroll_cents: 650000, // $6,500.00 / month recurring
      };

      const result = calculateScenarioProjection(
        mockBaselineDays,
        safetyReserveCents,
        modifiers
      );

      // Day 0 has baseline 50000 + 650000 recurring payroll = 700000 expenses
      assert.equal(result.days[0].scenario_expenses_cents, 700000);
      assert.equal(result.days[0].scenario_closing_cents, -200000);
      assert.equal(result.first_reserve_breach_date, '2026-10-10');

      // Test multi-month recurrence (35 days horizon: dispatches on Day 0 and Day 30)
      const multiMonthDays: ForecastDay[] = Array.from({ length: 35 }, (_, idx) => ({
        date: `2026-10-${String(idx + 1).padStart(2, '0')}`,
        opening_balance_cents: 1000000,
        receipts_cents: 100000,
        expenses_cents: 50000,
        closing_balance_cents: 1050000,
      }));

      const multiMonthResult = calculateScenarioProjection(
        multiMonthDays,
        safetyReserveCents,
        modifiers
      );

      // Day 0: expenses + 650000
      assert.equal(multiMonthResult.days[0].scenario_expenses_cents, 700000);
      // Day 1 to 29: normal expenses 50000
      assert.equal(multiMonthResult.days[1].scenario_expenses_cents, 50000);
      assert.equal(multiMonthResult.days[29].scenario_expenses_cents, 50000);
      // Day 30 (month 2 payroll cycle): expenses + 650000 = 700000
      assert.equal(multiMonthResult.days[30].scenario_expenses_cents, 700000);
    });

  });

  // --------------------------------------------------------------------------
  // 2. Delayed Receivables & Horizon Boundaries
  // --------------------------------------------------------------------------
  describe('Delayed Receivables Timing & Horizon Limits', () => {
    it('shifts receipts forward to exact calendar dates without altering total collections within horizon', () => {
      const modifiers: ScenarioModifiers = {
        preset_id: 'delayed_receivables',
        delayed_receivables_days: 1, // Shift by 1 day
        receipts_modifier_pct: 0,
        expenses_modifier_pct: 0,
        lump_sum_expense_cents: 0,
      };

      const result = calculateScenarioProjection(
        mockBaselineDays,
        safetyReserveCents,
        modifiers
      );

      // Day 0 receipts (originally 100000) shifted to Day 1
      assert.equal(result.days[0].scenario_receipts_cents, 0);

      // Day 1 receives Day 0 receipts (100000) + Day 1 receipts (50000) are shifted to Day 2
      assert.equal(result.days[1].scenario_receipts_cents, 100000);

      // Day 2 receives Day 1 receipts (50000)
      assert.equal(result.days[2].scenario_receipts_cents, 50000);

      // Day 3 receives Day 2 receipts (0)
      assert.equal(result.days[3].scenario_receipts_cents, 0);

      // No uncollected receipts lost since max delay is 1 within 4 days
      assert.equal(result.uncollected_delayed_receipts_cents, 0);
    });

    it('tracks uncollected receipts shifted beyond the selected forecast horizon', () => {
      const modifiers: ScenarioModifiers = {
        preset_id: 'delayed_receivables',
        delayed_receivables_days: 10, // Far beyond 4-day horizon
        receipts_modifier_pct: 0,
        expenses_modifier_pct: 0,
        lump_sum_expense_cents: 0,
      };

      const result = calculateScenarioProjection(
        mockBaselineDays,
        safetyReserveCents,
        modifiers
      );

      // All receipts shifted past day 4
      assert.equal(result.days[0].scenario_receipts_cents, 0);
      assert.equal(result.days[1].scenario_receipts_cents, 0);
      assert.equal(result.days[2].scenario_receipts_cents, 0);
      assert.equal(result.days[3].scenario_receipts_cents, 0);

      // Total receipts originally: 100000 + 50000 = 150000
      assert.equal(result.uncollected_delayed_receipts_cents, 150000);
      assert.equal(result.comparison.net_variance_cents, -150000);
    });
  });

  // --------------------------------------------------------------------------
  // 3. Integer-Cent Precision, Bounds & Extreme Inputs
  // --------------------------------------------------------------------------
  describe('Integer-Cent Arithmetic & Bounds', () => {
    it('handles -100% modifier without negative receipts', () => {
      const modifiers: ScenarioModifiers = {
        receipts_modifier_pct: -100, // Zero revenue
        expenses_modifier_pct: 0,
        delayed_receivables_days: 0,
        lump_sum_expense_cents: 0,
      };

      const result = calculateScenarioProjection(
        mockBaselineDays,
        safetyReserveCents,
        modifiers
      );

      assert.equal(result.days[0].scenario_receipts_cents, 0);
      assert.equal(result.days[1].scenario_receipts_cents, 0);
    });

    it('handles +200% modifier correctly', () => {
      const modifiers: ScenarioModifiers = {
        receipts_modifier_pct: 200, // Triples revenue
        expenses_modifier_pct: 0,
        delayed_receivables_days: 0,
        lump_sum_expense_cents: 0,
      };

      const result = calculateScenarioProjection(
        mockBaselineDays,
        safetyReserveCents,
        modifiers
      );

      // Day 0: 100000 * 3 = 300000
      assert.equal(result.days[0].scenario_receipts_cents, 300000);
    });

    it('prevents floating-point drift with odd-cent numbers', () => {
      const oddDays: ForecastDay[] = [
        {
          date: '2026-10-10',
          opening_balance_cents: 33333,
          receipts_cents: 11111,
          expenses_cents: 7777,
          closing_balance_cents: 36667,
        },
      ];

      const modifiers: ScenarioModifiers = {
        receipts_modifier_pct: 15,
        expenses_modifier_pct: 7,
        delayed_receivables_days: 0,
        lump_sum_expense_cents: 1, // $0.01 single cent
      };

      const result = calculateScenarioProjection(oddDays, 100000, modifiers);

      assert.equal(Number.isInteger(result.days[0].scenario_receipts_cents), true);
      assert.equal(Number.isInteger(result.days[0].scenario_expenses_cents), true);
      assert.equal(Number.isInteger(result.days[0].scenario_closing_cents), true);
      assert.equal(Number.isInteger(result.comparison.net_variance_cents), true);
    });
  });

  // --------------------------------------------------------------------------
  // 4. Breach Timing & Acceleration / Aversion
  // --------------------------------------------------------------------------
  describe('Breach Timeline Shifts', () => {
    it('detects breach acceleration when scenario induces early deficit', () => {
      // Baseline breached on 2026-10-13
      const modifiers: ScenarioModifiers = {
        receipts_modifier_pct: 0,
        expenses_modifier_pct: 100, // Double expenses
        delayed_receivables_days: 0,
        lump_sum_expense_cents: 0,
      };

      const result = calculateScenarioProjection(
        mockBaselineDays,
        safetyReserveCents,
        modifiers
      );

      // Day 1: closing drops below 100000 reserve
      assert.equal(result.baseline_first_reserve_breach_date, '2026-10-13');
      assert.equal(result.first_reserve_breach_date, '2026-10-11');
      assert.ok(result.first_reserve_breach_date < result.baseline_first_reserve_breach_date);
    });

    it('detects breach aversion when scenario lifts all balances above reserve', () => {
      const modifiers: ScenarioModifiers = {
        receipts_modifier_pct: 150, // Major revenue boost
        expenses_modifier_pct: -50, // 50% cost cut
        delayed_receivables_days: 0,
        lump_sum_expense_cents: 0,
      };

      const result = calculateScenarioProjection(
        mockBaselineDays,
        safetyReserveCents,
        modifiers
      );

      assert.equal(result.baseline_first_reserve_breach_date, '2026-10-13');
      assert.equal(result.first_reserve_breach_date, null); // Breach averted!
    });
  });

  // --------------------------------------------------------------------------
  // 5. API Fallback, Disclaimer & Missing Data Handling
  // --------------------------------------------------------------------------
  describe('API Fallback & Missing Data Handling', () => {
    it('returns structured fallback tagged with demo disclaimer', () => {
      const modifiers: ScenarioModifiers = {
        receipts_modifier_pct: 0,
        expenses_modifier_pct: 0,
        delayed_receivables_days: 0,
        lump_sum_expense_cents: 0,
      };

      const result = calculateScenarioProjection(
        mockBaselineDays,
        safetyReserveCents,
        modifiers
      );

      assert.equal(result.is_demo, true);
      assert.equal(result.disclaimer, DEMO_SCENARIO_DISCLAIMER);
      assert.match(result.disclaimer, /DEMO SCENARIO FALLBACK MODEL/);
    });

    it('simulateScenario fails honestly when the backend is unavailable', async () => {
      await assert.rejects(
        async () => {
          await simulateScenario(
            {
              business_id: 'test_biz',
              forecast_days: 30,
              safety_reserve_cents: 100000,
              evidence_ids: [],
              currency: 'USD',
            },
            {
              receipts_modifier_pct: 0,
              expenses_modifier_pct: 0,
              delayed_receivables_days: 0,
              lump_sum_expense_cents: 0,
            },
            null // null baseline
          );
        },
        {
          name: 'ApiError',
          message: /Connection interrupted/i,
        }
      );
    });
  });

  // --------------------------------------------------------------------------
  // 6. Financial Reconciliation & Baseline Non-Mutation
  // --------------------------------------------------------------------------
  describe('Financial Reconciliation & Non-Mutation', () => {
    it('preserves exact receipt conservation: sum(shifted) + uncollected === sum(original)', () => {
      // Test across multiple delay increments
      for (let delay = 0; delay <= 6; delay++) {
        const modifiers: ScenarioModifiers = {
          delayed_receivables_days: delay,
          receipts_modifier_pct: 0,
          expenses_modifier_pct: 0,
          lump_sum_expense_cents: 0,
        };

        const result = calculateScenarioProjection(mockBaselineDays, safetyReserveCents, modifiers);

        const totalScenarioReceipts = result.days.reduce((sum, d) => sum + d.receipts_cents, 0);
        const totalOriginalReceipts = mockBaselineDays.reduce((sum, d) => sum + d.receipts_cents, 0);

        assert.equal(
          totalScenarioReceipts + result.uncollected_delayed_receipts_cents,
          totalOriginalReceipts,
          `Failed receipt conservation at delay=${delay}`
        );
      }
    });

    it('verifies exact boundary condition at targetDayIdx === days.length', () => {
      // mockBaselineDays has length 4.
      // Day 1 (index 1) has receipts 50000.
      // If delay is 3, targetDayIdx = 1 + 3 = 4 === days.length (exactly off-horizon boundary)
      const modifiers: ScenarioModifiers = {
        delayed_receivables_days: 3,
        receipts_modifier_pct: 0,
        expenses_modifier_pct: 0,
        lump_sum_expense_cents: 0,
      };

      const result = calculateScenarioProjection(mockBaselineDays, safetyReserveCents, modifiers);

      // Day 0 receipts (100000) land on Day 0 + 3 = Day 3 (within horizon index 3)
      assert.equal(result.days[3].receipts_cents, 100000);
      // Day 1 receipts (50000) land on Day 1 + 3 = Day 4 === days.length (withheld from horizon!)
      assert.equal(result.uncollected_delayed_receipts_cents, 50000);
      // No receipt collected after Day 3
      assert.equal(result.days.length, 4);
    });

    it('reconciles closing balances, variances, and ending totals across all days', () => {
      const modifiers: ScenarioModifiers = {
        receipts_modifier_pct: 10,
        expenses_modifier_pct: 5,
        delayed_receivables_days: 1,
        lump_sum_expense_cents: 20000,
      };

      const result = calculateScenarioProjection(mockBaselineDays, safetyReserveCents, modifiers);

      let running = mockBaselineDays[0].opening_balance_cents;
      for (const day of result.days) {
        // Daily identity: closing = opening + receipts - expenses
        assert.equal(day.opening_balance_cents, running);
        assert.equal(
          day.closing_balance_cents,
          day.opening_balance_cents + day.receipts_cents - day.expenses_cents
        );
        running = day.closing_balance_cents;

        // Daily variance identity
        assert.equal(day.variance_cents, day.scenario_closing_cents - day.baseline_closing_cents);
      }

      // Ending balance identity
      assert.equal(
        result.comparison.scenario_ending_balance_cents,
        result.days[result.days.length - 1].closing_balance_cents
      );
      assert.equal(
        result.comparison.net_variance_cents,
        result.comparison.scenario_ending_balance_cents - result.comparison.baseline_ending_balance_cents
      );
    });

    it('does NOT mutate the input baselineDays object or array', () => {
      const baselineSnapshot = JSON.parse(JSON.stringify(mockBaselineDays));

      const modifiers: ScenarioModifiers = {
        receipts_modifier_pct: -50,
        expenses_modifier_pct: 75,
        delayed_receivables_days: 14,
        lump_sum_expense_cents: 500000,
        recurring_payroll_cents: 650000,
      };

      calculateScenarioProjection(mockBaselineDays, safetyReserveCents, modifiers);

      // Verify strict deep equality: input baseline was never mutated
      assert.deepEqual(mockBaselineDays, baselineSnapshot);
    });
  });

});
