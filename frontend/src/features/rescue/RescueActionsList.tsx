import React from 'react';
import { HelpCircle, CheckSquare, Square } from 'lucide-react';
import type { RankedRescueAction } from './ranking';
import { RANKING_CRITERIA_SUMMARY } from './ranking';
import { RescueActionCard } from './RescueActionCard';
import { formatCents } from '../../utils/currency';

interface RescueActionsListProps {
  actions: RankedRescueAction[];
  currency: string;
  selectedActionIds: string[];
  onToggleAction: (actionId: string) => void;
  onSelectAll: () => void;
  onClearAll: () => void;
}

export const RescueActionsList: React.FC<RescueActionsListProps> = ({
  actions,
  currency,
  selectedActionIds,
  onToggleAction,
  onSelectAll,
  onClearAll,
}) => {
  const totalPotentialImpactCents = actions.reduce(
    (acc, a) => acc + Math.round(a.estimated_impact_cents),
    0
  );

  const allSelected = actions.length > 0 && selectedActionIds.length === actions.length;

  return (
    <div className="rescue-actions-section">
      <div className="rescue-actions-header-row">
        <div>
          <div className="section-title-with-pill">
            <h3 className="section-title">Ranked AI Rescue Recommendations</h3>
            <span className="actions-count-pill">{actions.length} Actions Available</span>
          </div>
          <p className="section-subtitle">
            Autonomous intervention strategies deterministically prioritized to restore required liquidity.
          </p>
        </div>

        <div className="actions-header-controls">
          <div className="total-impact-preview">
            <span className="label">Total Potential Pool:</span>
            <span className="value text-safe">
              +{formatCents(totalPotentialImpactCents, currency)}
            </span>
          </div>

          <div className="selection-buttons-group">
            <button
              type="button"
              className="control-text-btn"
              onClick={allSelected ? onClearAll : onSelectAll}
            >
              {allSelected ? <Square size={13} /> : <CheckSquare size={13} />}
              <span>{allSelected ? 'Clear All' : 'Select All'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Transparent Ranking Criteria Banner */}
      <div className="ranking-criteria-banner">
        <div className="criteria-banner-icon">
          <HelpCircle size={15} />
        </div>
        <div className="criteria-banner-text">
          <span className="criteria-heading">Deterministic Prioritization Criteria:</span>{' '}
          {RANKING_CRITERIA_SUMMARY}
        </div>
      </div>

      {/* List of cards */}
      <div className="actions-cards-stack">
        {actions.map((action) => (
          <RescueActionCard
            key={action.action_id}
            action={action}
            currency={currency}
            isSelectedForSimulation={selectedActionIds.includes(action.action_id)}
            onToggleSimulation={onToggleAction}
          />
        ))}
      </div>
    </div>
  );
};
