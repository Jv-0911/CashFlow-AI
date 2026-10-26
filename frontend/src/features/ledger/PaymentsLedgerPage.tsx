import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  CreditCard,
  RefreshCw,
  AlertTriangle,
  ArrowLeft,
  Sparkles,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { getLedgerEntries } from '../../api/ledger';
import type { LedgerEntry, LedgerResponse } from '../../types/ledger';
import {
  calculateLedgerSummary,
  filterLedgerEntries,
  type LedgerFilterTab,
} from './ledger-math';
import { LedgerSummaryCards } from './LedgerSummaryCards';
import { LedgerControls } from './LedgerControls';
import { LedgerTable } from './LedgerTable';
import { LedgerDetailDrawer } from './LedgerDetailDrawer';
import '../../styles/ledger.css';

export const PaymentsLedgerPage: React.FC = () => {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [ledgerData, setLedgerData] = useState<LedgerResponse | null>(null);
  const [selectedEntry, setSelectedEntry] = useState<LedgerEntry | null>(null);
  const [currentTab, setCurrentTab] = useState<LedgerFilterTab>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [retrying, setRetrying] = useState<boolean>(false);

  const fetchLedger = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await getLedgerEntries();
      setLedgerData(res.data);
    } catch (err) {
      console.error('Failed to load ledger records:', err);
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to connect to recovery ledger service.'
      );
    } finally {
      setLoading(false);
      setRetrying(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    getLedgerEntries()
      .then((res) => {
        if (active) {
          setLedgerData(res.data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (active) {
          setError(
            err instanceof Error
              ? err.message
              : 'Unable to connect to recovery ledger service.'
          );
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  const handleRetry = () => {
    setRetrying(true);
    fetchLedger();
  };

  const entries = useMemo(() => ledgerData?.entries || [], [ledgerData]);
  const currency = ledgerData?.currency || 'USD';
  const isBackendUnavailable = !!ledgerData?.backend_unavailable;
  const isDemoMode = !!ledgerData?.is_demo;
  const showNotice = isBackendUnavailable || isDemoMode;

  // Real-time summary re-calculated across current entries
  const summary = useMemo(() => {
    return calculateLedgerSummary(entries);
  }, [entries]);

  // Filtered and searched entries
  const filteredEntries = useMemo(() => {
    return filterLedgerEntries(entries, currentTab, searchQuery);
  }, [entries, currentTab, searchQuery]);

  const handleClearFilters = () => {
    setCurrentTab('all');
    setSearchQuery('');
  };

  // Loading Skeleton State
  if (loading && !retrying) {
    return (
      <div className="ledger-page-container">
        <div className="ledger-summary-grid">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="ledger-kpi-card" style={{ height: 130 }}>
              <div
                className="skeleton-box"
                style={{
                  width: '40%',
                  height: 16,
                  background: 'rgba(51, 65, 85, 0.4)',
                  borderRadius: 4,
                }}
              />
              <div
                className="skeleton-box"
                style={{
                  width: '75%',
                  height: 32,
                  background: 'rgba(51, 65, 85, 0.4)',
                  borderRadius: 6,
                  marginTop: 8,
                }}
              />
              <div
                className="skeleton-box"
                style={{
                  width: '60%',
                  height: 12,
                  background: 'rgba(51, 65, 85, 0.3)',
                  borderRadius: 4,
                  marginTop: 4,
                }}
              />
            </div>
          ))}
        </div>
        <div
          className="ledger-table-card"
          style={{ height: 350, background: 'rgba(17, 25, 37, 0.6)' }}
        />
      </div>
    );
  }

  // Actionable Error State
  if (error && !ledgerData) {
    return (
      <div className="ledger-page-container">
        <div className="ledger-empty-state">
          <AlertTriangle size={36} className="text-danger" />
          <h4>Ledger Connection Error</h4>
          <p>{error}</p>
          <button
            type="button"
            className="empty-clear-btn"
            onClick={handleRetry}
          >
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="ledger-page-container">
      {/* Top Bar Navigation */}
      <div className="ledger-top-bar">
        <div className="top-bar-left">
          <Link to="/dashboard" className="back-nav-btn">
            <ArrowLeft size={14} />
            <span>Overview Dashboard</span>
          </Link>
          <div className="title-with-badge">
            <CreditCard size={20} className="text-accent" />
            <h1 className="ledger-page-title">Payments & Verified Ledger</h1>
            <span className="milestone-badge">Milestone 8</span>
          </div>
        </div>

        <div className="top-bar-right">
          <Link to="/dashboard/rescue" className="back-nav-btn">
            <Sparkles size={13} className="text-accent" />
            <span>AI Rescue Actions</span>
          </Link>

          <button
            type="button"
            className="refresh-btn"
            onClick={handleRetry}
            disabled={retrying}
            title="Reload ledger records and test API endpoint"
          >
            <RefreshCw size={13} className={retrying ? 'spin' : ''} />
            <span>{retrying ? 'Connecting...' : 'Refresh Ledger'}</span>
          </button>
        </div>
      </div>

      {/* Persistent Visible Notice when Backend Ledger API is Unavailable OR in Demo Mode */}
      {showNotice && (
        <div
          className="backend-unavailable-notice"
          data-testid="backend-unavailable-banner"
        >
          <div className="notice-left">
            <AlertTriangle size={18} className="text-warning flex-shrink-0" />
            <div>
              <span className="notice-title">
                {isBackendUnavailable ? (
                  <>
                    Backend Service Notice: <code>/api/v1/ledger</code> is Currently Unreachable
                  </>
                ) : (
                  'Demo Mode Active: Synthetic Recovery Records'
                )}
              </span>
              <p className="notice-desc">
                {isBackendUnavailable ? (
                  <>
                    Displaying synthetic demo records adhering to{' '}
                    <code>contracts/payment-ledger.example.json</code>. Live PayPal Sandbox
                    settlement and verification will be integrated by Member 3 in{' '}
                    <code>backend/app/ledger</code>.
                  </>
                ) : (
                  <>
                    Displaying synthetic demo records returned by backend. Live PayPal Sandbox
                    settlement and authoritative verification will be completed in{' '}
                    <code>backend/app/ledger</code>.
                  </>
                )}
              </p>
            </div>
          </div>
          {isBackendUnavailable && (
            <button
              type="button"
              className="notice-retry-btn"
              onClick={handleRetry}
              disabled={retrying}
            >
              <RefreshCw size={12} className={retrying ? 'spin' : ''} />
              <span>{retrying ? 'Retrying...' : 'Retry Endpoint'}</span>
            </button>
          )}
        </div>
      )}

      {/* Summary KPI Cards Grid */}
      <LedgerSummaryCards summary={summary} currency={currency} />

      {/* Filter Tabs & Search Controls */}
      <LedgerControls
        currentTab={currentTab}
        searchQuery={searchQuery}
        totalEntries={entries.length}
        filteredCount={filteredEntries.length}
        onTabChange={setCurrentTab}
        onSearchChange={setSearchQuery}
        onClearSearch={() => setSearchQuery('')}
      />

      {/* Ledger Table */}
      <LedgerTable
        entries={filteredEntries}
        currency={currency}
        selectedEntryId={selectedEntry?.ledger_entry_id || null}
        onSelectEntry={(entry) => setSelectedEntry(entry)}
        onClearFilters={handleClearFilters}
      />

      {/* Detail Slideover Drawer */}
      <LedgerDetailDrawer
        entry={selectedEntry}
        currency={currency}
        onClose={() => setSelectedEntry(null)}
      />
    </div>
  );
};
