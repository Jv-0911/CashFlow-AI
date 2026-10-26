import React, { useState } from 'react';
import type { ForecastDay } from '../../types/forecast';
import { formatCents } from '../../utils/currency';

interface CashFlowTrendChartProps {
  days: ForecastDay[];
  safetyReserveCents: number;
  currency: string;
}

export const CashFlowTrendChart: React.FC<CashFlowTrendChartProps> = ({
  days,
  safetyReserveCents,
  currency,
}) => {
  const [selectedRange, setSelectedRange] = useState<'7D' | '14D' | 'ALL'>('7D');
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  const displayDays =
    selectedRange === '7D'
      ? days.slice(0, 7)
      : selectedRange === '14D'
      ? days.slice(0, 14)
      : days;

  if (!displayDays || displayDays.length === 0) {
    return null;
  }

  // SVG Chart dimensions
  const svgWidth = 840;
  const svgHeight = 280;
  const padding = { top: 25, right: 30, bottom: 45, left: 65 };
  const chartWidth = svgWidth - padding.left - padding.right;
  const chartHeight = svgHeight - padding.top - padding.bottom;

  // Domain scaling
  const allValues = displayDays.flatMap((d) => [
    d.closing_balance_cents,
    d.receipts_cents,
    d.expenses_cents,
    safetyReserveCents,
  ]);
  const minValue = Math.min(0, ...allValues);
  const maxValue = Math.max(safetyReserveCents * 1.4, ...allValues) * 1.12;
  const range = maxValue - minValue || 1;

  const getX = (idx: number) => {
    if (displayDays.length <= 1) return padding.left + chartWidth / 2;
    return padding.left + (idx / (displayDays.length - 1)) * chartWidth;
  };

  const getY = (val: number) => {
    return padding.top + chartHeight - ((val - minValue) / range) * chartHeight;
  };

  // Generate closing balance trajectory line path
  const points = displayDays.map((d, i) => `${getX(i)},${getY(d.closing_balance_cents)}`);
  const linePath = points.length > 0 ? `M ${points.join(' L ')}` : '';
  const areaPath =
    points.length > 0
      ? `M ${getX(0)},${getY(0)} L ${points.join(' L ')} L ${getX(displayDays.length - 1)},${getY(0)} Z`
      : '';

  const safetyY = getY(safetyReserveCents);
  const hoveredDay = hoveredIdx !== null ? displayDays[hoveredIdx] : null;

  return (
    <div className="analytics-chart-card">
      <div className="chart-header-row">
        <div>
          <h4 className="chart-card-title">Projected Cash Trajectory & Net Velocity</h4>
          <span className="chart-card-subtitle">
            Daily balance trajectory (cyan) against safety reserve threshold (dashed red)
          </span>
        </div>

        <div className="range-selector-group">
          {(['7D', '14D', 'ALL'] as const).map((r) => (
            <button
              key={r}
              type="button"
              className={`range-btn ${selectedRange === r ? 'active' : ''}`}
              onClick={() => setSelectedRange(r)}
            >
              {r === 'ALL' ? `${days.length}D Horizon` : r}
            </button>
          ))}
        </div>
      </div>

      <div className="svg-container">
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="analytics-svg"
          preserveAspectRatio="none"
        >
          <defs>
            <linearGradient id="balanceAreaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#38bdf8" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines (horizontal) */}
          {[0, 0.25, 0.5, 0.75, 1].map((pct, i) => {
            const y = padding.top + chartHeight * pct;
            const val = maxValue - pct * range;
            return (
              <g key={i}>
                <line
                  x1={padding.left}
                  y1={y}
                  x2={padding.left + chartWidth}
                  y2={y}
                  stroke="rgba(51, 65, 85, 0.35)"
                  strokeDasharray="3 3"
                />
                <text
                  x={padding.left - 10}
                  y={y + 4}
                  fill="#64748b"
                  fontSize="10"
                  textAnchor="end"
                  fontFamily="monospace"
                >
                  {formatCents(Math.round(val), currency)}
                </text>
              </g>
            );
          })}

          {/* Safety Reserve Line */}
          <line
            x1={padding.left}
            y1={safetyY}
            x2={padding.left + chartWidth}
            y2={safetyY}
            stroke="#ef4444"
            strokeWidth="1.5"
            strokeDasharray="4 4"
          />
          <text
            x={padding.left + chartWidth - 6}
            y={safetyY - 5}
            fill="#ef4444"
            fontSize="10.5"
            fontWeight="bold"
            textAnchor="end"
          >
            Safety Reserve ({formatCents(safetyReserveCents, currency)})
          </text>

          {/* Area fill under closing balance */}
          {areaPath && <path d={areaPath} fill="url(#balanceAreaGrad)" />}

          {/* Daily Inflow / Outflow impulse bars */}
          {displayDays.map((d, i) => {
            const x = getX(i);
            const inflowY = getY(d.receipts_cents);
            const outflowY = getY(d.expenses_cents);
            const baseY = getY(0);

            return (
              <g key={i} className="daily-bars-group">
                {/* Receipts bar (green) */}
                {d.receipts_cents > 0 && (
                  <line
                    x1={x - 4}
                    y1={baseY}
                    x2={x - 4}
                    y2={inflowY}
                    stroke="#10b981"
                    strokeWidth="3.5"
                    strokeLinecap="round"
                    opacity="0.8"
                  />
                )}
                {/* Expenses bar (amber) */}
                {d.expenses_cents > 0 && (
                  <line
                    x1={x + 4}
                    y1={baseY}
                    x2={x + 4}
                    y2={outflowY}
                    stroke="#f59e0b"
                    strokeWidth="3.5"
                    strokeLinecap="round"
                    opacity="0.8"
                  />
                )}
              </g>
            );
          })}

          {/* Closing balance trajectory line */}
          {linePath && (
            <path
              d={linePath}
              fill="none"
              stroke="#38bdf8"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* Data point markers */}
          {displayDays.map((d, i) => {
            const x = getX(i);
            const y = getY(d.closing_balance_cents);
            const isHovered = hoveredIdx === i;

            return (
              <circle
                key={i}
                cx={x}
                cy={y}
                r={isHovered ? 5.5 : 3.5}
                fill={d.closing_balance_cents < safetyReserveCents ? '#ef4444' : '#38bdf8'}
                stroke="#111925"
                strokeWidth="2"
                style={{ cursor: 'pointer' }}
                onMouseEnter={() => setHoveredIdx(i)}
                onMouseLeave={() => setHoveredIdx(null)}
              />
            );
          })}

          {/* X Axis Date Labels */}
          {displayDays.map((d, i) => {
            const x = getX(i);
            // Show every other label on dense view
            if (displayDays.length > 14 && i % 3 !== 0) return null;
            return (
              <text
                key={i}
                x={x}
                y={padding.top + chartHeight + 20}
                fill="#94a3b8"
                fontSize="10"
                textAnchor="middle"
                fontFamily="monospace"
              >
                {d.date.slice(5)}
              </text>
            );
          })}
        </svg>
      </div>

      {/* Hover Detail Strip */}
      {hoveredDay ? (
        <div className="chart-hover-strip">
          <span className="hover-date font-mono">Date: {hoveredDay.date}</span>
          <span className="hover-item">
            Inflow:{' '}
            <strong className="text-safe font-mono">
              +{formatCents(hoveredDay.receipts_cents, currency)}
            </strong>
          </span>
          <span className="hover-item">
            Outflow:{' '}
            <strong className="text-warning font-mono">
              -{formatCents(hoveredDay.expenses_cents, currency)}
            </strong>
          </span>
          <span className="hover-item">
            Closing:{' '}
            <strong
              className={`font-mono ${
                hoveredDay.closing_balance_cents < safetyReserveCents
                  ? 'text-danger'
                  : 'text-accent'
              }`}
            >
              {formatCents(hoveredDay.closing_balance_cents, currency)}
            </strong>
          </span>
        </div>
      ) : (
        <div className="chart-legend-strip">
          <span className="legend-item">
            <span className="legend-dot" style={{ background: '#38bdf8' }} />
            Closing Balance
          </span>
          <span className="legend-item">
            <span className="legend-dot" style={{ background: '#10b981' }} />
            Receipts (Inflow)
          </span>
          <span className="legend-item">
            <span className="legend-dot" style={{ background: '#f59e0b' }} />
            Expenses (Outflow)
          </span>
          <span className="legend-item">
            <span className="legend-dash" style={{ borderColor: '#ef4444' }} />
            Safety Reserve
          </span>
        </div>
      )}
    </div>
  );
};
