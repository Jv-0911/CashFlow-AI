import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  calculateCashFlowAnalytics,
  calculatePeriodComparison,
} from '../analytics-math.ts';
import type { ForecastDay } from '../../../types/forecast.ts';
import type { LedgerEntry } from '../../../types/ledger.ts';

describe('Analytics Suite — Unit & Calculation Integrity Tests', () => {
  const sampleDays: ForecastDay[] = [
    {
      date: '2026-10-15',
      opening_balance_cents: 440000,
      receipts_cents: 100000, // $1,000.00
      expenses_cents: 40000,  // $400.00
      closing_balance_cents: 500000, // $5,000.00
    },
    {
      date: '2026-10-16',
      opening_balance_cents: 500000,
      receipts_cents: 50000,  // $500.00
      expenses_cents: 60000,  // $600.00
      closing_balance_cents: 490000, // $4,900.00
    },
    {
      date: '2026-10-17',
      opening_balance_cents: 490000,
      receipts_cents: 0,
      expenses_cents: 100000, // $1,000.00
      closing_balance_cents: 390000, // $3,900.00
    },
    {
      date: '2026-10-18',
      opening_balance_cents: 390000,
      receipts_cents: 20000,  // $200.00
      expenses_cents: 80000,  // $800.00
      closing_balance_cents: 330000, // $3,300.00
    },
  ];

  const sampleLedgerEntries: LedgerEntry[] = [
    {
      ledger_entry_id: 'led_1',
      invoice_id: 'inv_1',
      amount_cents: 50000,
      currency: 'USD',
      status: 'verified_completed',
      provider: 'paypal_sandbox',
      verified_at: '2026-10-12T10:00:00Z',
      created_at: '2026-10-10T10:00:00Z',
    },
    {
      ledger_entry_id: 'led_2',
      invoice_id: 'inv_2',
      amount_cents: 50000,
      currency: 'USD',
      status: 'pending_verification',
      provider: 'paypal_sandbox',
      verified_at: null,
      created_at: '2026-10-11T10:00:00Z',
    },
  ];

  describe('Core Aggregations & Integer-Cent Math', () => {
    it('accurately calculates total inflows, outflows, and net cash flow without drift', () => {
      const result = calculateCashFlowAnalytics(sampleDays, 100000, sampleLedgerEntries);

      // Inflow: 100000 + 50000 + 0 + 20000 = 170000
      assert.strictEqual(result.total_inflow_cents, 170000);
      // Outflow: 40000 + 60000 + 100000 + 80000 = 280000
      assert.strictEqual(result.total_outflow_cents, 280000);
      // Net: 170000 - 280000 = -110000
      assert.strictEqual(result.net_cash_flow_cents, -110000);
      // Daily averages (4 days):
      // avg inflow: 170000 / 4 = 42500
      assert.strictEqual(result.avg_daily_inflow_cents, 42500);
      // avg burn: 280000 / 4 = 70000
      assert.strictEqual(result.avg_daily_burn_cents, 70000);
      // net daily delta: 42500 - 70000 = -27500
      assert.strictEqual(result.net_daily_delta_cents, -27500);
    });

    it('identifies min, max, and current closing balances correctly', () => {
      const result = calculateCashFlowAnalytics(sampleDays, 100000);

      assert.strictEqual(result.min_projected_balance_cents, 330000);
      assert.strictEqual(result.max_projected_balance_cents, 500000);
      assert.strictEqual(result.current_balance_cents, 330000);
    });

    it('preserves immutability of input forecast days and ledger array', () => {
      const daysCopy = JSON.parse(JSON.stringify(sampleDays));
      const ledgerCopy = JSON.parse(JSON.stringify(sampleLedgerEntries));

      calculateCashFlowAnalytics(sampleDays, 100000, sampleLedgerEntries);

      assert.deepStrictEqual(sampleDays, daysCopy);
      assert.deepStrictEqual(sampleLedgerEntries, ledgerCopy);
    });
  });

  describe('Runway Calculations — Zero Cash vs Safety Reserve Breach', () => {
    it('computes runway to zero cash and runway to reserve breach separately', () => {
      // currentBalance = 330000 cents ($3,300)
      // avg burn = 70000 cents/day ($700/day)
      // reserve = 100000 cents ($1,000)
      // runway to zero = floor(330000 / 70000) = 4 days
      // runway to breach = floor((330000 - 100000) / 70000) = floor(230000 / 70000) = 3 days
      const result = calculateCashFlowAnalytics(sampleDays, 100000);

      assert.strictEqual(result.runway_zero_days, 4);
      assert.strictEqual(result.runway_reserve_breach_days, 3);
    });

    it('returns null for runway when average daily burn is zero (sustainable/no burn)', () => {
      const zeroBurnDays: ForecastDay[] = [
        { date: '2026-10-15', opening_balance_cents: 150000, receipts_cents: 50000, expenses_cents: 0, closing_balance_cents: 200000 },
        { date: '2026-10-16', opening_balance_cents: 200000, receipts_cents: 30000, expenses_cents: 0, closing_balance_cents: 230000 },
      ];

      const result = calculateCashFlowAnalytics(zeroBurnDays, 100000);

      assert.strictEqual(result.avg_daily_burn_cents, 0);
      assert.strictEqual(result.runway_zero_days, null);
      assert.strictEqual(result.runway_reserve_breach_days, null);
    });

    it('returns 0 for runway_reserve_breach_days when current balance is already below reserve', () => {
      const breachedDays: ForecastDay[] = [
        { date: '2026-10-15', opening_balance_cents: 120000, receipts_cents: 10000, expenses_cents: 50000, closing_balance_cents: 80000 },
      ];

      // reserve is $1000 (100000 cents), balance is $800 (80000 cents) -> already breached
      const result = calculateCashFlowAnalytics(breachedDays, 100000);

      assert.strictEqual(result.runway_reserve_breach_days, 0);
      // But runway to zero is still positive: floor(80000 / 50000) = 1 day
      assert.strictEqual(result.runway_zero_days, 1);
    });

    it('returns 0 for runway_zero_days when closing balance is zero or negative', () => {
      const insolventDays: ForecastDay[] = [
        { date: '2026-10-15', opening_balance_cents: 50000, receipts_cents: 0, expenses_cents: 50000, closing_balance_cents: 0 },
      ];

      const result = calculateCashFlowAnalytics(insolventDays, 50000);

      assert.strictEqual(result.runway_zero_days, 0);
      assert.strictEqual(result.runway_reserve_breach_days, 0);
    });

    it('accurately detects earliest forecast reserve breach date', () => {
      const breachHorizon: ForecastDay[] = [
        { date: '2026-10-15', opening_balance_cents: 160000, receipts_cents: 0, expenses_cents: 10000, closing_balance_cents: 150000 },
        { date: '2026-10-16', opening_balance_cents: 150000, receipts_cents: 0, expenses_cents: 60000, closing_balance_cents: 90000 }, // drops < 100000
        { date: '2026-10-17', opening_balance_cents: 90000, receipts_cents: 0, expenses_cents: 50000, closing_balance_cents: 40000 },
      ];

      const result = calculateCashFlowAnalytics(breachHorizon, 100000);

      assert.strictEqual(result.earliest_forecast_breach_date, '2026-10-16');
    });

    it('returns null for earliest_forecast_breach_date if balance never breaches reserve', () => {
      const healthyHorizon: ForecastDay[] = [
        { date: '2026-10-15', opening_balance_cents: 190000, receipts_cents: 20000, expenses_cents: 10000, closing_balance_cents: 200000 },
        { date: '2026-10-16', opening_balance_cents: 200000, receipts_cents: 20000, expenses_cents: 10000, closing_balance_cents: 210000 },
      ];

      const result = calculateCashFlowAnalytics(healthyHorizon, 100000);

      assert.strictEqual(result.earliest_forecast_breach_date, null);
    });
  });

  describe('Ledger Recovery Efficiency & Denominator Discipline', () => {
    it('strictly counts verified_completed entries with valid timestamps in numerator', () => {
      const ledger: LedgerEntry[] = [
        {
          ledger_entry_id: '1',
          invoice_id: 'i1',
          amount_cents: 40000,
          currency: 'USD',
          status: 'verified_completed',
          provider: 'paypal_sandbox',
          verified_at: '2026-10-10T12:00:00Z',
          created_at: '2026-10-09T10:00:00Z',
        },
        {
          ledger_entry_id: '2',
          invoice_id: 'i2',
          amount_cents: 60000,
          currency: 'USD',
          status: 'pending_verification',
          provider: 'paypal_sandbox',
          verified_at: null,
          created_at: '2026-10-09T10:00:00Z',
        },
      ];

      const result = calculateCashFlowAnalytics(sampleDays, 100000, ledger);

      assert.strictEqual(result.verified_recovered_cents, 40000);
      assert.strictEqual(result.total_tracked_ledger_cents, 100000);
      assert.strictEqual(result.recovery_efficiency_pct, 40); // 40000 / 100000 = 40%
    });

    it('rejects entries with verified_completed status but missing or invalid timestamp from verified cash', () => {
      const ledgerWithBogusDate: LedgerEntry[] = [
        {
          ledger_entry_id: '1',
          invoice_id: 'i1',
          amount_cents: 50000,
          currency: 'USD',
          status: 'verified_completed',
          provider: 'paypal_sandbox',
          verified_at: 'invalid-date-string',
          created_at: '2026-10-09T10:00:00Z',
        },
        {
          ledger_entry_id: '2',
          invoice_id: 'i2',
          amount_cents: 50000,
          currency: 'USD',
          status: 'verified_completed',
          provider: 'paypal_sandbox',
          verified_at: '',
          created_at: '2026-10-09T10:00:00Z',
        },
      ];

      const result = calculateCashFlowAnalytics(sampleDays, 100000, ledgerWithBogusDate);

      assert.strictEqual(result.verified_recovered_cents, 0);
      assert.strictEqual(result.total_tracked_ledger_cents, 100000);
      assert.strictEqual(result.recovery_efficiency_pct, 0);
    });

    it('returns null for recovery_efficiency_pct when ledger is empty to avoid division by zero', () => {
      const result = calculateCashFlowAnalytics(sampleDays, 100000, []);

      assert.strictEqual(result.verified_recovered_cents, 0);
      assert.strictEqual(result.total_tracked_ledger_cents, 0);
      assert.strictEqual(result.recovery_efficiency_pct, null);
    });
  });

  describe('Period-Over-Period Comparison', () => {
    it('compares first half vs second half inflows and outflows', () => {
      const comparison = calculatePeriodComparison(sampleDays);
      assert.ok(comparison);

      // 4 days total -> mid = 2
      // first half: [day0, day1]
      //   inflows: 100000 + 50000 = 150000
      //   outflows: 40000 + 60000 = 100000
      // second half: [day2, day3]
      //   inflows: 0 + 20000 = 20000
      //   outflows: 100000 + 80000 = 180000
      // inflow variance: 20000 - 150000 = -130000
      // outflow variance: 180000 - 100000 = 80000
      assert.strictEqual(comparison.first_half_inflow_cents, 150000);
      assert.strictEqual(comparison.first_half_outflow_cents, 100000);
      assert.strictEqual(comparison.second_half_inflow_cents, 20000);
      assert.strictEqual(comparison.second_half_outflow_cents, 180000);
      assert.strictEqual(comparison.inflow_variance_cents, -130000);
      assert.strictEqual(comparison.outflow_variance_cents, 80000);
    });

    it('returns null if days array has fewer than 2 items', () => {
      assert.strictEqual(calculatePeriodComparison([]), null);
      assert.strictEqual(calculatePeriodComparison([sampleDays[0]]), null);
    });
  });

  describe('Edge Cases & Missing Data Handling', () => {
    it('safely handles empty forecast days array without crashing', () => {
      const result = calculateCashFlowAnalytics([], 100000);

      assert.strictEqual(result.horizon_days, 0);
      assert.strictEqual(result.total_inflow_cents, 0);
      assert.strictEqual(result.total_outflow_cents, 0);
      assert.strictEqual(result.net_cash_flow_cents, 0);
      assert.strictEqual(result.runway_zero_days, null);
      assert.strictEqual(result.runway_reserve_breach_days, null);
    });
  });
});
