import { useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import type { ForecastDay } from '../../../types';

interface CashFlowChartProps {
  days: ForecastDay[];
  safetyReserveCents: number;
  currency: string;
}

export function CashFlowChart({ days, safetyReserveCents, currency }: CashFlowChartProps) {
  const [selectedRange, setSelectedRange] = useState<'7D' | '14D' | '30D'>('7D');
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Format currency helpers
  const formatCurrency = (cents: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency || 'USD',
      maximumFractionDigits: 0,
    }).format(cents / 100);
  };

  // Filter days based on range
  const displayDays = days.slice(0, selectedRange === '7D' ? 7 : selectedRange === '14D' ? 14 : 30);

  // Dimensions for SVG viewport
  const svgWidth = 800;
  const svgHeight = 280;
  const padding = { top: 20, right: 30, bottom: 40, left: 60 };

  const chartWidth = svgWidth - padding.left - padding.right;
  const chartHeight = svgHeight - padding.top - padding.bottom;

  // Compute domain ranges
  const allValues = displayDays.flatMap((d) => [
    d.closing_balance_cents,
    d.opening_balance_cents,
    d.receipts_cents,
    d.expenses_cents,
    safetyReserveCents,
  ]);
  const minValue = Math.min(0, ...allValues);
  const maxValue = Math.max(safetyReserveCents * 1.5, ...allValues) * 1.15;
  const valueRange = maxValue - minValue || 1;

  // Scaling helpers
  const getX = (index: number) => {
    if (displayDays.length <= 1) return padding.left + chartWidth / 2;
    return padding.left + (index / (displayDays.length - 1)) * chartWidth;
  };

  const getY = (val: number) => {
    return padding.top + chartHeight - ((val - minValue) / valueRange) * chartHeight;
  };

  // Generate smooth path for closing balance line
  const points = displayDays.map((d, i) => `${getX(i)},${getY(d.closing_balance_cents)}`);
  const linePath = points.length > 0 ? `M ${points.join(' L ')}` : '';

  // Area path under closing balance line
  const areaPath =
    points.length > 0
      ? `M ${getX(0)},${getY(0)} L ${points.join(' L ')} L ${getX(displayDays.length - 1)},${getY(0)} Z`
      : '';

  // Safety reserve threshold Y position
  const safetyReserveY = getY(safetyReserveCents);

  // Active hovered day data
  const hoveredDay = hoveredIndex !== null && displayDays[hoveredIndex] ? displayDays[hoveredIndex] : null;

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div className="chart-header-left">
          <h2 className="chart-title">Cash-Flow Trajectory</h2>
          <p className="chart-subtitle">
            Daily operating balance, inflows & outflows against safety reserve
          </p>
        </div>

        <div className="chart-controls">
          <Link
            to="/dashboard/forecast"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              fontSize: 11,
              color: '#7896B0',
              textDecoration: 'none',
              fontWeight: 600,
              padding: '4px 8px',
              borderRadius: 6,
              background: 'rgba(120, 150, 176, 0.08)',
              border: '1px solid rgba(120, 150, 176, 0.18)',
            }}
          >
            <span>Full Forecast</span>
            <ArrowRight size={12} />
          </Link>

          {(['7D', '14D', '30D'] as const).map((range) => (
            <button
              key={range}
              type="button"
              className={`chart-range-btn ${selectedRange === range ? 'active' : ''}`}
              onClick={() => setSelectedRange(range)}
            >
              {range}
            </button>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className="chart-legend">
        <div className="legend-item">
          <span className="legend-dot" style={{ background: '#7896B0' }} />
          <span>Closing Balance</span>
        </div>
        <div className="legend-item">
          <span className="legend-dot" style={{ background: '#34d399' }} />
          <span>Inflows (Receipts)</span>
        </div>
        <div className="legend-item">
          <span className="legend-dot" style={{ background: '#9A758D' }} />
          <span>Outflows (Expenses)</span>
        </div>
        <div className="legend-item">
          <span className="legend-line-dashed" />
          <span>Safety Reserve ({formatCurrency(safetyReserveCents)})</span>
        </div>
      </div>

      {/* SVG Canvas */}
      <div className="svg-chart-container" ref={containerRef}>
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="svg-chart-canvas"
          preserveAspectRatio="none"
        >
          <defs>
            {/* Gradient fill under balance line */}
            <linearGradient id="balanceAreaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#7896B0" stopOpacity="0.28" />
              <stop offset="100%" stopColor="#7896B0" stopOpacity="0.0" />
            </linearGradient>

            <linearGradient id="inflowGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#34d399" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#34d399" stopOpacity="0.3" />
            </linearGradient>

            <linearGradient id="outflowGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#9A758D" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#9A758D" stopOpacity="0.3" />
            </linearGradient>
          </defs>

          {/* Grid lines (horizontal) */}
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
                  {formatCurrency(val)}
                </text>
              </g>
            );
          })}

          {/* Safety Reserve Dashed Line */}
          <line
            x1={padding.left}
            y1={safetyReserveY}
            x2={svgWidth - padding.right}
            y2={safetyReserveY}
            stroke="#f87171"
            strokeWidth="2"
            strokeDasharray="6 4"
            opacity="0.8"
          />
          <text
            x={svgWidth - padding.right}
            y={safetyReserveY - 6}
            fill="#f87171"
            fontSize="10"
            fontWeight="bold"
            textAnchor="end"
          >
            Safety Threshold {formatCurrency(safetyReserveCents)}
          </text>

          {/* Dual Inflow / Outflow Bars per day */}
          {displayDays.map((d, i) => {
            const cx = getX(i);
            const barWidth = Math.max(6, Math.min(22, (chartWidth / displayDays.length) * 0.28));
            const baseZeroY = getY(0);

            // Inflow bar
            const inflowH = (d.receipts_cents / valueRange) * chartHeight;
            const inflowY = baseZeroY - inflowH;

            // Outflow bar
            const outflowH = (d.expenses_cents / valueRange) * chartHeight;
            const outflowY = baseZeroY - outflowH;

            return (
              <g key={`bars-${i}`}>
                {/* Inflow bar */}
                {d.receipts_cents > 0 && (
                  <rect
                    x={cx - barWidth - 1}
                    y={inflowY}
                    width={barWidth}
                    height={Math.max(2, inflowH)}
                    rx="3"
                    fill="url(#inflowGrad)"
                  />
                )}
                {/* Outflow bar */}
                {d.expenses_cents > 0 && (
                  <rect
                    x={cx + 1}
                    y={outflowY}
                    width={barWidth}
                    height={Math.max(2, outflowH)}
                    rx="3"
                    fill="url(#outflowGrad)"
                  />
                )}
              </g>
            );
          })}

          {/* Closing balance area & smooth line */}
          <path d={areaPath} fill="url(#balanceAreaGrad)" />
          <path
            d={linePath}
            fill="none"
            stroke="#7896B0"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Data point dots & hover hit targets */}
          {displayDays.map((d, i) => {
            const cx = getX(i);
            const cy = getY(d.closing_balance_cents);
            const isHovered = hoveredIndex === i;

            return (
              <g
                key={`point-${i}`}
                onMouseEnter={() => setHoveredIndex(i)}
                onMouseLeave={() => setHoveredIndex(null)}
                style={{ cursor: 'pointer' }}
              >
                {/* Invisible larger hit target */}
                <rect
                  x={cx - chartWidth / (displayDays.length * 2)}
                  y={padding.top}
                  width={chartWidth / displayDays.length}
                  height={chartHeight}
                  fill="transparent"
                />

                {/* Vertical hover crosshair line */}
                {isHovered && (
                  <line
                    x1={cx}
                    y1={padding.top}
                    x2={cx}
                    y2={padding.top + chartHeight}
                    stroke="#7896B0"
                    strokeWidth="1.5"
                    strokeDasharray="3 3"
                    opacity="0.8"
                  />
                )}

                {/* Outer circle ring on point */}
                <circle
                  cx={cx}
                  cy={cy}
                  r={isHovered ? 6 : 4}
                  fill={isHovered ? '#E7E9ED' : '#7896B0'}
                  stroke="#111925"
                  strokeWidth="2"
                  style={{ transition: 'all 0.15s ease' }}
                />

                {/* X-axis date label */}
                <text
                  x={cx}
                  y={svgHeight - 14}
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

        {/* Floating Tooltip */}
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
              <span style={{ color: '#9AA6B5' }}>Closing Balance:</span>
              <strong style={{ color: '#E7E9ED' }}>{formatCurrency(hoveredDay.closing_balance_cents)}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
              <span style={{ color: '#34d399' }}>+ Inflows:</span>
              <span>{formatCurrency(hoveredDay.receipts_cents)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
              <span style={{ color: '#9A758D' }}>- Outflows:</span>
              <span>{formatCurrency(hoveredDay.expenses_cents)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: '11px', marginTop: 2, color: hoveredDay.closing_balance_cents >= safetyReserveCents ? '#34d399' : '#f87171' }}>
              <span>Reserve Margin:</span>
              <span>{formatCurrency(hoveredDay.closing_balance_cents - safetyReserveCents)}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
