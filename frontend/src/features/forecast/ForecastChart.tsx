import { useState, useRef } from 'react';
import type { ForecastDay } from '../../types';
import { formatCents } from '../../utils/currency';

interface ForecastChartProps {
  days: ForecastDay[];
  safetyReserveCents: number;
  currency: string;
}

export function ForecastChart({ days, safetyReserveCents, currency }: ForecastChartProps) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Dimensions
  const svgWidth = 840;
  const svgHeight = 320;
  const padding = { top: 25, right: 35, bottom: 45, left: 75 };

  const chartWidth = svgWidth - padding.left - padding.right;
  const chartHeight = svgHeight - padding.top - padding.bottom;

  if (days.length === 0) {
    return (
      <div className="chart-card" style={{ textAlign: 'center', padding: '40px 20px' }}>
        <p style={{ color: '#9AA6B5', fontSize: 13 }}>No daily forecast projections available to graph.</p>
      </div>
    );
  }

  // Calculate domain values
  const allValues = days.flatMap((d) => [
    d.opening_balance_cents,
    d.closing_balance_cents,
    d.receipts_cents,
    d.expenses_cents,
    safetyReserveCents,
  ]);
  const minValue = Math.min(0, ...allValues);
  const maxValue = Math.max(safetyReserveCents * 1.5, ...allValues) * 1.15;
  const valueRange = maxValue - minValue || 1;

  // Scale helpers
  const getX = (index: number) => {
    if (days.length <= 1) return padding.left + chartWidth / 2;
    return padding.left + (index / (days.length - 1)) * chartWidth;
  };

  const getY = (val: number) => {
    return padding.top + chartHeight - ((val - minValue) / valueRange) * chartHeight;
  };

  // Paths
  const closingPoints = days.map((d, i) => `${getX(i)},${getY(d.closing_balance_cents)}`);
  const closingPath = `M ${closingPoints.join(' L ')}`;

  const areaPath = `M ${getX(0)},${getY(0)} L ${closingPoints.join(' L ')} L ${getX(
    days.length - 1
  )},${getY(0)} Z`;

  const openingPoints = days.map((d, i) => `${getX(i)},${getY(d.opening_balance_cents)}`);
  const openingPath = `M ${openingPoints.join(' L ')}`;

  const safetyY = getY(safetyReserveCents);
  const hoveredDay = hoveredIndex !== null && days[hoveredIndex] ? days[hoveredIndex] : null;

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div className="chart-header-left">
          <h2 className="chart-title">Primary Cash-Flow Trajectory</h2>
          <p className="chart-subtitle">
            Opening balance, receipts, expenses, closing liquidity & reserve threshold
          </p>
        </div>

        {/* Legend */}
        <div className="chart-legend" style={{ marginBottom: 0 }}>
          <div className="legend-item">
            <span className="legend-dot" style={{ background: '#7896B0' }} />
            <span>Closing Balance</span>
          </div>
          <div className="legend-item">
            <span
              style={{
                width: 10,
                height: 2,
                borderTop: '2px dashed #607D98',
                display: 'inline-block',
              }}
            />
            <span>Opening Balance</span>
          </div>
          <div className="legend-item">
            <span className="legend-dot" style={{ background: '#34d399' }} />
            <span>Receipts</span>
          </div>
          <div className="legend-item">
            <span className="legend-dot" style={{ background: '#9A758D' }} />
            <span>Expenses</span>
          </div>
          <div className="legend-item">
            <span className="legend-line-dashed" />
            <span>Safety Reserve ({formatCents(safetyReserveCents, currency)})</span>
          </div>
        </div>
      </div>

      {/* SVG Canvas */}
      <div className="svg-chart-container" ref={containerRef} style={{ height: 320 }}>
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="svg-chart-canvas"
          preserveAspectRatio="none"
          role="img"
          aria-label="Cash flow forecast trajectory chart"
        >
          <defs>
            <linearGradient id="forecastAreaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#7896B0" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#7896B0" stopOpacity="0.0" />
            </linearGradient>

            <linearGradient id="receiptGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#34d399" stopOpacity="0.85" />
              <stop offset="100%" stopColor="#34d399" stopOpacity="0.3" />
            </linearGradient>

            <linearGradient id="expenseGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#9A758D" stopOpacity="0.85" />
              <stop offset="100%" stopColor="#9A758D" stopOpacity="0.3" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((pct, idx) => {
            const val = minValue + valueRange * pct;
            const y = padding.top + chartHeight * (1 - pct);
            return (
              <g key={idx}>
                <line
                  x1={padding.left}
                  y1={y}
                  x2={svgWidth - padding.right}
                  y2={y}
                  stroke="rgba(120, 150, 176, 0.1)"
                  strokeDasharray="4 4"
                />
                <text
                  x={padding.left - 10}
                  y={y + 4}
                  fill="#9AA6B5"
                  fontSize="10"
                  textAnchor="end"
                  fontFamily="Inter, sans-serif"
                >
                  {formatCents(val, currency)}
                </text>
              </g>
            );
          })}

          {/* Safety Reserve Threshold Line */}
          <line
            x1={padding.left}
            y1={safetyY}
            x2={svgWidth - padding.right}
            y2={safetyY}
            stroke="#f87171"
            strokeWidth="2"
            strokeDasharray="6 4"
            opacity="0.85"
          />
          <text
            x={svgWidth - padding.right}
            y={safetyY - 6}
            fill="#f87171"
            fontSize="10"
            fontWeight="bold"
            textAnchor="end"
          >
            Safety Reserve Threshold: {formatCents(safetyReserveCents, currency)}
          </text>

          {/* Daily Inflow & Outflow Bars */}
          {days.map((d, i) => {
            const cx = getX(i);
            const barW = Math.max(6, Math.min(20, (chartWidth / days.length) * 0.24));
            const zeroY = getY(0);

            const recH = (d.receipts_cents / valueRange) * chartHeight;
            const expH = (d.expenses_cents / valueRange) * chartHeight;

            return (
              <g key={`bars-${i}`}>
                {d.receipts_cents > 0 && (
                  <rect
                    x={cx - barW - 1}
                    y={zeroY - recH}
                    width={barW}
                    height={Math.max(2, recH)}
                    rx="3"
                    fill="url(#receiptGrad)"
                  />
                )}
                {d.expenses_cents > 0 && (
                  <rect
                    x={cx + 1}
                    y={zeroY - expH}
                    width={barW}
                    height={Math.max(2, expH)}
                    rx="3"
                    fill="url(#expenseGrad)"
                  />
                )}
              </g>
            );
          })}

          {/* Area under closing line */}
          <path d={areaPath} fill="url(#forecastAreaGrad)" />

          {/* Opening balance line (dashed secondary) */}
          <path
            d={openingPath}
            fill="none"
            stroke="#607D98"
            strokeWidth="1.5"
            strokeDasharray="4 3"
            opacity="0.65"
          />

          {/* Closing balance line (solid primary) */}
          <path
            d={closingPath}
            fill="none"
            stroke="#7896B0"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Data point markers and hover interactions */}
          {days.map((d, i) => {
            const cx = getX(i);
            const cy = getY(d.closing_balance_cents);
            const isHovered = hoveredIndex === i;
            const isUnderReserve = d.closing_balance_cents < safetyReserveCents;

            return (
              <g
                key={`point-${i}`}
                onMouseEnter={() => setHoveredIndex(i)}
                onMouseLeave={() => setHoveredIndex(null)}
                style={{ cursor: 'pointer' }}
              >
                {/* Hit target area */}
                <rect
                  x={cx - chartWidth / (days.length * 2)}
                  y={padding.top}
                  width={chartWidth / days.length}
                  height={chartHeight}
                  fill="transparent"
                />

                {/* Vertical hover crosshair */}
                {isHovered && (
                  <line
                    x1={cx}
                    y1={padding.top}
                    x2={cx}
                    y2={padding.top + chartHeight}
                    stroke="#7896B0"
                    strokeWidth="1.5"
                    strokeDasharray="3 3"
                    opacity="0.85"
                  />
                )}

                {/* Closing dot */}
                <circle
                  cx={cx}
                  cy={cy}
                  r={isHovered ? 6 : 4}
                  fill={isUnderReserve ? '#f87171' : isHovered ? '#E7E9ED' : '#7896B0'}
                  stroke="#111925"
                  strokeWidth="2"
                />

                {/* X axis date label */}
                <text
                  x={cx}
                  y={svgHeight - 16}
                  fill={isHovered ? '#E7E9ED' : '#9AA6B5'}
                  fontSize="10"
                  textAnchor="middle"
                  fontFamily="Inter, sans-serif"
                  fontWeight={isHovered ? 'bold' : 'normal'}
                >
                  {d.date.slice(5)}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Hover Tooltip */}
        {hoveredDay && hoveredIndex !== null && (
          <div
            className="chart-tooltip-box"
            style={{
              left: `${(getX(hoveredIndex) / svgWidth) * 100}%`,
              top: `${(getY(hoveredDay.closing_balance_cents) / svgHeight) * 100}%`,
            }}
          >
            <div style={{ fontWeight: 700, borderBottom: '1px solid rgba(120, 150, 176, 0.2)', paddingBottom: 4 }}>
              {hoveredDay.date}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
              <span style={{ color: '#9AA6B5' }}>Opening Balance:</span>
              <strong style={{ color: '#9AA6B5' }}>{formatCents(hoveredDay.opening_balance_cents, currency)}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
              <span style={{ color: '#34d399' }}>+ Receipts:</span>
              <span>{formatCents(hoveredDay.receipts_cents, currency)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
              <span style={{ color: '#9A758D' }}>- Expenses:</span>
              <span>{formatCents(hoveredDay.expenses_cents, currency)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, borderTop: '1px solid rgba(120, 150, 176, 0.15)', paddingTop: 4 }}>
              <span style={{ color: '#E7E9ED' }}>Closing Balance:</span>
              <strong style={{ color: hoveredDay.closing_balance_cents < safetyReserveCents ? '#f87171' : '#E7E9ED' }}>
                {formatCents(hoveredDay.closing_balance_cents, currency)}
              </strong>
            </div>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                gap: 12,
                fontSize: 11,
                color: hoveredDay.closing_balance_cents >= safetyReserveCents ? '#34d399' : '#f87171',
              }}
            >
              <span>Reserve Margin:</span>
              <span>
                {formatCents(hoveredDay.closing_balance_cents - safetyReserveCents, currency)}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
