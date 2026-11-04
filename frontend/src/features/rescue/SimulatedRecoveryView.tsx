import React from 'react';
import {
  Sparkles,
  AlertOctagon,
  ArrowRight,
  RotateCcw,
  ShieldCheck,
  CheckCircle2,
  TrendingUp,
} from 'lucide-react';
import type { SimulationResult } from './simulation';
import { formatCents } from '../../utils/currency';

interface SimulatedRecoveryViewProps {
  simulation: SimulationResult;
  currency: string;
  onResetSimulation: () => void;
}

export const SimulatedRecoveryView: React.FC<SimulatedRecoveryViewProps> = ({
  simulation,
  currency,
  onResetSimulation,
}) => {
  const {
    simulatedDays,
    originalMinBalanceCents,
    simulatedMinBalanceCents,
    safetyReserveCents,
    originalShortfallCents,
    simulatedShortfallCents,
    shortfallRecoveredCents,
    isBreachResolved,
    totalEstimatedImpactCents,
    activeAssumptions,
    simulatedActionsCount,
    disclaimer,
  } = simulation;

  if (simulatedActionsCount === 0) {
    return (
      <div className="simulation-empty-placeholder">
        <Sparkles size={28} className="empty-sparkle-icon" />
        <h4 className="empty-sim-heading">Simulate Recovery Interventions</h4>
        <p className="empty-sim-text">
          Select one or more ranked recommendations above to project hypothetical cash recovery
          and evaluate reserve breach closure without moving funds.
        </p>
      </div>
    );
  }

  const recoveryPct =
    originalShortfallCents > 0
      ? Math.min(100, Math.round((shortfallRecoveredCents / originalShortfallCents) * 100))
      : 100;

  return (
    <div className="simulation-container-card" data-testid="simulated-recovery-view">
      {/* Simulation Header */}
      <div className="sim-header-row">
        <div className="sim-title-group">
          <div className="sim-icon-pill">
            <Sparkles size={18} />
          </div>
          <div>
            <div className="sim-badge-row">
              <span className="sim-mode-tag">Simulated Projection</span>
              <span className="sim-count-tag">
                {simulatedActionsCount} Action{simulatedActionsCount > 1 ? 's' : ''} Modeled
              </span>
            </div>
            <h3 className="sim-main-heading">Hypothetical Liquidity Trajectory Preview</h3>
          </div>
        </div>

        <button
          type="button"
          className="sim-reset-btn"
          onClick={onResetSimulation}
          title="Reset active simulation"
        >
          <RotateCcw size={13} />
          <span>Reset Simulation</span>
        </button>
      </div>

      {/* Prominent Mandatory Non-Execution Disclaimer */}
      <div className="sim-governance-banner">
        <AlertOctagon size={18} className="text-warning flex-shrink-0" />
        <div className="sim-governance-text">
          <strong>Non-Execution Disclosure:</strong> {disclaimer}
        </div>
      </div>

      {/* Before vs. After KPI Comparison Cards */}
      <div className="sim-metrics-grid">
        {/* Metric 1: Shortfall Comparison */}
        <div className="sim-metric-card">
          <span className="sim-metric-title">Projected Reserve Shortfall</span>
          <div className="sim-comparison-row">
            <div className="comparison-side before">
              <span className="side-label">Before Simulation</span>
              <span className="side-value text-danger">
                {originalShortfallCents > 0
                  ? `-${formatCents(originalShortfallCents, currency)}`
                  : formatCents(0, currency)}
              </span>
            </div>
            <ArrowRight size={16} className="text-muted" />
            <div className="comparison-side after">
              <span className="side-label">After Simulated Recovery</span>
              <span className={`side-value ${simulatedShortfallCents > 0 ? 'text-warning' : 'text-safe'}`}>
                {simulatedShortfallCents > 0
                  ? `-${formatCents(simulatedShortfallCents, currency)}`
                  : formatCents(0, currency)}
              </span>
            </div>
          </div>
          <div className="sim-metric-footer">
            <span className="text-safe">+{formatCents(shortfallRecoveredCents, currency)}</span>{' '}
            gap closed ({recoveryPct}% of breach averted)
          </div>
        </div>

        {/* Metric 2: Minimum Closing Balance */}
        <div className="sim-metric-card">
          <span className="sim-metric-title">Minimum Horizon Cash Floor</span>
          <div className="sim-comparison-row">
            <div className="comparison-side before">
              <span className="side-label">Baseline Min</span>
              <span className="side-value font-mono">
                {formatCents(originalMinBalanceCents, currency)}
              </span>
            </div>
            <ArrowRight size={16} className="text-muted" />
            <div className="comparison-side after">
              <span className="side-label">Simulated Min</span>
              <span className={`side-value font-mono ${simulatedMinBalanceCents >= safetyReserveCents ? 'text-safe' : 'text-warning'}`}>
                {formatCents(simulatedMinBalanceCents, currency)}
              </span>
            </div>
          </div>
          <div className="sim-metric-footer">
            Safety reserve target: <strong>{formatCents(safetyReserveCents, currency)}</strong>
          </div>
        </div>

        {/* Metric 3: Total Simulated Injection */}
        <div className="sim-metric-card">
          <span className="sim-metric-title">Simulated Gross Impact</span>
          <div className="single-val-display">
            <span className="big-val text-safe">
              +{formatCents(totalEstimatedImpactCents, currency)}
            </span>
          </div>
          <div className="sim-metric-footer">
            Status:{' '}
            {isBreachResolved ? (
              <span className="text-safe font-semibold">
                ✓ Breach completely resolved in model
              </span>
            ) : (
              <span className="text-warning font-semibold">
                ⚠ Partial gap closure; additional runway needed
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Daily Timing Breakdown Table (Showing impact applied strictly by timing) */}
      <div className="sim-table-wrapper">
        <div className="table-intro-row">
          <span className="table-intro-title">
            <TrendingUp size={14} />
            <span>Daily Forecast Progression with Timing-Adjusted Impact</span>
          </span>
          <span className="table-intro-sub">
            Impacts apply strictly on each action's effective day and roll forward into cumulative liquidity.
          </span>
        </div>

        <div className="sim-table-overflow">
          <table className="sim-daily-table">
            <thead>
              <tr>
                <th>Forecast Date</th>
                <th>Baseline Balance</th>
                <th>Simulated Daily Delta</th>
                <th>Simulated Balance</th>
                <th>Reserve Status</th>
              </tr>
            </thead>
            <tbody>
              {simulatedDays.map((d) => {
                const isUnderOriginal = d.closing_balance_cents < safetyReserveCents;
                const isUnderSimulated = d.simulated_closing_balance_cents < safetyReserveCents;
                return (
                  <tr key={d.date} className={isUnderOriginal ? 'breach-row' : ''}>
                    <td className="font-mono">{d.date}</td>
                    <td className="font-mono">{formatCents(d.closing_balance_cents, currency)}</td>
                    <td className="font-mono text-safe">
                      {d.simulated_cumulative_impact_cents > 0
                        ? `+${formatCents(d.simulated_cumulative_impact_cents, currency)}`
                        : '$0.00'}
                    </td>
                    <td className={`font-mono font-bold ${isUnderSimulated ? 'text-danger' : 'text-safe'}`}>
                      {formatCents(d.simulated_closing_balance_cents, currency)}
                    </td>
                    <td>
                      {!isUnderSimulated ? (
                        <span className="reserve-status-pill safe">
                          <CheckCircle2 size={11} />
                          <span>Protected</span>
                        </span>
                      ) : (
                        <span className="reserve-status-pill danger">
                          <span>Deficit</span>
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Active Assumptions for Simulated Actions */}
      <div className="sim-assumptions-box">
        <div className="assumptions-box-header">
          <ShieldCheck size={15} />
          <span>Operational Assumptions Behind This Simulation ({activeAssumptions.length})</span>
        </div>
        <ul className="assumptions-checklist">
          {activeAssumptions.map((a, i) => (
            <li key={i} className="assumption-item-checked">
              <span className="check-bullet">✓</span>
              <span>{a}</span>
            </li>
          ))}
        </ul>
        <div className="assumptions-disclaimer">
          This preview will only match reality if each assumption above is fully met in actual business operations.
        </div>
      </div>
    </div>
  );
};
