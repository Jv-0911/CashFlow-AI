import React from 'react';
import { Info, FileText, CheckCircle, AlertCircle } from 'lucide-react';
import type { ForecastDay } from '../../types';
import { formatCents } from '../../utils/currency';

interface BreachExplanationCardProps {
  summary: string;
  breachDate: string | null;
  breachDay: ForecastDay | undefined;
  safetyReserveCents: number;
  evidenceIds: string[];
  currency: string;
}

export const BreachExplanationCard: React.FC<BreachExplanationCardProps> = ({
  summary,
  breachDate,
  breachDay,
  safetyReserveCents,
  evidenceIds,
  currency,
}) => {
  const hasEvidence = Array.isArray(evidenceIds) && evidenceIds.length > 0;

  return (
    <div className="rescue-explanation-card">
      <div className="explanation-card-header">
        <div className="explanation-title-group">
          <Info size={18} className="explanation-icon" />
          <h3 className="explanation-title">Evidence-Grounded Breach Analysis</h3>
        </div>
        <span className="zero-hallucination-badge">
          Zero-Hallucination Policy Active
        </span>
      </div>

      <div className="explanation-body">
        {/* Core reason summary from API response */}
        <div className="explanation-summary-quote">
          <p className="summary-text">"{summary}"</p>
        </div>

        {/* Mathematical fact grounding from forecast */}
        {breachDay ? (
          <div className="explanation-facts-box">
            <h4 className="facts-heading">Forecast Ledger Grounding:</h4>
            <div className="facts-grid">
              <div className="fact-item">
                <span className="fact-label">Breach Occurrence Date</span>
                <span className="fact-value font-mono">{breachDay.date}</span>
              </div>
              <div className="fact-item">
                <span className="fact-label">Opening Cash Balance</span>
                <span className="fact-value font-mono">
                  {formatCents(breachDay.opening_balance_cents, currency)}
                </span>
              </div>
              <div className="fact-item">
                <span className="fact-label">Projected Inflows (Receipts)</span>
                <span className="fact-value font-mono text-safe">
                  +{formatCents(breachDay.receipts_cents, currency)}
                </span>
              </div>
              <div className="fact-item">
                <span className="fact-label">Projected Outflows (Expenses)</span>
                <span className="fact-value font-mono text-danger">
                  -{formatCents(breachDay.expenses_cents, currency)}
                </span>
              </div>
              <div className="fact-item highlight">
                <span className="fact-label">Resulting Closing Balance</span>
                <span className="fact-value font-mono">
                  {formatCents(breachDay.closing_balance_cents, currency)}
                </span>
              </div>
              <div className="fact-item highlight">
                <span className="fact-label">Buffer Shortfall</span>
                <span className="fact-value font-mono text-danger">
                  -{formatCents(Math.max(0, safetyReserveCents - breachDay.closing_balance_cents), currency)}
                </span>
              </div>
            </div>
            <p className="facts-footer-note">
              On <strong>{breachDay.date}</strong>, outgoing disbursements of{' '}
              <strong>{formatCents(breachDay.expenses_cents, currency)}</strong> exceed the net
              available cash buffer, bringing the closing balance{' '}
              <strong>
                {formatCents(Math.max(0, safetyReserveCents - breachDay.closing_balance_cents), currency)}
              </strong>{' '}
              below the configured <strong>{formatCents(safetyReserveCents, currency)}</strong> threshold.
            </p>
          </div>
        ) : (
          <div className="explanation-facts-box safe-state">
            <p>
              {breachDate
                ? `Breach flagged for ${breachDate}. No additional daily ledger records required.`
                : 'No reserve breach detected in current forecast data. Balances remain strictly compliant.'}
            </p>
          </div>
        )}

        {/* Evidence IDs Section */}
        <div className="explanation-evidence-section">
          <div className="evidence-header-row">
            <span className="evidence-title">
              <FileText size={14} />
              <span>Grounded Evidence Citations</span>
            </span>
            <span className="evidence-count">
              {hasEvidence ? `${evidenceIds.length} Cited Record${evidenceIds.length > 1 ? 's' : ''}` : 'No Records Attached'}
            </span>
          </div>

          {hasEvidence ? (
            <div className="evidence-tags-list">
              {evidenceIds.map((id) => (
                <div key={id} className="evidence-chip">
                  <CheckCircle size={13} className="text-safe" />
                  <span className="evidence-id-text">{id}</span>
                  <span className="evidence-badge-sub">Grounded Contract ID</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="evidence-empty-notice">
              <AlertCircle size={14} className="text-muted" />
              <span>
                Evidence unavailable: No explicit transaction IDs were attached to this recommendation in the API response.
              </span>
            </div>
          )}

          <div className="evidence-governance-notice">
            Strict verification notice: Only evidence keys present in contracts, verified fixtures, or live ledger records are referenced. Unsupported evidence is never generated or labeled as verified.
          </div>
        </div>
      </div>
    </div>
  );
};
