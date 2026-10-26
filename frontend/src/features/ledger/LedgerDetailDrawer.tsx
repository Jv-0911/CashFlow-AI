import React from 'react';
import {
  X,
  ShieldCheck,
  Clock,
  AlertTriangle,
  FileText,
  CreditCard,
  Info,
  Lock,
} from 'lucide-react';
import type { LedgerEntry } from '../../types/ledger';
import { formatCents } from '../../utils/currency';
import { getStatusBadgeMetadata, isStrictlyVerified } from './ledger-math';

interface LedgerDetailDrawerProps {
  entry: LedgerEntry | null;
  currency: string;
  onClose: () => void;
}

export const LedgerDetailDrawer: React.FC<LedgerDetailDrawerProps> = ({
  entry,
  currency,
  onClose,
}) => {
  if (!entry) return null;

  const isVerified = isStrictlyVerified(entry);
  const isDemoRecord =
    entry.provider.toLowerCase().includes('sandbox') ||
    entry.ledger_entry_id.toLowerCase().includes('demo') ||
    entry.invoice_id.toLowerCase().includes('demo');

  const meta = getStatusBadgeMetadata(entry.status, entry.verified_at);

  return (
    <div className="ledger-drawer-backdrop" onClick={onClose}>
      <div
        className="ledger-drawer-container"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Ledger Record Detail"
      >
        {/* Drawer Header */}
        <div className="drawer-header">
          <div className="drawer-title-group">
            <div className="drawer-tags-row">
              <span className="drawer-tag">Audit Ledger Record</span>
              {isDemoRecord && (
                <span className="drawer-demo-badge font-mono">
                  Synthetic Demo Record
                </span>
              )}
            </div>
            <h3 className="drawer-title font-mono">{entry.ledger_entry_id}</h3>
          </div>
          <button
            type="button"
            className="drawer-close-btn"
            onClick={onClose}
            aria-label="Close drawer"
          >
            <X size={18} />
          </button>
        </div>

        {/* Amount & Status Card */}
        <div className="drawer-amount-card">
          <div className="amount-col">
            <span className="drawer-field-label">Transaction Amount</span>
            <span
              className={`drawer-amount-value font-mono ${
                isVerified ? 'text-safe' : ''
              }`}
            >
              {formatCents(entry.amount_cents, currency)}
            </span>
            <span className="drawer-amount-sub font-mono">
              {entry.amount_cents} integer cents ({entry.currency})
            </span>
          </div>

          <div className="status-col">
            <span className="drawer-field-label">Current Status</span>
            <span className={`status-pill pill-${meta.variant}`}>
              {isVerified ? (
                <ShieldCheck size={13} className="pill-icon" />
              ) : meta.variant === 'invoice' ? (
                <FileText size={13} className="pill-icon" />
              ) : meta.variant === 'failed' ? (
                <AlertTriangle size={13} className="pill-icon" />
              ) : (
                <Clock size={13} className="pill-icon" />
              )}
              <span>{meta.label}</span>
            </span>
            <span className="drawer-status-desc">{meta.description}</span>
          </div>
        </div>

        {/* Verification Status Banner */}
        {isVerified ? (
          <div className="drawer-verification-box verified-box">
            <ShieldCheck size={18} className="text-safe flex-shrink-0" />
            <div className="box-content">
              <strong>
                {isDemoRecord
                  ? 'Simulated Provider Settlement (Demo)'
                  : 'Provider-Verified Cash Recovery'}
              </strong>
              <p>
                {isDemoRecord
                  ? `Simulated settlement timestamped for ${entry.verified_at} in PayPal Sandbox environment. This is synthetic demo data and does not represent real deposited cash.`
                  : `Authoritative settlement reported by ${entry.provider} on ${entry.verified_at}. Counted toward verified recovered cash.`}
              </p>
            </div>
          </div>
        ) : (
          <div className="drawer-verification-box unverified-box">
            <Clock size={18} className="text-warning flex-shrink-0" />
            <div className="box-content">
              <strong>Pending Provider Settlement</strong>
              <p>
                This entry has not yet been confirmed by provider settlement webhooks. By policy,
                unverified funds are withheld from verified cash balances.
              </p>
            </div>
          </div>
        )}

        {/* Detailed Fields Grid */}
        <div className="drawer-fields-list">
          <div className="drawer-field-item">
            <span className="field-name">Invoice Reference</span>
            <span className="field-value font-mono">{entry.invoice_id}</span>
          </div>

          <div className="drawer-field-item">
            <span className="field-name">Payment Provider</span>
            <span className="field-value font-mono">
              <CreditCard size={13} className="field-icon" />
              {entry.provider} {isDemoRecord ? '(Sandbox Demo)' : ''}
            </span>
          </div>

          <div className="drawer-field-item">
            <span className="field-name">Created Timestamp</span>
            <span className="field-value font-mono">
              {entry.created_at || 'Recorded at baseline creation'}
            </span>
          </div>

          <div className="drawer-field-item">
            <span className="field-name">Verification Timestamp</span>
            <span className="field-value font-mono">
              {entry.verified_at || 'None (Pending)'}
            </span>
          </div>

          {entry.notes && (
            <div className="drawer-field-item full-width">
              <span className="field-name">Audit Rationale & Notes</span>
              <p className="field-notes-text">{entry.notes}</p>
            </div>
          )}
        </div>

        {/* Backend Governance Requirements */}
        <div className="drawer-governance-box">
          <div className="governance-title">
            <Lock size={13} className="text-accent" />
            <span>Backend Governance Requirements</span>
          </div>
          <ul className="governance-rules-list">
            <li>
              <Info size={12} className="text-muted flex-shrink-0" />
              <span>
                <strong>Authoritative Verification Requirement:</strong> Payment statuses must reflect
                authoritative provider settlement webhooks, never unverified UI actions or browser redirects.
              </span>
            </li>
            <li>
              <Info size={12} className="text-muted flex-shrink-0" />
              <span>
                <strong>Multi-Tenant Scoping Requirement:</strong> Real financial transactions require
                server-side authenticated business authorization; client-side filters do not establish tenant isolation.
              </span>
            </li>
            <li>
              <Info size={12} className="text-muted flex-shrink-0" />
              <span>
                <strong>Idempotent Recording Requirement:</strong> The backend ledger module is required
                to enforce duplicate prevention before recording cash recovery outcomes.
              </span>
            </li>
          </ul>
        </div>

        {/* Drawer Actions */}
        <div className="drawer-footer-actions">
          <button type="button" className="drawer-btn-secondary" onClick={onClose}>
            Close Inspection
          </button>
        </div>
      </div>
    </div>
  );
};
