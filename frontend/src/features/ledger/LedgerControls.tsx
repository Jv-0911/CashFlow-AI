import React from 'react';
import { Search, Filter, X } from 'lucide-react';
import type { LedgerFilterTab } from './ledger-math';

interface LedgerControlsProps {
  currentTab: LedgerFilterTab;
  searchQuery: string;
  totalEntries: number;
  filteredCount: number;
  onTabChange: (tab: LedgerFilterTab) => void;
  onSearchChange: (query: string) => void;
  onClearSearch: () => void;
}

export const LedgerControls: React.FC<LedgerControlsProps> = ({
  currentTab,
  searchQuery,
  totalEntries,
  filteredCount,
  onTabChange,
  onSearchChange,
  onClearSearch,
}) => {
  const tabs: { id: LedgerFilterTab; label: string }[] = [
    { id: 'all', label: 'All Records' },
    { id: 'verified_completed', label: 'Verified Completed' },
    { id: 'pending_verification', label: 'Pending Verification' },
    { id: 'invoices', label: 'Invoices Issued' },
    { id: 'unresolved', label: 'Unresolved / Failed' },
  ];

  return (
    <div className="ledger-controls-panel">
      {/* Tab Filter Buttons */}
      <div className="ledger-tabs-row" role="tablist">
        {tabs.map((tab) => {
          const isActive = currentTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={isActive}
              className={`ledger-tab-btn ${isActive ? 'active' : ''}`}
              onClick={() => onTabChange(tab.id)}
            >
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Search & Entry Counter */}
      <div className="ledger-search-row">
        <div className="ledger-search-input-wrapper">
          <Search size={14} className="search-icon" />
          <input
            type="text"
            className="ledger-search-input"
            placeholder="Search by invoice ID, ledger entry ID, provider, or notes..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
          />
          {searchQuery && (
            <button
              type="button"
              className="clear-search-btn"
              onClick={onClearSearch}
              title="Clear search query"
            >
              <X size={13} />
            </button>
          )}
        </div>

        <div className="ledger-filter-count">
          <Filter size={13} className="text-muted" />
          <span>
            Showing <strong>{filteredCount}</strong> of {totalEntries} entries
          </span>
        </div>
      </div>
    </div>
  );
};
