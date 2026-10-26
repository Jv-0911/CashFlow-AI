import React, { useState } from 'react';
import {
  ChevronDown,
  ChevronUp,
  ShieldCheck,
  AlertCircle,
  Clock,
  Sparkles,
  Layers,
  ArrowUpRight,
} from 'lucide-react';
import type { RankedRescueAction } from './ranking';
import { formatCents } from '../../utils/currency';

interface RescueActionCardProps {
  action: RankedRescueAction;
  currency: string;
  isSelectedForSimulation: boolean;
  onToggleSimulation: (actionId: string) => void;
}

export const RescueActionCard: React.FC<RescueActionCardProps> = ({
  action,
  currency,
  isSelectedForSimulation,
  onToggleSimulation,
}) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(false);

  const confidence = action.confidence || 'medium';
  const hasEvidence = Array.isArray(action.evidence_ids) && action.evidence_ids.length > 0;
  const timingOffset = action.timing_days_offset ?? 1;

  return (
    <div
      className={`rescue-action-card ${isSelectedForSimulation ? 'selected' : ''}`}
      data-testid={`action-card-${action.action_id}`}
    >
      <div className="action-card-main">
        {/* Left: Rank & Selection */}
        <div className="action-rank-column">
          <div className={`action-rank-badge rank-${action.rank}`} title={`Deterministic Priority Rank ${action.rank}`}>
            #{action.rank}
          </div>
          <button
            type="button"
            className={`action-select-btn ${isSelectedForSimulation ? 'active' : ''}`}
            onClick={() => onToggleSimulation(action.action_id)}
            aria-label={isSelectedForSimulation ? 'Deselect from simulation' : 'Select for simulation'}
          >
            {isSelectedForSimulation ? 'Simulating' : 'Simulate'}
          </button>
        </div>

        {/* Center: Title, Impact, Category */}
        <div className="action-content-column">
          <div className="action-header-row">
            <span className="action-id-tag font-mono">{action.action_id}</span>
            <span className={`confidence-pill confidence-${confidence}`}>
              {confidence.toUpperCase()} CONFIDENCE
            </span>
            {action.category && (
              <span className="category-pill">
                <Layers size={11} />
                <span>{action.category}</span>
              </span>
            )}
            <span className="timing-pill">
              <Clock size={11} />
              <span>Effective Day +{timingOffset}</span>
            </span>
          </div>

          <h4 className="action-title">{action.title}</h4>

          {action.rationale && (
            <p className="action-rationale">{action.rationale}</p>
          )}

          {/* Ranking criteria explanation snippet */}
          <div className="action-ranking-criteria">
            <Sparkles size={13} className="text-accent" />
            <span className="criteria-text">{action.rankingExplanation}</span>
          </div>
        </div>

        {/* Right: Estimated Impact & Details Toggle */}
        <div className="action-impact-column">
          <div className="impact-box">
            <span className="impact-caption">Estimated Impact</span>
            <span className="impact-value text-safe">
              +{formatCents(action.estimated_impact_cents, currency)}
            </span>
            <span className="impact-disclaimer-tag">
              Projected recovery • Not realized
            </span>
          </div>

          <button
            type="button"
            className="action-expand-btn"
            onClick={() => setIsExpanded(!isExpanded)}
            aria-expanded={isExpanded}
          >
            <span>{isExpanded ? 'Hide Details' : 'Inspect Evidence & Assumptions'}</span>
            {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        </div>
      </div>

      {/* Expandable Inspection Drawer */}
      {isExpanded && (
        <div className="action-drawer-details">
          <div className="drawer-grid">
            {/* Underlying Assumptions */}
            <div className="drawer-column">
              <div className="drawer-col-header">
                <ShieldCheck size={14} />
                <span>Underlying Assumptions ({action.assumptions.length})</span>
              </div>
              <ul className="drawer-assumptions-list">
                {action.assumptions.map((assumption, i) => (
                  <li key={i} className="assumption-item">
                    <span className="bullet">•</span>
                    <span>{assumption}</span>
                  </li>
                ))}
              </ul>
              <div className="drawer-note">
                Notice: Assumptions represent external dependencies. If unfulfilled, the projected impact will not materialize.
              </div>
            </div>

            {/* Evidence Linkage */}
            <div className="drawer-column">
              <div className="drawer-col-header">
                <ArrowUpRight size={14} />
                <span>Direct Evidence Linkage</span>
              </div>
              {hasEvidence ? (
                <div className="drawer-evidence-list">
                  {action.evidence_ids!.map((id) => (
                    <div key={id} className="drawer-evidence-chip">
                      <span className="font-mono text-safe">{id}</span>
                      <span className="chip-sub">Grounded Contract Identifier</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="drawer-evidence-empty">
                  <AlertCircle size={14} className="text-muted" />
                  <span>
                    Evidence unavailable: Recommendation is generated by aggregate model heuristics without direct transaction attachment.
                  </span>
                </div>
              )}

              <div className="drawer-status-box">
                <span className="status-label">Verification Status:</span>
                <span className="status-val text-warning">
                  Unverified Estimate • Analytical projection pending operational execution
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
