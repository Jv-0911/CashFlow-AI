import React from 'react';
import {
  Flame,
  TrendingUp,
  Clock,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
} from 'lucide-react';
import type { CashFlowAnalyticsResult } from './analytics-math';
import { formatCents } from '../../utils/currency';

interface AnalyticsKpiCardsProps {
  analytics: CashFlowAnalyticsResult;
  currency: string;
}

export const AnalyticsKpiCards: React.FC<AnalyticsKpiCardsProps> = ({
  analytics,
  currency,
}) => {
  const isBreached =
    analytics.runway_reserve_breach_days === 0 ||
    analytics.current_balance_cents < analytics.safety_reserve_cents;

  return (
    <div className="analytics-kpi-grid">
      {/* 1. Average Daily Burn Rate */}
      <div className="analytics-card burn-card">
        <div className="card-header">
          <div className="card-icon-wrapper burn-icon">
            <Flame size={18} />
          </div>
          <span className="source-badge projection-badge" title="Derived from forecast daily expenses">
            Forecast Projection
          </span>
        </div>
        <div className="card-body">
          <span className="card-label">Average Daily Burn</span>
          <div className="card-value-row">
            <span className="card-value font-mono text-warning">
              {formatCents(analytics.avg_daily_burn_cents, currency)}
              <span className="card-value-unit">/day</span>
            </span>
          </div>
          <span className="card-subtext">
            Based on {formatCents(analytics.total_outflow_cents, currency)} total projected
            outflows over {analytics.horizon_days} days
          </span>
        </div>
      </div>

      {/* 2. Average Daily Inflow */}
      <div className="analytics-card inflow-card">
        <div className="card-header">
          <div className="card-icon-wrapper inflow-icon">
            <TrendingUp size={18} />
          </div>
          <span className="source-badge projection-badge" title="Derived from forecast daily receipts">
            Forecast Projection
          </span>
        </div>
        <div className="card-body">
          <span className="card-label">Average Daily Inflow</span>
          <div className="card-value-row">
            <span className="card-value font-mono text-safe">
              {formatCents(analytics.avg_daily_inflow_cents, currency)}
              <span className="card-value-unit">/day</span>
            </span>
          </div>
          <span className="card-subtext">
            Net daily velocity:{' '}
            <strong
              className={`font-mono ${
                analytics.net_daily_delta_cents >= 0 ? 'text-safe' : 'text-danger'
              }`}
            >
              {analytics.net_daily_delta_cents >= 0 ? '+' : ''}
              {formatCents(analytics.net_daily_delta_cents, currency)}/day
            </strong>
          </span>
        </div>
      </div>

      {/* 3. Estimated Cash Runway (Separate Zero Cash vs Reserve Breach) */}
      <div className="analytics-card runway-card">
        <div className="card-header">
          <div className="card-icon-wrapper runway-icon">
            <Clock size={18} />
          </div>
          <span
            className={`source-badge ${isBreached ? 'danger-badge' : 'projection-badge'}`}
          >
            {isBreached ? 'Reserve Breached' : 'Projected Runway'}
          </span>
        </div>
        <div className="card-body">
          <span className="card-label">Projected Cash Runway</span>
          <div className="card-value-row">
            {analytics.runway_zero_days !== null ? (
              <span className="card-value font-mono">
                {analytics.runway_zero_days}
                <span className="card-value-unit"> Days (Zero Cash)</span>
              </span>
            ) : (
              <span className="card-value font-mono text-safe">
                Sustainable
              </span>
            )}
          </div>
          <div className="runway-secondary-row">
            {isBreached ? (
              <span className="runway-breach-text text-danger">
                <AlertTriangle size={12} />
                Reserve buffer exhausted ({formatCents(analytics.safety_reserve_cents, currency)} target)
              </span>
            ) : analytics.runway_reserve_breach_days !== null ? (
              <span className="runway-breach-text text-warning">
                <Clock size={12} />
                {analytics.runway_reserve_breach_days} days until safety reserve threshold
              </span>
            ) : (
              <span className="runway-breach-text text-safe">
                <CheckCircle2 size={12} />
                Buffer above safety reserve maintained
              </span>
            )}
          </div>
        </div>
      </div>

      {/* 4. Recovery Efficiency (Strictly Verified Completed from Ledger) */}
      <div className="analytics-card recovery-card">
        <div className="card-header">
          <div className="card-icon-wrapper recovery-icon">
            <ShieldCheck size={18} />
          </div>
          <span className="source-badge actuals-badge" title="Derived strictly from verified provider settlements">
            Verified Actuals (Sample)
          </span>
        </div>
        <div className="card-body">
          <span className="card-label">Recovery Conversion Rate</span>
          <div className="card-value-row">
            {analytics.recovery_efficiency_pct !== null ? (
              <span className="card-value font-mono text-safe">
                {analytics.recovery_efficiency_pct}%
              </span>
            ) : (
              <span className="card-value font-mono text-muted">
                N/A
              </span>
            )}
          </div>
          <span className="card-subtext">
            {analytics.total_tracked_ledger_cents > 0 ? (
              <>
                <strong>{formatCents(analytics.verified_recovered_cents, currency)}</strong> verified of{' '}
                {formatCents(analytics.total_tracked_ledger_cents, currency)} tracked pipeline
              </>
            ) : (
              'No ledger pipeline records recorded yet'
            )}
          </span>
        </div>
      </div>
    </div>
  );
};
