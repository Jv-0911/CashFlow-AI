import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  Clock,
  RefreshCw,
  Shield,
  Sparkles,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import { getForecast } from '../../api';
import type { ForecastResponse } from '../../types';
import { formatCents } from '../../utils/currency';
import { ForecastChart } from './ForecastChart';
import { ForecastTable } from './ForecastTable';
import '../../styles/forecast.css';

export function ForecastPage() {
  const [data, setData] = useState<ForecastResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [horizonDays, setHorizonDays] = useState<7 | 14 | 30>(30);

  const fetchForecastData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getForecast();
      setData(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to connect to forecast service.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    getForecast()
      .then((res) => {
        if (active) {
          setData(res.data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (active) {
          setError(err instanceof Error ? err.message : 'Unable to connect to forecast service.');
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  // Filter days based on horizon selection
  const rawDays = data?.days || [];
  const days = rawDays.slice(0, horizonDays);
  const currency = data?.currency || 'USD';
  const safetyReserveCents = data?.safety_reserve_cents || 100000;

  // Exact integer financial calculations (Zero floating-point arithmetic)
  const endingBalanceCents = days.length > 0 ? days[days.length - 1].closing_balance_cents : 0;
  const totalReceiptsCents = days.reduce((acc, d) => acc + d.receipts_cents, 0);
  const totalExpensesCents = days.reduce((acc, d) => acc + d.expenses_cents, 0);
  const minBalanceCents = days.length > 0 ? Math.min(...days.map((d) => d.closing_balance_cents)) : 0;
  const netProjectionCents = totalReceiptsCents - totalExpensesCents;

  // Check for breach within the selected horizon
  const breachDay = days.find((d) => d.closing_balance_cents < safetyReserveCents);
  const isBreached = Boolean(data?.first_reserve_breach_date || breachDay);
  const breachDate = data?.first_reserve_breach_date || breachDay?.date || null;
  const shortfallCents = isBreached && minBalanceCents < safetyReserveCents
    ? safetyReserveCents - minBalanceCents
    : 0;

  // Loading skeleton state
  if (loading) {
    return (
      <div className="dashboard-content">
        <div className="kpi-cards-grid">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="kpi-card" style={{ height: 130 }}>
              <div className="skeleton-box" style={{ width: '40%', height: 16 }} />
              <div className="skeleton-box" style={{ width: '70%', height: 28 }} />
              <div className="skeleton-box" style={{ width: '50%', height: 14 }} />
            </div>
          ))}
        </div>
        <div className="chart-card" style={{ height: 350 }}>
          <div className="skeleton-box" style={{ width: '30%', height: 24 }} />
          <div className="skeleton-box" style={{ width: '100%', height: 260 }} />
        </div>
      </div>
    );
  }

  // Error state
  if (error || !data) {
    return (
      <div className="dashboard-content">
        <div className="dashboard-error-state">
          <AlertTriangle size={36} color="#f87171" />
          <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0, color: '#E7E9ED' }}>
            Forecast Service Connection Error
          </h2>
          <p style={{ fontSize: 13, color: '#9AA6B5', margin: 0, maxWidth: 460 }}>
            {error || 'Unable to retrieve forecast data from the backend engine endpoint.'}
          </p>
          <button type="button" className="error-retry-btn" onClick={fetchForecastData}>
            <RefreshCw size={14} style={{ display: 'inline', marginRight: 6 }} />
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  // Empty state
  if (rawDays.length === 0) {
    return (
      <div className="dashboard-content">
        <div className="dashboard-error-state" style={{ borderColor: 'rgba(120, 150, 176, 0.2)' }}>
          <Clock size={36} color="#7896B0" />
          <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0, color: '#E7E9ED' }}>
            No Forecast Projections Available
          </h2>
          <p style={{ fontSize: 13, color: '#9AA6B5', margin: 0, maxWidth: 460 }}>
            The financial engine returned zero projection days for this business account.
          </p>
          <button type="button" className="rescue-action-btn" onClick={fetchForecastData} style={{ maxWidth: 200 }}>
            <RefreshCw size={14} />
            <span>Check Again</span>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-content">
      {/* Header with Horizon Controls */}
      <div className="forecast-header-row">
        <div className="forecast-title-group">
          <h1 className="forecast-main-title">Cash-Flow Forecast</h1>
          <p className="forecast-subtitle">
            Deterministic liquidity projections, daily receipts, expenses, and safety buffer runway
          </p>
        </div>

        {/* Horizon Controls */}
        <div className="horizon-toggle-group" role="group" aria-label="Forecast horizon selection">
          {([7, 14, 30] as const).map((h) => (
            <button
              key={h}
              type="button"
              className={`horizon-btn ${horizonDays === h ? 'active' : ''}`}
              onClick={() => setHorizonDays(h)}
              aria-pressed={horizonDays === h}
            >
              {h} Days
            </button>
          ))}
        </div>
      </div>

      {/* Demo Transparency Disclaimer */}
      {data.is_demo && (
        <div className="overview-demo-banner" role="status">
          <div className="demo-banner-text">
            <Sparkles size={16} color="#7896B0" style={{ flexShrink: 0 }} />
            <div>
              <strong>Demo Forecast Projections:</strong> Displaying contract-compliant fixture data from FastAPI{' '}
              <code>/api/v1/forecast</code>. Deterministic calculations by Member 1 in{' '}
              <code>backend/app/forecast/</code> are pending integration.
            </div>
          </div>
          <span className="demo-banner-tag">Contract Fixture</span>
        </div>
      )}

      {/* Reserve Breach Alert Banner */}
      {isBreached ? (
        <div className="breach-alert-card warning" role="alert">
          <div className="breach-alert-left">
            <div className="breach-icon-pill">
              <AlertTriangle size={20} />
            </div>
            <div className="breach-alert-text">
              <span className="breach-alert-title">
                Safety Reserve Breach Projected on {breachDate || 'Forecast Horizon'}
              </span>
              <span className="breach-alert-desc">
                Projected closing balance reaches a minimum of{' '}
                <strong>{formatCents(minBalanceCents, currency)}</strong>, creating a shortfall of{' '}
                <strong>{formatCents(shortfallCents, currency)}</strong> below the configured{' '}
                <strong>{formatCents(safetyReserveCents, currency)}</strong> reserve threshold.
              </span>
            </div>
          </div>

          <Link to="/dashboard/rescue" className="breach-rescue-btn">
            <span>Simulate Recovery in AI Rescue</span>
            <ArrowRight size={14} />
          </Link>
        </div>
      ) : (
        <div className="breach-alert-card safe">
          <div className="breach-alert-left">
            <div className="breach-icon-pill">
              <CheckCircle2 size={20} />
            </div>
            <div className="breach-alert-text">
              <span className="breach-alert-title">Safety Buffer Fully Maintained</span>
              <span className="breach-alert-desc">
                No reserve breach detected across the selected {horizonDays}-day horizon. Minimum projected balance is{' '}
                <strong>{formatCents(minBalanceCents, currency)}</strong> (
                <strong>{formatCents(minBalanceCents - safetyReserveCents, currency)}</strong> above safety reserve).
              </span>
            </div>
          </div>

          <span className="demo-banner-tag" style={{ background: 'rgba(52, 211, 153, 0.2)', color: '#34d399' }}>
            Safe Runway
          </span>
        </div>
      )}

      {/* Summary KPI Metrics (AdminCN style) */}
      <div className="kpi-cards-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
        {/* Metric 1: Ending Balance */}
        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Ending Balance ({horizonDays}d)</span>
            <span className={`kpi-pill ${endingBalanceCents >= safetyReserveCents ? 'positive' : 'warning'}`}>
              <ArrowUpRight size={12} />
              <span>Projected</span>
            </span>
          </div>
          <div className="kpi-value-row">
            <div>
              <div className="kpi-value">{formatCents(endingBalanceCents, currency)}</div>
              <div className="kpi-subtext">Liquidity on day {days.length}</div>
            </div>
          </div>
        </div>

        {/* Metric 2: Total Receipts */}
        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Total Receipts</span>
            <span className="kpi-pill positive">
              <TrendingUp size={12} />
              <span>Inflow</span>
            </span>
          </div>
          <div className="kpi-value-row">
            <div>
              <div className="kpi-value" style={{ color: '#34d399' }}>
                +{formatCents(totalReceiptsCents, currency)}
              </div>
              <div className="kpi-subtext">Sum of all incoming receipts</div>
            </div>
          </div>
        </div>

        {/* Metric 3: Total Expenses */}
        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Total Expenses</span>
            <span className="kpi-pill neutral">
              <TrendingDown size={12} />
              <span>Outflow</span>
            </span>
          </div>
          <div className="kpi-value-row">
            <div>
              <div className="kpi-value" style={{ color: '#9A758D' }}>
                -{formatCents(totalExpensesCents, currency)}
              </div>
              <div className="kpi-subtext">Committed disbursements & AP</div>
            </div>
          </div>
        </div>

        {/* Metric 4: Minimum Projected Balance */}
        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Minimum Balance</span>
            <span className={`kpi-pill ${minBalanceCents >= safetyReserveCents ? 'positive' : 'warning'}`}>
              <Shield size={12} />
              <span>{minBalanceCents >= safetyReserveCents ? 'Above Buffer' : 'Dip Risk'}</span>
            </span>
          </div>
          <div className="kpi-value-row">
            <div>
              <div className="kpi-value">{formatCents(minBalanceCents, currency)}</div>
              <div className="kpi-subtext">
                Net horizon flow: {netProjectionCents >= 0 ? '+' : ''}{formatCents(netProjectionCents, currency)}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Primary Forecast Chart */}
      <ForecastChart
        days={days}
        safetyReserveCents={safetyReserveCents}
        currency={currency}
      />

      {/* Detailed Daily Breakdown Table */}
      <ForecastTable
        days={days}
        safetyReserveCents={safetyReserveCents}
        currency={currency}
      />
    </div>
  );
}
