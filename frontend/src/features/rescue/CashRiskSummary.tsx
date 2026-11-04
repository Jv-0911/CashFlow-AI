import React from 'react';
import { AlertTriangle, CheckCircle2, Shield, Calendar, TrendingDown } from 'lucide-react';
import { formatCents } from '../../utils/currency';

interface CashRiskSummaryProps {
  safetyReserveCents: number;
  projectedShortfallCents: number;
  earliestBreachDate: string | null;
  riskLevel: 'high' | 'medium' | 'low' | 'unknown';
  currency: string;
  isDemo: boolean;
  lowestProjectedBalanceCents: number;
}

export const CashRiskSummary: React.FC<CashRiskSummaryProps> = ({
  safetyReserveCents,
  projectedShortfallCents,
  earliestBreachDate,
  riskLevel,
  currency,
  isDemo,
  lowestProjectedBalanceCents,
}) => {
  const hasBreach = projectedShortfallCents > 0 || !!earliestBreachDate;

  return (
    <div className="rescue-risk-summary-card">
      <div className="risk-summary-header">
        <div className="risk-summary-title-row">
          <div className="risk-title-wrapper">
            <div className={`risk-status-icon-pill ${hasBreach ? 'danger' : 'safe'}`}>
              {hasBreach ? <AlertTriangle size={20} /> : <CheckCircle2 size={20} />}
            </div>
            <div>
              <h2 className="risk-summary-heading">
                {hasBreach
                  ? 'Projected Safety Reserve Breach Detected'
                  : 'Safety Reserve Adequately Maintained'}
              </h2>
              <p className="risk-summary-subtext">
                {hasBreach
                  ? 'Deterministic forecast model projects closing balance to drop below configured liquidity buffer.'
                  : 'Forecasted daily liquidity remains above minimum safety reserve threshold throughout horizon.'}
              </p>
            </div>
          </div>

          <div className="risk-badges-cluster">
            {isDemo && (
              <span className="rescue-badge demo" title="Conforming to contracts/rescue-response.example.json">
                Demo Business Data
              </span>
            )}
            <span
              className={`rescue-badge risk-${riskLevel}`}
              title={`Risk assessment: ${riskLevel.toUpperCase()}`}
            >
              {riskLevel.toUpperCase()} RISK
            </span>
            <span className="rescue-badge analytical" title="Derived strictly from forecast facts">
              Projected Model
            </span>
          </div>
        </div>
      </div>

      <div className="risk-kpi-grid">
        {/* KPI 1: Configured Safety Reserve */}
        <div className="risk-kpi-item">
          <div className="risk-kpi-label">
            <Shield size={14} />
            <span>Configured Safety Reserve</span>
          </div>
          <div className="risk-kpi-value">{formatCents(safetyReserveCents, currency)}</div>
          <div className="risk-kpi-note">Minimum policy liquidity buffer</div>
        </div>

        {/* KPI 2: Projected Shortfall */}
        <div className="risk-kpi-item">
          <div className="risk-kpi-label">
            <TrendingDown size={14} />
            <span>Projected Shortfall</span>
          </div>
          <div className={`risk-kpi-value ${projectedShortfallCents > 0 ? 'text-danger' : 'text-safe'}`}>
            {projectedShortfallCents > 0
              ? `-${formatCents(projectedShortfallCents, currency)}`
              : formatCents(0, currency)}
          </div>
          <div className="risk-kpi-note">
            {projectedShortfallCents > 0
              ? `Dip below required ${formatCents(safetyReserveCents, currency)} buffer`
              : 'Zero reserve deficit projected'}
          </div>
        </div>

        {/* KPI 3: Earliest Breach Date */}
        <div className="risk-kpi-item">
          <div className="risk-kpi-label">
            <Calendar size={14} />
            <span>Earliest Projected Breach</span>
          </div>
          <div className="risk-kpi-value date-value">
            {earliestBreachDate ? earliestBreachDate : 'None Projected'}
          </div>
          <div className="risk-kpi-note">
            {earliestBreachDate
              ? 'First calendar day closing balance dips'
              : 'Reserves remain solvent through entire horizon'}
          </div>
        </div>

        {/* KPI 4: Lowest Projected Balance */}
        <div className="risk-kpi-item">
          <div className="risk-kpi-label">
            <Shield size={14} />
            <span>Lowest Projected Balance</span>
          </div>
          <div className={`risk-kpi-value ${lowestProjectedBalanceCents < safetyReserveCents ? 'text-warning' : 'text-safe'}`}>
            {formatCents(lowestProjectedBalanceCents, currency)}
          </div>
          <div className="risk-kpi-note">Horizon minimum projected cash floor</div>
        </div>
      </div>
    </div>
  );
};
