import { useState, useRef } from 'react';
import type { CalculatedScenarioDay } from './scenario-math';
import { formatCents } from '../../utils/currency';

interface ScenarioChartProps {
  days: CalculatedScenarioDay[];
  safetyReserveCents: number;
  currency: string;
}

export function ScenarioChart({ days, safetyReserveCents, currency }: ScenarioChartProps) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const svgWidth = 840;
  const svgHeight = 320;
  const padding = { top: 25, right: 35, bottom: 45, left: 75 };

  const chartWidth = svgWidth - padding.left - padding.right;
  const chartHeight = svgHeight - padding.top - padding.bottom;

  if (days.length === 0) {
    return (
      <div className="chart-card" style={{ textAlign: 'center', padding: '40px 20px' }}>
        <p style={{ color: '#9AA6B5', fontSize: 13 }}>No daily projections available to graph.</p>
      </div>
    );
  }

  // Calculate domain values
  const allValues = days.flatMap((d) => [
    d.baseline_closing_cents,
    d.scenario_closing_cents,
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
  const baselinePoints = days.map((d, i) => `${getX(i)},${getY(d.baseline_closing_cents)}`);
  const baselinePath = `M ${baselinePoints.join(' L ')}`;

  const scenarioPoints = days.map((d, i) => `${getX(i)},${getY(d.scenario_closing_cents)}`);
  const scenarioPath = `M ${scenarioPoints.join(' L ')}`;

  const scenarioAreaPath = `M ${getX(0)},${getY(0)} L ${scenarioPoints.join(' L ')} L ${getX(
    days.length - 1
  )},${getY(0)} Z`;

  const safetyY = getY(safetyReserveCents);
  const hoveredDay = hoveredIndex !== null && days[hoveredIndex] ? days[hoveredIndex] : null;

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div className="chart-header-left">
          <h2 className="chart-title">Comparative Trajectory Analysis</h2>
          <p className="chart-subtitle">
            Side-by-side progression: Baseline Forecast vs. Simulated What-If Model
          </p>
        </div>

        {/* Legend */}
        <div className="chart-legend" style={{ marginBottom: 0 }}>
          <div className="legend-item">
            <span
              style={{
                width: 14,
                height: 2,
                borderTop: '2px dashed #7896B0',
                display: 'inline-block',
              }}
            />
            <span>Baseline Closing</span>
          </div>
          <div className="legend-item">
            <span className="legend-dot" style={{ background: '#38bdf8' }} />
            <span>Scenario Model</span>
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
          aria-label="Comparative cash flow scenario trajectory chart"
        >
          <defs>
            <linearGradient id="scenarioAreaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.18" />
              <stop offset="100%" stopColor="#38bdf8" stopOpacity="0.0" />
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
            Safety Target: {formatCents(safetyReserveCents, currency)}
          </text>

          {/* Scenario Area Under Curve */}
          <path d={scenarioAreaPath} fill="url(#scenarioAreaGrad)" />

          {/* Baseline Closing Curve (Slate dashed) */}
          <path
            d={baselinePath}
            fill="none"
            stroke="#7896B0"
            strokeWidth="2"
            strokeDasharray="5 4"
            opacity="0.75"
          />

          {/* Scenario Closing Curve (Cyan solid primary) */}
          <path
            d={scenarioPath}
            fill="none"
            stroke="#38bdf8"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Data point markers and hover interactions */}
          {days.map((d, i) => {
            const cx = getX(i);
            const cyScenario = getY(d.scenario_closing_cents);
            const cyBase = getY(d.baseline_closing_cents);
            const isHovered = hoveredIndex === i;
            const isUnderReserve = d.scenario_closing_cents < safetyReserveCents;

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
                    stroke="#38bdf8"
                    strokeWidth="1.5"
                    strokeDasharray="3 3"
                    opacity="0.85"
                  />
                )}

                {/* Baseline dot */}
                <circle
                  cx={cx}
                  cy={cyBase}
                  r={isHovered ? 4 : 3}
                  fill="#7896B0"
                  opacity="0.7"
                />

                {/* Scenario dot */}
                <circle
                  cx={cx}
                  cy={cyScenario}
                  r={isHovered ? 6 : 4}
                  fill={isUnderReserve ? '#f87171' : isHovered ? '#ffffff' : '#38bdf8'}
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
              top: `${(getY(hoveredDay.scenario_closing_cents) / svgHeight) * 100}%`,
            }}
          >
            <div style={{ fontWeight: 700, borderBottom: '1px solid rgba(120, 150, 176, 0.2)', paddingBottom: 4 }}>
              {hoveredDay.date}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
              <span style={{ color: '#7896B0' }}>Baseline Balance:</span>
              <strong style={{ color: '#7896B0' }}>
                {formatCents(hoveredDay.baseline_closing_cents, currency)}
              </strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
              <span style={{ color: '#38bdf8' }}>Scenario Balance:</span>
              <strong
                style={{
                  color:
                    hoveredDay.scenario_closing_cents < safetyReserveCents ? '#f87171' : '#38bdf8',
                }}
              >
                {formatCents(hoveredDay.scenario_closing_cents, currency)}
              </strong>
            </div>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                gap: 12,
                borderTop: '1px solid rgba(120, 150, 176, 0.15)',
                paddingTop: 4,
              }}
            >
              <span style={{ color: '#E7E9ED' }}>Variance (Delta):</span>
              <strong
                style={{
                  color: hoveredDay.variance_cents >= 0 ? '#34d399' : '#f87171',
                }}
              >
                {hoveredDay.variance_cents >= 0 ? '+' : ''}
                {formatCents(hoveredDay.variance_cents, currency)}
              </strong>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
