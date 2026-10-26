import React from 'react';
import { ArrowUpRight, ArrowDownRight, GitCommit } from 'lucide-react';
import type { ForecastDay } from '../../types/forecast';
import { calculatePeriodComparison } from './analytics-math';
import { formatCents } from '../../utils/currency';

interface PeriodComparisonCardProps {
  days: ForecastDay[];
  currency: string;
}

export const PeriodComparisonCard: React.FC<PeriodComparisonCardProps> = ({
  days,
  currency,
}) => {
  const comparison = calculatePeriodComparison(days);
  if (!comparison) return null;

  const halfSize = Math.floor(days.length / 2);

  return (
    <div className="period-comparison-card">
      <div className="period-header">
        <GitCommit size={16} className="text-accent" />
        <div>
          <h4 className="period-title">Horizon Period Velocity Comparison</h4>
          <span className="period-subtitle">
            Compares the first {halfSize} days against the subsequent {days.length - halfSize} days
          </span>
        </div>
      </div>

      <div className="period-metrics-grid">
        {/* Inflows Comparison */}
        <div className="period-metric-box">
          <span className="period-box-label">Inflow Velocity</span>
          <div className="period-box-values">
            <div>
              <span className="period-phase-tag">Days 1–{halfSize}</span>
              <span className="period-cents font-mono">
                {formatCents(comparison.first_half_inflow_cents, currency)}
              </span>
            </div>
            <div className="variance-indicator">
              {comparison.inflow_variance_cents >= 0 ? (
                <span className="variance-pill text-safe">
                  <ArrowUpRight size={13} />
                  +{formatCents(comparison.inflow_variance_cents, currency)}
                </span>
              ) : (
                <span className="variance-pill text-warning">
                  <ArrowDownRight size={13} />
                  {formatCents(comparison.inflow_variance_cents, currency)}
                </span>
              )}
            </div>
            <div>
              <span className="period-phase-tag">Days {halfSize + 1}–{days.length}</span>
              <span className="period-cents font-mono text-safe">
                {formatCents(comparison.second_half_inflow_cents, currency)}
              </span>
            </div>
          </div>
        </div>

        {/* Outflows Comparison */}
        <div className="period-metric-box">
          <span className="period-box-label">Outflow (Expense) Velocity</span>
          <div className="period-box-values">
            <div>
              <span className="period-phase-tag">Days 1–{halfSize}</span>
              <span className="period-cents font-mono">
                {formatCents(comparison.first_half_outflow_cents, currency)}
              </span>
            </div>
            <div className="variance-indicator">
              {comparison.outflow_variance_cents <= 0 ? (
                <span className="variance-pill text-safe">
                  <ArrowDownRight size={13} />
                  {formatCents(comparison.outflow_variance_cents, currency)}
                </span>
              ) : (
                <span className="variance-pill text-warning">
                  <ArrowUpRight size={13} />
                  +{formatCents(comparison.outflow_variance_cents, currency)}
                </span>
              )}
            </div>
            <div>
              <span className="period-phase-tag">Days {halfSize + 1}–{days.length}</span>
              <span className="period-cents font-mono text-warning">
                {formatCents(comparison.second_half_outflow_cents, currency)}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
