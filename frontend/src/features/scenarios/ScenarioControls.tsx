import React from 'react';
import {
  Clock,
  UserPlus,
  TrendingUp,
  TrendingDown,
  Sliders,
  RotateCcw,
  AlertCircle,
  Shield,
} from 'lucide-react';
import type { ScenarioModifiers, ScenarioPresetId } from '../../types/scenario';
import { formatCents } from '../../utils/currency';

interface ScenarioControlsProps {
  modifiers: ScenarioModifiers;
  safetyReserveCents: number;
  currency: string;
  horizonDays: number;
  uncollectedDelayedCents: number;
  onModifierChange: (newModifiers: ScenarioModifiers) => void;
  onSafetyReserveChange: (cents: number) => void;
  onReset: () => void;
}

interface PresetOption {
  id: ScenarioPresetId;
  title: string;
  description: string;
  icon: React.ReactNode;
  modifiers: ScenarioModifiers;
}

export const ScenarioControls: React.FC<ScenarioControlsProps> = ({
  modifiers,
  safetyReserveCents,
  currency,
  horizonDays,
  uncollectedDelayedCents,
  onModifierChange,
  onSafetyReserveChange,
  onReset,
}) => {
  const presets: PresetOption[] = [
    {
      id: 'delayed_receivables',
      title: 'Delayed Receivables',
      description: 'Customer collections deferred by +14 days',
      icon: <Clock size={16} />,
      modifiers: {
        preset_id: 'delayed_receivables',
        delayed_receivables_days: 14,
        receipts_modifier_pct: 0,
        expenses_modifier_pct: 0,
        lump_sum_expense_cents: 0,
      },
    },
    {
      id: 'headcount_expansion',
      title: 'Headcount Expansion',
      description: 'New senior engineering hire ($6,500/mo ongoing payroll)',
      icon: <UserPlus size={16} />,
      modifiers: {
        preset_id: 'headcount_expansion',
        delayed_receivables_days: 0,
        receipts_modifier_pct: 0,
        expenses_modifier_pct: 0,
        lump_sum_expense_cents: 0,
        recurring_payroll_cents: 650000,
      },
    },

    {
      id: 'vendor_price_hike',
      title: 'Vendor Cost Hike',
      description: 'Key supplier disbursements rise by +15%',
      icon: <TrendingUp size={16} />,
      modifiers: {
        preset_id: 'vendor_price_hike',
        delayed_receivables_days: 0,
        receipts_modifier_pct: 0,
        expenses_modifier_pct: 15,
        lump_sum_expense_cents: 0,
      },
    },
    {
      id: 'revenue_dip',
      title: 'Revenue Dip Stress Test',
      description: 'Incoming sales receipts contract by -20%',
      icon: <TrendingDown size={16} />,
      modifiers: {
        preset_id: 'revenue_dip',
        delayed_receivables_days: 0,
        receipts_modifier_pct: -20,
        expenses_modifier_pct: 0,
        lump_sum_expense_cents: 0,
      },
    },
  ];

  const currentPresetId = modifiers.preset_id || 'custom';

  const handleSelectPreset = (preset: PresetOption) => {
    onModifierChange(preset.modifiers);
  };

  const handleCustomChange = <K extends keyof ScenarioModifiers>(
    field: K,
    val: ScenarioModifiers[K]
  ) => {
    onModifierChange({
      ...modifiers,
      preset_id: 'custom',
      [field]: val,
    });
  };

  return (
    <div className="scenario-controls-panel">
      <div className="controls-header-row">
        <div>
          <h3 className="controls-title">What-If Scenario Presets</h3>
          <p className="controls-subtitle">
            Model stressed business conditions or evaluate expansion commitments against your baseline forecast.
          </p>
        </div>

        <button
          type="button"
          className="scenario-reset-btn"
          onClick={onReset}
          title="Reset all scenario adjustments to baseline"
        >
          <RotateCcw size={13} />
          <span>Reset to Baseline</span>
        </button>
      </div>

      {/* Preset Buttons Grid */}
      <div className="presets-grid">
        {presets.map((preset) => {
          const isActive = currentPresetId === preset.id;
          return (
            <button
              key={preset.id}
              type="button"
              className={`preset-card-btn ${isActive ? 'active' : ''}`}
              onClick={() => handleSelectPreset(preset)}
            >
              <div className="preset-icon-wrapper">{preset.icon}</div>
              <div className="preset-text-wrapper">
                <span className="preset-title">{preset.title}</span>
                <span className="preset-desc">{preset.description}</span>
              </div>
            </button>
          );
        })}
      </div>

      {/* Fine-Tuning Custom Controls */}
      <div className="custom-tuning-section">
        <div className="tuning-section-header">
          <Sliders size={14} />
          <span>Fine-Tune What-If Parameters</span>
          {currentPresetId !== 'custom' && (
            <span className="preset-active-indicator">
              Preset Active: {presets.find((p) => p.id === currentPresetId)?.title}
            </span>
          )}
        </div>

        <div className="tuning-inputs-grid">
          {/* Delayed Receivables (Days) */}
          <div className="tuning-field">
            <div className="field-label-row">
              <label htmlFor="delayed-days-input">Receivables Delay</label>
              <span className="field-value-badge font-mono">
                +{modifiers.delayed_receivables_days} Days
              </span>
            </div>
            <input
              id="delayed-days-input"
              type="range"
              min="0"
              max="45"
              step="1"
              value={modifiers.delayed_receivables_days}
              onChange={(e) =>
                handleCustomChange('delayed_receivables_days', parseInt(e.target.value, 10) || 0)
              }
              className="scenario-range-slider"
            />
            <span className="field-hint">
              Shifts projected customer payment dates forward by exact calendar days.
            </span>
          </div>

          {/* Revenue Receipts Modifier (%) */}
          <div className="tuning-field">
            <div className="field-label-row">
              <label htmlFor="receipts-mod-input">Receipts Shift (%)</label>
              <span
                className={`field-value-badge font-mono ${
                  modifiers.receipts_modifier_pct > 0
                    ? 'text-safe'
                    : modifiers.receipts_modifier_pct < 0
                    ? 'text-danger'
                    : ''
                }`}
              >
                {modifiers.receipts_modifier_pct > 0 ? '+' : ''}
                {modifiers.receipts_modifier_pct}%
              </span>
            </div>
            <input
              id="receipts-mod-input"
              type="range"
              min="-100"
              max="100"
              step="5"
              value={modifiers.receipts_modifier_pct}
              onChange={(e) =>
                handleCustomChange('receipts_modifier_pct', parseInt(e.target.value, 10) || 0)
              }
              className="scenario-range-slider"
            />
            <span className="field-hint">
              Multiplies incoming revenue across all non-delayed receipts.
            </span>
          </div>

          {/* Expenses Modifier (%) */}
          <div className="tuning-field">
            <div className="field-label-row">
              <label htmlFor="expenses-mod-input">Expenses Shift (%)</label>
              <span
                className={`field-value-badge font-mono ${
                  modifiers.expenses_modifier_pct > 0
                    ? 'text-warning'
                    : modifiers.expenses_modifier_pct < 0
                    ? 'text-safe'
                    : ''
                }`}
              >
                {modifiers.expenses_modifier_pct > 0 ? '+' : ''}
                {modifiers.expenses_modifier_pct}%
              </span>
            </div>
            <input
              id="expenses-mod-input"
              type="range"
              min="-100"
              max="100"
              step="5"
              value={modifiers.expenses_modifier_pct}
              onChange={(e) =>
                handleCustomChange('expenses_modifier_pct', parseInt(e.target.value, 10) || 0)
              }
              className="scenario-range-slider"
            />
            <span className="field-hint">
              Scales recurring operational and vendor disbursements.
            </span>
          </div>

          {/* Recurring Monthly Payroll (Integer Cents) */}
          <div className="tuning-field">
            <div className="field-label-row">
              <label htmlFor="recurring-payroll-input">Monthly Recurring Payroll</label>
              <span className="field-value-badge font-mono text-warning">
                {formatCents(modifiers.recurring_payroll_cents || 0, currency)}/mo
              </span>
            </div>
            <input
              id="recurring-payroll-input"
              type="number"
              min="0"
              step="500"
              value={Math.round((modifiers.recurring_payroll_cents || 0) / 100)}
              onChange={(e) => {
                const dollars = Math.max(0, parseInt(e.target.value, 10) || 0);
                handleCustomChange('recurring_payroll_cents', dollars * 100);
              }}
              className="scenario-number-input"
              placeholder="0"
            />
            <span className="field-hint">
              Committed recurring salary disbursed on Day 1 and repeating every 30 days.
            </span>
          </div>

          {/* One-Time Capex / Lump-Sum (Integer Cents) */}
          <div className="tuning-field">
            <div className="field-label-row">
              <label htmlFor="lump-sum-input">One-Time Capex / Expense</label>

              <span className="field-value-badge font-mono text-warning">
                {formatCents(modifiers.lump_sum_expense_cents, currency)}
              </span>
            </div>
            <input
              id="lump-sum-input"
              type="number"
              min="0"
              step="100"
              value={Math.round(modifiers.lump_sum_expense_cents / 100)}
              onChange={(e) => {
                const dollars = Math.max(0, parseInt(e.target.value, 10) || 0);
                handleCustomChange('lump_sum_expense_cents', dollars * 100);
              }}
              className="scenario-number-input"
              placeholder="0"
            />
            <span className="field-hint">
              Immediate disbursement simulated on Day 1 of the horizon.
            </span>
          </div>

          {/* Configured Safety Reserve Threshold */}
          <div className="tuning-field">
            <div className="field-label-row">
              <label htmlFor="safety-reserve-input">
                <Shield size={12} style={{ display: 'inline', marginRight: 4 }} />
                Safety Reserve Target
              </label>
              <span className="field-value-badge font-mono">
                {formatCents(safetyReserveCents, currency)}
              </span>
            </div>
            <input
              id="safety-reserve-input"
              type="number"
              min="0"
              step="100"
              value={Math.round(safetyReserveCents / 100)}
              onChange={(e) => {
                const dollars = Math.max(0, parseInt(e.target.value, 10) || 0);
                onSafetyReserveChange(dollars * 100);
              }}
              className="scenario-number-input"
              placeholder="1000"
            />
            <span className="field-hint">
              Minimum policy buffer to maintain before breach alert triggers.
            </span>
          </div>
        </div>

        {/* Delayed Receivables Horizon Limit Notice */}
        {modifiers.delayed_receivables_days > 0 && uncollectedDelayedCents > 0 && (
          <div className="delayed-horizon-warning">
            <AlertCircle size={15} className="text-warning flex-shrink-0" />
            <div className="warning-text">
              <strong>Horizon Boundary Effect:</strong> Delaying receipts by{' '}
              {modifiers.delayed_receivables_days} days causes{' '}
              <strong>{formatCents(uncollectedDelayedCents, currency)}</strong> of expected customer
              collections to fall beyond the current {horizonDays}-day horizon. These funds are not
              treated as collected in this projection.
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
