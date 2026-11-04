import React from 'react';
import { ShieldCheck, Clock, AlertOctagon, Layers } from 'lucide-react';
import type { LedgerSummary } from '../../types/ledger';
import { formatCents } from '../../utils/currency';

interface LedgerSummaryCardsProps {
  summary: LedgerSummary;
  currency: string;
}

export const LedgerSummaryCards: React.FC<LedgerSummaryCardsProps> = ({
  summary,
  currency,
}) => {
  return (
    <div className="ledger-summary-grid">
      {/* 1. Verified Recovered Cash (Strictly Verified Completed only) */}
      <div className="ledger-kpi-card verified-card">
        <div className="kpi-header">
          <div className="kpi-icon-wrapper verified-icon">
            <ShieldCheck size={18} />
          </div>
          <span className="kpi-badge verified-badge">
            {summary.verified_entries} Verified
          </span>
        </div>
        <div className="kpi-body">
          <span className="kpi-label">Verified Recovered Cash</span>
          <div className="kpi-value-row">
            <span className="kpi-value text-safe font-mono">
              {formatCents(summary.verified_recovered_cents, currency)}
            </span>
          </div>
          <span className="kpi-subtext">
            Confirmed by provider with authoritative verification timestamp
          </span>
        </div>
      </div>

      {/* 2. Pending Provider Verification */}
      <div className="ledger-kpi-card pending-card">
        <div className="kpi-header">
          <div className="kpi-icon-wrapper pending-icon">
            <Clock size={18} />
          </div>
          <span className="kpi-badge pending-badge">
            {summary.pending_entries} Pending
          </span>
        </div>
        <div className="kpi-body">
          <span className="kpi-label">Pending Verification</span>
          <div className="kpi-value-row">
            <span className="kpi-value text-warning font-mono">
              {formatCents(summary.pending_verification_cents, currency)}
            </span>
          </div>
          <span className="kpi-subtext">
            Proposed, approved or pending; not verified recovered cash
          </span>
        </div>
      </div>

      {/* 3. Unresolved / Failed / Cancelled */}
      <div className="ledger-kpi-card unresolved-card">
        <div className="kpi-header">
          <div className="kpi-icon-wrapper unresolved-icon">
            <AlertOctagon size={18} />
          </div>
          <span className="kpi-badge unresolved-badge">
            {summary.unresolved_entries} Unresolved
          </span>
        </div>
        <div className="kpi-body">
          <span className="kpi-label">Unresolved / Declined</span>
          <div className="kpi-value-row">
            <span className="kpi-value text-danger font-mono">
              {formatCents(summary.unresolved_failed_cents, currency)}
            </span>
          </div>
          <span className="kpi-subtext">
            Declined, cancelled, or expired without payment authorization
          </span>
        </div>
      </div>

      {/* 4. Total Tracked Ledger Pipeline */}
      <div className="ledger-kpi-card total-card">
        <div className="kpi-header">
          <div className="kpi-icon-wrapper total-icon">
            <Layers size={18} />
          </div>
          <span className="kpi-badge total-badge">
            {summary.total_entries} Records
          </span>
        </div>
        <div className="kpi-body">
          <span className="kpi-label">Total Tracked Ledger</span>
          <div className="kpi-value-row">
            <span className="kpi-value font-mono">
              {formatCents(summary.total_tracked_cents, currency)}
            </span>
          </div>
          <span className="kpi-subtext">
            Cumulative recovery and invoice entries recorded in audit ledger
          </span>
        </div>
      </div>
    </div>
  );
};
