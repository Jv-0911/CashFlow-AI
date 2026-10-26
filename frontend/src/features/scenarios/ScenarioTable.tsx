import React from 'react';
import { Table, CheckCircle2, AlertTriangle } from 'lucide-react';
import type { CalculatedScenarioDay } from './scenario-math';
import { formatCents } from '../../utils/currency';

interface ScenarioTableProps {
  days: CalculatedScenarioDay[];
  safetyReserveCents: number;
  currency: string;
}

export const ScenarioTable: React.FC<ScenarioTableProps> = ({
  days,
  safetyReserveCents,
  currency,
}) => {
  return (
    <div className="scenario-table-container">
      <div className="table-header-row">
        <div className="table-title-group">
          <Table size={16} className="text-accent" />
          <h3 className="table-heading">Daily Projection & Divergence Breakdown</h3>
        </div>
        <span className="table-row-count">{days.length} Daily Intervals Modeled</span>
      </div>

      <div className="table-overflow-wrapper">
        <table className="scenario-breakdown-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Baseline Receipts</th>
              <th>Scenario Receipts</th>
              <th>Baseline Expenses</th>
              <th>Scenario Expenses</th>
              <th>Baseline Closing</th>
              <th>Scenario Closing</th>
              <th>Variance (Delta)</th>
              <th>Reserve Status</th>
            </tr>
          </thead>
          <tbody>
            {days.map((day) => {
              const isBreach = day.scenario_closing_cents < safetyReserveCents;
              const isPositive = day.variance_cents >= 0;

              return (
                <tr key={day.date} className={isBreach ? 'breach-row' : ''}>
                  <td className="font-mono">{day.date}</td>
                  <td className="font-mono text-muted">
                    {formatCents(day.baseline_receipts_cents, currency)}
                  </td>
                  <td className="font-mono text-safe">
                    {formatCents(day.scenario_receipts_cents, currency)}
                  </td>
                  <td className="font-mono text-muted">
                    {formatCents(day.baseline_expenses_cents, currency)}
                  </td>
                  <td className="font-mono text-warning">
                    {formatCents(day.scenario_expenses_cents, currency)}
                  </td>
                  <td className="font-mono text-muted">
                    {formatCents(day.baseline_closing_cents, currency)}
                  </td>
                  <td className="font-mono font-bold">
                    <span className={isBreach ? 'text-danger' : 'text-safe'}>
                      {formatCents(day.scenario_closing_cents, currency)}
                    </span>
                  </td>
                  <td className={`font-mono font-bold ${isPositive ? 'text-safe' : 'text-danger'}`}>
                    {isPositive ? '+' : ''}
                    {formatCents(day.variance_cents, currency)}
                  </td>
                  <td>
                    {!isBreach ? (
                      <span className="scenario-status-pill safe">
                        <CheckCircle2 size={11} />
                        <span>Protected</span>
                      </span>
                    ) : (
                      <span className="scenario-status-pill deficit">
                        <AlertTriangle size={11} />
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
  );
};
