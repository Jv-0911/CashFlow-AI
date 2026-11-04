import React from 'react';
import {
  ArrowRight,
  TrendingUp,
  TrendingDown,
  Calendar,
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react';
import type { ScenarioComparison } from '../../types/scenario';
import { formatCents } from '../../utils/currency';

interface ScenarioComparisonCardProps {
  comparison: ScenarioComparison;
  safetyReserveCents: number;
  currency: string;
}

export const ScenarioComparisonCard: React.FC<ScenarioComparisonCardProps> = ({
  comparison,
  safetyReserveCents,
  currency,
}) => {
  const {
    baseline_ending_balance_cents,
    scenario_ending_balance_cents,
    baseline_breach_date,
    scenario_breach_date,
    changes_applied,
    net_variance_cents = scenario_ending_balance_cents - baseline_ending_balance_cents,
    baseline_min_balance_cents = 0,
    scenario_min_balance_cents = 0,
  } = comparison;

  const isNetPositive = net_variance_cents >= 0;

  // Breach analysis
  let breachStatusText = 'Reserves Maintained';
  let breachStatusType: 'safe' | 'warning' | 'danger' = 'safe';

  if (!baseline_breach_date && scenario_breach_date) {
    breachStatusText = `New Breach Induced on ${scenario_breach_date}`;
    breachStatusType = 'danger';
  } else if (baseline_breach_date && !scenario_breach_date) {
    breachStatusText = 'Baseline Breach Averted';
    breachStatusType = 'safe';
  } else if (baseline_breach_date && scenario_breach_date) {
    if (scenario_breach_date < baseline_breach_date) {
      breachStatusText = `Breach Accelerated to ${scenario_breach_date}`;
      breachStatusType = 'danger';
    } else if (scenario_breach_date > baseline_breach_date) {
      breachStatusText = `Breach Delayed to ${scenario_breach_date}`;
      breachStatusType = 'warning';
    } else {
      breachStatusText = `Breach Confirmed on ${scenario_breach_date}`;
      breachStatusType = 'danger';
    }
  }

  return (
    <div className="scenario-comparison-card">
      <div className="comparison-card-header">
        <div className="header-title-group">
          <div className={`status-pill ${breachStatusType}`}>
            {breachStatusType === 'safe' ? (
              <ShieldCheck size={16} />
            ) : breachStatusType === 'warning' ? (
              <AlertTriangle size={16} />
            ) : (
              <ShieldAlert size={16} />
            )}
            <span>{breachStatusText}</span>
          </div>
          <h3 className="comparison-heading">Baseline vs. Scenario Impact Summary</h3>
        </div>

        <div className="changes-summary-pill">
          <span>{changes_applied.length} Parameter Shift{changes_applied.length > 1 ? 's' : ''}</span>
        </div>
      </div>

      <div className="comparison-kpi-grid">
        {/* KPI 1: Ending Balance Comparison */}
        <div className="comparison-kpi-item">
          <span className="kpi-label">Ending Horizon Balance</span>
          <div className="kpi-compare-row">
            <div className="side">
              <span className="side-caption">Baseline</span>
              <span className="side-number font-mono">
                {formatCents(baseline_ending_balance_cents, currency)}
              </span>
            </div>
            <ArrowRight size={14} className="text-muted" />
            <div className="side">
              <span className="side-caption">Scenario</span>
              <span className={`side-number font-mono ${isNetPositive ? 'text-safe' : 'text-danger'}`}>
                {formatCents(scenario_ending_balance_cents, currency)}
              </span>
            </div>
          </div>
          <div className="kpi-footer-variance">
            {isNetPositive ? <TrendingUp size={12} className="text-safe" /> : <TrendingDown size={12} className="text-danger" />}
            <span className={isNetPositive ? 'text-safe' : 'text-danger'}>
              {isNetPositive ? '+' : ''}{formatCents(net_variance_cents, currency)} Net Horizon Shift
            </span>
          </div>
        </div>

        {/* KPI 2: Earliest Breach Timing */}
        <div className="comparison-kpi-item">
          <span className="kpi-label">Earliest Reserve Breach</span>
          <div className="kpi-compare-row">
            <div className="side">
              <span className="side-caption">Baseline</span>
              <span className="side-number font-mono">
                {baseline_breach_date || 'None'}
              </span>
            </div>
            <ArrowRight size={14} className="text-muted" />
            <div className="side">
              <span className="side-caption">Scenario</span>
              <span className={`side-number font-mono ${scenario_breach_date ? 'text-danger' : 'text-safe'}`}>
                {scenario_breach_date || 'Safe'}
              </span>
            </div>
          </div>
          <div className="kpi-footer-variance">
            <Calendar size={12} />
            <span>Target Safety Reserve: {formatCents(safetyReserveCents, currency)}</span>
          </div>
        </div>

        {/* KPI 3: Minimum Cash Floor */}
        <div className="comparison-kpi-item">
          <span className="kpi-label">Minimum Projected Cash Floor</span>
          <div className="kpi-compare-row">
            <div className="side">
              <span className="side-caption">Baseline Min</span>
              <span className="side-number font-mono">
                {formatCents(baseline_min_balance_cents, currency)}
              </span>
            </div>
            <ArrowRight size={14} className="text-muted" />
            <div className="side">
              <span className="side-caption">Scenario Min</span>
              <span
                className={`side-number font-mono ${
                  scenario_min_balance_cents < safetyReserveCents ? 'text-warning' : 'text-safe'
                }`}
              >
                {formatCents(scenario_min_balance_cents, currency)}
              </span>
            </div>
          </div>
          <div className="kpi-footer-variance">
            <span>
              {scenario_min_balance_cents >= safetyReserveCents
                ? `Buffer: +${formatCents(scenario_min_balance_cents - safetyReserveCents, currency)} above target`
                : `Shortfall: -${formatCents(safetyReserveCents - scenario_min_balance_cents, currency)} deficit`}
            </span>
          </div>
        </div>
      </div>

      {/* Changes Applied Bullet List */}
      <div className="changes-applied-box">
        <span className="changes-title">Active What-If Assumptions Modeled:</span>
        <div className="changes-tags-row">
          {changes_applied.map((change, idx) => (
            <span key={idx} className="change-tag">
              <CheckCircle2 size={12} className="text-safe" />
              <span>{change}</span>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
};
