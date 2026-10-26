import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { rankRescueActions } from '../ranking.ts';
import {
  runRecoverySimulation,
  HYPOTHETICAL_SIMULATION_DISCLAIMER,
} from '../simulation.ts';
import { formatCents, formatCentsCompact } from '../../../utils/currency.ts';
import type { RescueAction, ForecastDay } from '../../../types/index.ts';

describe('AI Rescue Suite - Unit & Behavioral Tests', () => {
  // --------------------------------------------------------------------------
  // 1. Deterministic Action Ranking Tests
  // --------------------------------------------------------------------------
  describe('Deterministic Action Ranking', () => {
    it('ranks high confidence with verified evidence above speculative high-dollar action', () => {
      const actions: RescueAction[] = [
        {
          action_id: 'action_speculative_large',
          title: 'High-risk unverified liquidity intervention',
          estimated_impact_cents: 1000000, // $10,000.00
          assumptions: ['Client agrees to new equity pledge', 'Lender waives covenants'],
          confidence: 'low',
          evidence_ids: [],
        },
        {
          action_id: 'action_grounded_safe',
          title: 'Collect overdue invoice #INV-101',
          estimated_impact_cents: 50000, // $500.00
          assumptions: ['Customer pays in full'],
          confidence: 'high',
          evidence_ids: ['txn_demo_001'],
        },
      ];

      const ranked = rankRescueActions(actions);
      assert.equal(ranked.length, 2);
      assert.equal(ranked[0].action_id, 'action_grounded_safe');
      assert.equal(ranked[0].rank, 1);
      assert.match(ranked[0].rankingExplanation, /verified transaction evidence/i);
      assert.equal(ranked[1].action_id, 'action_speculative_large');
      assert.equal(ranked[1].rank, 2);
      assert.match(ranked[1].rankingExplanation, /low outcome certainty/i);
    });

    it('breaks ties deterministically by action_id when scores are identical', () => {
      const actions: RescueAction[] = [
        {
          action_id: 'action_z_tied',
          title: 'Action Z',
          estimated_impact_cents: 30000,
          assumptions: ['Standard terms'],
          confidence: 'medium',
        },
        {
          action_id: 'action_a_tied',
          title: 'Action A',
          estimated_impact_cents: 30000,
          assumptions: ['Standard terms'],
          confidence: 'medium',
        },
      ];

      const ranked = rankRescueActions(actions);
      assert.equal(ranked[0].action_id, 'action_a_tied');
      assert.equal(ranked[1].action_id, 'action_z_tied');
    });

    it('handles missing assumptions and missing confidence with default fallbacks', () => {
      const actions: RescueAction[] = [
        {
          action_id: 'action_no_conf_or_assumptions',
          title: 'Action without optional fields',
          estimated_impact_cents: 25000,
          assumptions: [], // empty
        },
      ];

      const ranked = rankRescueActions(actions);
      assert.equal(ranked.length, 1);
      assert.equal(ranked[0].rank, 1);
      assert.match(ranked[0].rankingExplanation, /moderate confidence/i);
    });

    it('returns empty array when no actions provided', () => {
      const ranked = rankRescueActions([]);
      assert.deepEqual(ranked, []);
    });

  });

  // --------------------------------------------------------------------------
  // 2. Missing & Grounded Evidence Tests
  // --------------------------------------------------------------------------
  describe('Evidence Tracing & Missing Evidence Handling', () => {
    it('preserves grounded evidence IDs without inventing synthetic citations', () => {
      const action: RescueAction = {
        action_id: 'action_with_evidence',
        title: 'Verified action',
        estimated_impact_cents: 50000,
        assumptions: [],
        evidence_ids: ['txn_demo_001', 'txn_demo_002'],
      };

      const ranked = rankRescueActions([action]);
      assert.deepEqual(ranked[0].evidence_ids, ['txn_demo_001', 'txn_demo_002']);
    });

    it('handles empty or undefined evidence_ids cleanly without synthesis', () => {
      const action: RescueAction = {
        action_id: 'action_no_evidence',
        title: 'Action without evidence',
        estimated_impact_cents: 20000,
        assumptions: [],
      };

      const ranked = rankRescueActions([action]);
      assert.equal(ranked[0].action_id, 'action_no_evidence');
      assert.ok(!ranked[0].evidence_ids || ranked[0].evidence_ids.length === 0);
    });
  });

  // --------------------------------------------------------------------------
  // 3. Timing-Based Simulation & Integer Cent Math
  // --------------------------------------------------------------------------
  describe('Recovery Simulation Engine', () => {
    const mockDays: ForecastDay[] = [
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
        receipts_cents: 100000,
        expenses_cents: 50000,
        closing_balance_cents: 450000,
      },
      {
        date: '2026-10-12',
        opening_balance_cents: 450000,
        receipts_cents: 0,
        expenses_cents: 400000,
        closing_balance_cents: 50000, // Breach below 100000 reserve
      },
      {
        date: '2026-10-13',
        opening_balance_cents: 50000,
        receipts_cents: 0,
        expenses_cents: 0,
        closing_balance_cents: 50000, // Stays in breach
      },
    ];

    it('does NOT blindly add impact to days prior to action effective timing', () => {
      const selectedAction: RescueAction = {
        action_id: 'action_invoice_recovery',
        title: 'Collect invoice',
        estimated_impact_cents: 70000, // $700.00
        assumptions: ['Customer pays'],
        timing_days_offset: 1, // Effective on breach day (index 2: 2026-10-12)
      };

      const result = runRecoverySimulation(
        mockDays,
        100000, // $1,000.00 reserve
        [selectedAction],
        '2026-10-12'
      );

      // Day 0 (2026-10-10) and Day 1 (2026-10-11) MUST NOT have any impact added
      assert.equal(result.simulatedDays[0].simulated_cumulative_impact_cents, 0);
      assert.equal(result.simulatedDays[0].simulated_closing_balance_cents, 400000);

      assert.equal(result.simulatedDays[1].simulated_cumulative_impact_cents, 0);
      assert.equal(result.simulatedDays[1].simulated_closing_balance_cents, 450000);

      // Day 2 (2026-10-12) has impact added: 50000 + 70000 = 120000
      assert.equal(result.simulatedDays[2].simulated_cumulative_impact_cents, 70000);
      assert.equal(result.simulatedDays[2].simulated_closing_balance_cents, 120000);

      // Day 3 (2026-10-13) rolls forward impact: 50000 + 70000 = 120000
      assert.equal(result.simulatedDays[3].simulated_cumulative_impact_cents, 70000);
      assert.equal(result.simulatedDays[3].simulated_closing_balance_cents, 120000);

      // Integer cent metrics
      assert.equal(result.originalShortfallCents, 50000); // 100000 - 50000 = 50000 ($500 shortfall)
      assert.equal(result.simulatedShortfallCents, 0); // 120000 >= 100000, shortfall 0
      assert.equal(result.shortfallRecoveredCents, 50000);
      assert.equal(result.isBreachResolved, true);
    });

    it('handles multiple actions with distinct timing offsets and cumulative roll-forward', () => {
      const actionA: RescueAction = {
        action_id: 'action_a',
        title: 'Action A (day 2)',
        estimated_impact_cents: 20000, // $200.00 on breach day
        assumptions: ['Assump A'],
        timing_days_offset: 1,
      };
      const actionB: RescueAction = {
        action_id: 'action_b',
        title: 'Action B (day 3)',
        estimated_impact_cents: 30000, // $300.00 on breach day + 1
        assumptions: ['Assump B'],
        timing_days_offset: 2,
      };

      // Both selected
      const resultBoth = runRecoverySimulation(mockDays, 100000, [actionA, actionB], '2026-10-12');
      assert.equal(resultBoth.simulatedActionsCount, 2);
      assert.equal(resultBoth.totalEstimatedImpactCents, 50000);
      assert.deepEqual(resultBoth.activeAssumptions, ['Assump A', 'Assump B']);

      // Day 0: +0, Day 1: +0
      assert.equal(resultBoth.simulatedDays[0].simulated_cumulative_impact_cents, 0);
      assert.equal(resultBoth.simulatedDays[1].simulated_cumulative_impact_cents, 0);
      // Day 2 (breach): +20000
      assert.equal(resultBoth.simulatedDays[2].simulated_cumulative_impact_cents, 20000);
      assert.equal(resultBoth.simulatedDays[2].simulated_closing_balance_cents, 70000);
      // Day 3: +20000 + 30000 = +50000
      assert.equal(resultBoth.simulatedDays[3].simulated_cumulative_impact_cents, 50000);
      assert.equal(resultBoth.simulatedDays[3].simulated_closing_balance_cents, 100000);

      // Deselect actionA (simulating only actionB)
      const resultBOnly = runRecoverySimulation(mockDays, 100000, [actionB], '2026-10-12');
      assert.equal(resultBOnly.simulatedActionsCount, 1);
      assert.equal(resultBOnly.totalEstimatedImpactCents, 30000);
      // Day 2 has 0 impact because Action B takes effect on day 3
      assert.equal(resultBOnly.simulatedDays[2].simulated_cumulative_impact_cents, 0);
      assert.equal(resultBOnly.simulatedDays[2].simulated_closing_balance_cents, 50000);
      // Day 3 has 30000 impact
      assert.equal(resultBOnly.simulatedDays[3].simulated_cumulative_impact_cents, 30000);
      assert.equal(resultBOnly.simulatedDays[3].simulated_closing_balance_cents, 80000);
    });

    it('handles simulation when no breach exists in forecast days (safe buffer)', () => {
      const safeDays: ForecastDay[] = [
        {
          date: '2026-10-10',
          opening_balance_cents: 500000,
          receipts_cents: 50000,
          expenses_cents: 20000,
          closing_balance_cents: 530000,
        },
      ];

      const action: RescueAction = {
        action_id: 'action_opt',
        title: 'Buffer boost',
        estimated_impact_cents: 10000,
        assumptions: [],
      };

      const result = runRecoverySimulation(safeDays, 100000, [action], null);
      assert.equal(result.originalShortfallCents, 0);
      assert.equal(result.simulatedShortfallCents, 0);
      assert.equal(result.shortfallRecoveredCents, 0);
      assert.equal(result.isBreachResolved, true);
    });

    it('strictly maintains integer cent calculations with zero floating point drift', () => {
      const selectedAction: RescueAction = {
        action_id: 'action_small_change',
        title: 'Precision test',
        estimated_impact_cents: 33333,
        assumptions: [],
      };

      const result = runRecoverySimulation(mockDays, 100000, [selectedAction], '2026-10-12');
      assert.equal(Number.isInteger(result.simulatedMinBalanceCents), true);
      assert.equal(Number.isInteger(result.simulatedShortfallCents), true);
      assert.equal(Number.isInteger(result.shortfallRecoveredCents), true);
      assert.equal(Number.isInteger(result.totalEstimatedImpactCents), true);
    });

    it('includes mandatory hypothetical non-execution disclaimer', () => {
      const result = runRecoverySimulation(mockDays, 100000, [], null);
      assert.equal(result.disclaimer, HYPOTHETICAL_SIMULATION_DISCLAIMER);
      assert.match(result.disclaimer, /HYPOTHETICAL SIMULATION PREVIEW/);
      assert.match(result.disclaimer, /do not represent actual cash movements/i);
    });

  });

  // --------------------------------------------------------------------------
  // 4. Currency Formatter Verification (Negative, Zero, Compact)
  // --------------------------------------------------------------------------
  describe('Currency Formatter Verification', () => {
    it('formats negative currency correctly without floating point errors', () => {
      assert.equal(formatCents(-50000), '-$500.00');
      assert.equal(formatCents(-100000), '-$1,000.00');
      assert.equal(formatCents(-1), '-$0.01');
      assert.equal(formatCents(-50), '-$0.50');
      assert.equal(formatCents(-99), '-$0.99');
    });

    it('formats zero and positive amounts correctly', () => {
      assert.equal(formatCents(0), '$0.00');
      assert.equal(formatCents(50000), '$500.00');
      assert.equal(formatCents(1234567), '$12,345.67');
    });

    it('supports custom ISO currency symbols and codes', () => {
      assert.equal(formatCents(-50000, 'EUR'), '-EUR 500.00');
      assert.equal(formatCents(100000, 'GBP'), 'GBP 1,000.00');
    });

    it('formats compact negative currency correctly', () => {
      assert.equal(formatCentsCompact(-50000), '-$500');
      assert.equal(formatCentsCompact(-100000), '-$1,000');
      assert.equal(formatCentsCompact(0), '$0');
      assert.equal(formatCentsCompact(50000), '$500');
    });
  });
});
