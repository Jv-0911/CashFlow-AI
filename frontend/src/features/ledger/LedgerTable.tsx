import React from 'react';
import {
  ShieldCheck,
  Clock,
  FileText,
  AlertTriangle,
  Eye,
  Inbox,
} from 'lucide-react';
import type { LedgerEntry } from '../../types/ledger';
import { formatCents } from '../../utils/currency';
import { getStatusBadgeMetadata } from './ledger-math';

interface LedgerTableProps {
  entries: LedgerEntry[];
  currency: string;
  selectedEntryId: string | null;
  onSelectEntry: (entry: LedgerEntry) => void;
  onClearFilters?: () => void;
}

export const LedgerTable: React.FC<LedgerTableProps> = ({
  entries,
  currency,
  selectedEntryId,
  onSelectEntry,
  onClearFilters,
}) => {
  const formatDate = (isoString?: string | null) => {
    if (!isoString) return '—';
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
    } catch {
      return isoString;
    }
  };

  const renderStatusBadge = (entry: LedgerEntry) => {
    const meta = getStatusBadgeMetadata(entry.status, entry.verified_at);

    let Icon = Clock;
    if (meta.variant === 'verified') Icon = ShieldCheck;
    else if (meta.variant === 'invoice') Icon = FileText;
    else if (meta.variant === 'failed') Icon = AlertTriangle;

    return (
      <span
        className={`status-pill pill-${meta.variant}`}
        title={meta.description}
      >
        <Icon size={12} className="pill-icon" />
        <span>{meta.label}</span>
      </span>
    );
  };

  if (entries.length === 0) {
    return (
      <div className="ledger-empty-state">
        <Inbox size={36} className="text-muted" />
        <h4>No matching ledger entries found</h4>
        <p>
          No payment or recovery records match your current status filter and search query.
        </p>
        {onClearFilters && (
          <button
            type="button"
            className="empty-clear-btn"
            onClick={onClearFilters}
          >
            Clear Filters & Search
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="ledger-table-card">
      <div className="table-header-bar">
        <div>
          <h4 className="table-card-title">Recovery Audit Ledger</h4>
          <span className="table-card-sub">
            Authoritative provider settlements, issued invoices, and pending recovery actions
          </span>
        </div>
      </div>

      <div className="table-responsive-container">
        <table className="ledger-data-table">
          <thead>
            <tr>
              <th>Date / Created</th>
              <th>Ledger Entry ID</th>
              <th>Invoice Reference</th>
              <th>Provider</th>
              <th className="text-right">Amount</th>
              <th>Status</th>
              <th>Verified At</th>
              <th className="text-center">Action</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => {
              const isSelected = selectedEntryId === entry.ledger_entry_id;
              const isVerified =
                entry.status === 'verified_completed' &&
                !!entry.verified_at &&
                entry.verified_at.trim().length > 0;

              return (
                <tr
                  key={entry.ledger_entry_id}
                  className={`ledger-row ${isSelected ? 'row-selected' : ''}`}
                  onClick={() => onSelectEntry(entry)}
                >
                  {/* Date */}
                  <td className="cell-date font-mono text-muted">
                    {formatDate(entry.created_at || entry.verified_at)}
                  </td>

                  {/* Ledger Entry ID */}
                  <td className="cell-id">
                    <span className="id-badge font-mono">{entry.ledger_entry_id}</span>
                  </td>

                  {/* Invoice Reference */}
                  <td className="cell-invoice">
                    <span className="invoice-badge font-mono">
                      {entry.invoice_id}
                    </span>
                  </td>

                  {/* Provider */}
                  <td className="cell-provider">
                    <span className="provider-tag">
                      {entry.provider.replace('_', ' ')}
                    </span>
                  </td>

                  {/* Amount */}
                  <td className="cell-amount text-right font-mono">
                    <span
                      className={`amount-text ${
                        isVerified ? 'text-safe font-bold' : ''
                      }`}
                    >
                      {formatCents(entry.amount_cents, currency)}
                    </span>
                  </td>

                  {/* Status */}
                  <td className="cell-status">{renderStatusBadge(entry)}</td>

                  {/* Verified Timestamp */}
                  <td className="cell-verified font-mono text-muted text-xs">
                    {entry.verified_at ? (
                      <span className="verified-timestamp" title={entry.verified_at}>
                        {formatDate(entry.verified_at)}
                      </span>
                    ) : (
                      <span className="unverified-dash" title="Awaiting authoritative provider settlement verification">
                        Unverified
                      </span>
                    )}
                  </td>

                  {/* Action */}
                  <td className="cell-action text-center">
                    <button
                      type="button"
                      className="inspect-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectEntry(entry);
                      }}
                      title="Inspect record details"
                    >
                      <Eye size={13} />
                      <span>Inspect</span>
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
