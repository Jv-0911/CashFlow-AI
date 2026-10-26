import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  GitBranch,
  RefreshCw,
  AlertTriangle,
  ArrowLeft,
  Sparkles,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { getForecast } from '../../api/forecast';
import { simulateScenario } from '../../api/scenario';
import type { ForecastResponse } from '../../types/forecast';
import type { ScenarioModifiers, ScenarioResponse } from '../../types/scenario';
import { ScenarioControls } from './ScenarioControls';
import { ScenarioComparisonCard } from './ScenarioComparisonCard';
import { ScenarioChart } from './ScenarioChart';
import { ScenarioTable } from './ScenarioTable';
import type { CalculatedScenarioDay } from './scenario-math';
import '../../styles/scenario.css';

const DEFAULT_MODIFIERS: ScenarioModifiers = {
  preset_id: 'delayed_receivables',
  delayed_receivables_days: 14,
  receipts_modifier_pct: 0,
  expenses_modifier_pct: 0,
  lump_sum_expense_cents: 0,
};

export const ScenarioPage: React.FC = () => {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [baselineForecast, setBaselineForecast] = useState<ForecastResponse | null>(null);
  const [scenarioData, setScenarioData] = useState<ScenarioResponse | null>(null);
  const [modifiers, setModifiers] = useState<ScenarioModifiers>(DEFAULT_MODIFIERS);
  const [safetyReserveCents, setSafetyReserveCents] = useState<number>(100000);
  const [retrying, setRetrying] = useState<boolean>(false);

  // Load baseline forecast
  const loadBaseline = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await getForecast();
      if (!res.data || !res.data.days || res.data.days.length === 0) {
        throw new Error('Baseline forecast data contains no daily records to simulate.');
      }
      setBaselineForecast(res.data);
      setSafetyReserveCents(res.data.safety_reserve_cents);

      // Trigger initial simulation
      const simRes = await simulateScenario(
        {
          business_id: 'demo_shop_001',
          forecast_days: res.data.days.length,
          safety_reserve_cents: res.data.safety_reserve_cents,
          evidence_ids: ['txn_demo_001'],
          currency: res.data.currency,
        },
        DEFAULT_MODIFIERS,
        res.data
      );
      setScenarioData(simRes.data);
    } catch (err) {
      console.error('Failed to load baseline forecast for scenario simulation:', err);
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to connect to forecast service. Baseline forecast is required to model scenarios.'
      );
    } finally {
      setLoading(false);
      setRetrying(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    getForecast()
      .then(async (res) => {
        if (!active) return;
        if (!res.data || !res.data.days || res.data.days.length === 0) {
          throw new Error('Baseline forecast data contains no daily records to simulate.');
        }
        setBaselineForecast(res.data);
        setSafetyReserveCents(res.data.safety_reserve_cents);

        const simRes = await simulateScenario(
          {
            business_id: 'demo_shop_001',
            forecast_days: res.data.days.length,
            safety_reserve_cents: res.data.safety_reserve_cents,
            evidence_ids: ['txn_demo_001'],
            currency: res.data.currency,
          },
          DEFAULT_MODIFIERS,
          res.data
        );
        if (active) {
          setScenarioData(simRes.data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (active) {
          setError(
            err instanceof Error
              ? err.message
              : 'Unable to connect to forecast service. Baseline forecast is required to model scenarios.'
          );
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  // Recalculate simulation whenever modifiers or safetyReserveCents change
  const runSimulation = useCallback(
    async (newModifiers: ScenarioModifiers, newReserveCents: number) => {
      if (!baselineForecast) return;
      try {
        const simRes = await simulateScenario(
          {
            business_id: 'demo_shop_001',
            forecast_days: baselineForecast.days.length,
            safety_reserve_cents: newReserveCents,
            evidence_ids: ['txn_demo_001'],
            currency: baselineForecast.currency,
          },
          newModifiers,
          baselineForecast
        );
        setScenarioData(simRes.data);
      } catch (err) {
        console.error('Scenario simulation computation error:', err);
      }
    },
    [baselineForecast]
  );

  const handleModifierChange = (newModifiers: ScenarioModifiers) => {
    setModifiers(newModifiers);
    runSimulation(newModifiers, safetyReserveCents);
  };

  const handleSafetyReserveChange = (newCents: number) => {
    setSafetyReserveCents(newCents);
    runSimulation(modifiers, newCents);
  };

  const handleResetToBaseline = () => {
    const cleanModifiers: ScenarioModifiers = {
      preset_id: 'custom',
      delayed_receivables_days: 0,
      receipts_modifier_pct: 0,
      expenses_modifier_pct: 0,
      lump_sum_expense_cents: 0,
      recurring_payroll_cents: 0,
    };

    setModifiers(cleanModifiers);
    if (baselineForecast) {
      setSafetyReserveCents(baselineForecast.safety_reserve_cents);
      runSimulation(cleanModifiers, baselineForecast.safety_reserve_cents);
    }
  };

  const handleRetryConnection = () => {
    setRetrying(true);
    loadBaseline();
  };

  // Convert scenarioData.days to CalculatedScenarioDay format
  const calculatedDays: CalculatedScenarioDay[] = useMemo(() => {
    if (!scenarioData || !baselineForecast) return [];
    return scenarioData.days.map((d, i) => {
      const baseDay = baselineForecast.days[i] || d;
      return {
        ...d,
        baseline_closing_cents: baseDay.closing_balance_cents,
        scenario_closing_cents: d.closing_balance_cents,
        variance_cents: d.closing_balance_cents - baseDay.closing_balance_cents,
        baseline_receipts_cents: baseDay.receipts_cents,
        scenario_receipts_cents: d.receipts_cents,
        baseline_expenses_cents: baseDay.expenses_cents,
        scenario_expenses_cents: d.expenses_cents,
        is_baseline_breach: baseDay.closing_balance_cents < safetyReserveCents,
        is_scenario_breach: d.closing_balance_cents < safetyReserveCents,
      };
    });
  }, [scenarioData, baselineForecast, safetyReserveCents]);

  const currency = baselineForecast?.currency || 'USD';
  const horizonDays = baselineForecast?.days.length || 30;
  const isBackendUnavailable = !!scenarioData?.backend_unavailable;

  // Uncollected delayed receipts calculation
  const uncollectedDelayedCents = useMemo(() => {
    if (!baselineForecast || modifiers.delayed_receivables_days <= 0) return 0;
    let sum = 0;
    const daysArr = baselineForecast.days;
    for (let i = 0; i < daysArr.length; i++) {
      if (i + modifiers.delayed_receivables_days >= daysArr.length) {
        sum += daysArr[i].receipts_cents;
      }
    }
    return sum;
  }, [baselineForecast, modifiers.delayed_receivables_days]);

  // Loading skeleton
  if (loading && !retrying) {
    return (
      <div className="scenario-page-container">
        <div className="scenario-loading-skeleton">
          <div className="skeleton-bar title-bar" />
          <div className="skeleton-box controls-box" />
          <div className="skeleton-box kpi-box" />
          <div className="skeleton-box chart-box" />
        </div>
      </div>
    );
  }

  // Actionable Error State if baseline forecast is missing or invalid
  if (error && !baselineForecast) {
    return (
      <div className="scenario-page-container">
        <div className="scenario-error-card">
          <AlertTriangle size={36} className="text-danger" />
          <h3>Baseline Forecast Unavailable</h3>
          <p>{error}</p>
          <div className="error-actions-group">
            <button type="button" className="empty-primary-btn" onClick={handleRetryConnection}>
              <RefreshCw size={14} className={retrying ? 'spin' : ''} />
              <span>Retry Baseline Connection</span>
            </button>
            <Link to="/dashboard/forecast" className="empty-secondary-btn">
              <span>Go to Forecast Dashboard</span>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const hasScenarioBreach = !!scenarioData?.comparison.scenario_breach_date;

  return (
    <div className="scenario-page-container">
      {/* Top Bar Navigation */}
      <div className="scenario-top-bar">
        <div className="top-bar-left">
          <Link to="/dashboard/forecast" className="back-nav-btn">
            <ArrowLeft size={14} />
            <span>Forecast Horizon</span>
          </Link>
          <div className="title-with-badge">
            <GitBranch size={20} className="text-accent" />
            <h1 className="scenario-page-title">Scenario Simulation</h1>
            <span className="milestone-badge">Milestone 7</span>
          </div>
        </div>

        <div className="top-bar-right">
          {hasScenarioBreach && (
            <Link to="/dashboard/rescue" className="rescue-cta-link">
              <Sparkles size={13} />
              <span>Breach Detected • Open AI Rescue</span>
            </Link>
          )}

          <button
            type="button"
            className="refresh-btn"
            onClick={handleRetryConnection}
            disabled={retrying}
            title="Reload baseline data and test API connection"
          >
            <RefreshCw size={13} className={retrying ? 'spin' : ''} />
            <span>{retrying ? 'Connecting...' : 'Refresh Baseline'}</span>
          </button>
        </div>
      </div>

      {/* Persistent Visible Notice when Backend Scenario API is Unavailable */}
      {isBackendUnavailable && (
        <div className="backend-unavailable-notice" data-testid="backend-unavailable-banner">
          <div className="notice-left">
            <AlertTriangle size={18} className="text-warning flex-shrink-0" />
            <div>
              <span className="notice-title">
                Backend Service Notice: <code>/api/v1/scenario</code> is Currently Unreachable
              </span>
              <p className="notice-desc">
                Simulation calculated using the isolated client fallback model (integer cents,
                exact calendar day shifts) conforming to <code>contracts/scenario-request.example.json</code>.
                Results are explicitly designated as demo projections.
              </p>
            </div>
          </div>
          <button
            type="button"
            className="notice-retry-btn"
            onClick={handleRetryConnection}
            disabled={retrying}
          >
            <RefreshCw size={12} className={retrying ? 'spin' : ''} />
            <span>{retrying ? 'Retrying...' : 'Retry Endpoint'}</span>
          </button>
        </div>
      )}

      {/* Scenario Presets & Custom Controls */}
      <ScenarioControls
        modifiers={modifiers}
        safetyReserveCents={safetyReserveCents}
        currency={currency}
        horizonDays={horizonDays}
        uncollectedDelayedCents={uncollectedDelayedCents}
        onModifierChange={handleModifierChange}
        onSafetyReserveChange={handleSafetyReserveChange}
        onReset={handleResetToBaseline}
      />

      {/* Baseline vs. Scenario Comparison Card */}
      {scenarioData && (
        <ScenarioComparisonCard
          comparison={scenarioData.comparison}
          safetyReserveCents={safetyReserveCents}
          currency={currency}
        />
      )}

      {/* Comparative Dual-Line Trajectory Chart */}
      {calculatedDays.length > 0 && (
        <ScenarioChart
          days={calculatedDays}
          safetyReserveCents={safetyReserveCents}
          currency={currency}
        />
      )}

      {/* Daily Divergence Table Breakdown */}
      {calculatedDays.length > 0 && (
        <ScenarioTable
          days={calculatedDays}
          safetyReserveCents={safetyReserveCents}
          currency={currency}
        />
      )}
    </div>
  );
};
