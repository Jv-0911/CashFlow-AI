import type { ForecastDay } from '../../types';
import { formatCents } from '../../utils/currency';
import { AlertCircle, CheckCircle2 } from 'lucide-react';

interface ForecastTableProps {
  days: ForecastDay[];
  safetyReserveCents: number;
  currency: string;
}

export function ForecastTable({ days, safetyReserveCents, currency }: ForecastTableProps) {
  // Helper for day of week
  const getDayOfWeek = (dateStr: string) => {
    try {
      const d = new Date(dateStr + 'T00:00:00');
      return d.toLocaleDateString('en-US', { weekday: 'short' });
    } catch {
      return '';
    }
  };

  if (days.length === 0) {
    return (
      <div className="forecast-table-card">
        <p style={{ color: '#9AA6B5', fontSize: 13, textAlign: 'center', margin: '20px 0' }}>
          No daily forecast entries available.
        </p>
      </div>
    );
  }

  return (
    <div className="forecast-table-card">
      <div className="table-header-row">
        <div>
          <h2 className="table-title">Daily Forecast Breakdown</h2>
          <p className="chart-subtitle" style={{ marginTop: 2 }}>
            Complete audit schedule of projected opening balance, cash receipts, disbursements, and safety buffer
          </p>
        </div>

        <span className="demo-banner-tag">
          {days.length} Days Projected
        </span>
      </div>

      <div className="table-responsive-wrapper">
        <table className="forecast-data-table" aria-label="Daily cash-flow forecast table">
          <thead>
            <tr>
              <th scope="col">Date</th>
              <th scope="col" style={{ textAlign: 'right' }}>Opening Balance</th>
              <th scope="col" style={{ textAlign: 'right' }}>Inflows (Receipts)</th>
              <th scope="col" style={{ textAlign: 'right' }}>Outflows (Expenses)</th>
              <th scope="col" style={{ textAlign: 'right' }}>Closing Balance</th>
              <th scope="col" style={{ textAlign: 'right' }}>Reserve Margin</th>
              <th scope="col" style={{ textAlign: 'center' }}>Runway Status</th>
            </tr>
          </thead>
          <tbody>
            {days.map((day) => {
              const isBreached = day.closing_balance_cents < safetyReserveCents;
              const reserveMarginCents = day.closing_balance_cents - safetyReserveCents;
              const dayName = getDayOfWeek(day.date);

              return (
                <tr key={day.date} className={isBreached ? 'row-breached' : ''}>
                  {/* Date Column */}
                  <td>
                    <div className="table-cell-date">
                      <span className="table-day-badge">{dayName}</span>
                      <span style={{ fontWeight: 600 }}>{day.date}</span>
                    </div>
                  </td>

                  {/* Opening Balance */}
                  <td style={{ textAlign: 'right', color: '#9AA6B5' }}>
                    {formatCents(day.opening_balance_cents, currency)}
                  </td>

                  {/* Inflows */}
                  <td style={{ textAlign: 'right' }}>
                    {day.receipts_cents > 0 ? (
                      <span className="num-inflow">+{formatCents(day.receipts_cents, currency)}</span>
                    ) : (
                      <span style={{ color: '#666A91' }}>$0.00</span>
                    )}
                  </td>

                  {/* Outflows */}
                  <td style={{ textAlign: 'right' }}>
                    {day.expenses_cents > 0 ? (
                      <span className="num-outflow">-{formatCents(day.expenses_cents, currency)}</span>
                    ) : (
                      <span style={{ color: '#666A91' }}>$0.00</span>
                    )}
                  </td>

                  {/* Closing Balance */}
                  <td style={{ textAlign: 'right' }}>
                    <span className={`num-closing ${isBreached ? 'warning' : ''}`}>
                      {formatCents(day.closing_balance_cents, currency)}
                    </span>
                  </td>

                  {/* Reserve Margin */}
                  <td style={{ textAlign: 'right' }}>
                    <span className={`margin-pill ${isBreached ? 'breached' : 'safe'}`}>
                      {reserveMarginCents >= 0 ? '+' : ''}
                      {formatCents(reserveMarginCents, currency)}
                    </span>
                  </td>

                  {/* Status Badge */}
                  <td style={{ textAlign: 'center' }}>
                    {isBreached ? (
                      <span className="margin-pill breached" title="Below Safety Reserve Threshold">
                        <AlertCircle size={12} />
                        <span>Shortfall</span>
                      </span>
                    ) : (
                      <span className="margin-pill safe" title="Above Safety Reserve Threshold">
                        <CheckCircle2 size={12} />
                        <span>Buffer Safe</span>
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
}
