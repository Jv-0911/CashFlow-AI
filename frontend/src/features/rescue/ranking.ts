import type { RescueAction } from '../../types';

export interface RankedRescueAction extends RescueAction {
  rank: number;
  rankingScore: number;
  rankingExplanation: string;
}

export const RANKING_CRITERIA_SUMMARY =
  'Actions are prioritized deterministically using a multi-factor risk model: Confidence Tier (High > Medium > Low), Assumption Certainty (fewer contingent dependencies), Grounded Evidence Verification, and Projected Financial Impact. Pure dollar size is deliberately decoupled from safety priority to prevent speculative, high-uncertainty actions from outranking safer interventions.';

/**
 * Deterministically ranks rescue actions based on confidence, assumption risk,
 * grounded evidence attachment, and estimated impact, with stable action_id tie-breaking.
 */
export function rankRescueActions(actions: RescueAction[]): RankedRescueAction[] {
  if (!actions || actions.length === 0) return [];

  // Calculate score for each action
  const scored = actions.map((action) => {
    let score = 0;

    // 1. Confidence weighting (base foundation)
    const conf = action.confidence || 'medium';
    if (conf === 'high') score += 3000;
    else if (conf === 'medium') score += 2000;
    else score += 1000;

    // 2. Grounded evidence bonus (verifiable link to ledger/contract)
    const hasEvidence = Array.isArray(action.evidence_ids) && action.evidence_ids.length > 0;
    if (hasEvidence) {
      score += 500;
    }

    // 3. Assumption certainty penalty (more contingent assumptions = higher risk)
    const assumptionCount = Array.isArray(action.assumptions) ? action.assumptions.length : 0;
    const assumptionPenalty = Math.min(600, assumptionCount * 150);
    score -= assumptionPenalty;

    // 4. Impact contribution (scaled conservatively so high dollar amounts don't override low confidence)
    // 10,000 cents ($100.00) = 10 points. Bounded at 500 points max.
    const impactPoints = Math.min(500, Math.floor(Math.max(0, action.estimated_impact_cents) / 1000));
    score += impactPoints;

    // Build transparent explanation
    let explanation = '';
    if (conf === 'high') {
      explanation = hasEvidence
        ? 'High confidence supported by verified transaction evidence and minimal contingent assumptions.'
        : 'High model confidence based on direct internal accounts receivable.';
    } else if (conf === 'medium') {
      explanation = 'Moderate confidence with operational feasibility, subject to counterparty timeline confirmation.';
    } else {
      explanation =
        'Higher estimated dollar recovery, but categorized lower due to low outcome certainty and multiple dependent client assumptions.';
    }

    return {
      action,
      score,
      explanation,
    };
  });

  // Sort deterministically: highest score first, stable tiebreaker by action_id
  scored.sort((a, b) => {
    if (b.score !== a.score) {
      return b.score - a.score;
    }
    return a.action.action_id.localeCompare(b.action.action_id);
  });

  return scored.map((item, index) => ({
    ...item.action,
    rank: index + 1,
    rankingScore: item.score,
    rankingExplanation: item.explanation,
  }));
}
