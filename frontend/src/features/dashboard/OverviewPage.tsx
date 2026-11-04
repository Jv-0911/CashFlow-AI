import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowUpRight,
  ArrowDownRight,
  CheckCircle2,
  Clock,
  RefreshCw,
  Shield,
  Sparkles,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import {
  DndContext,
  closestCenter,
  type DragEndEvent,
} from '@dnd-kit/core';
import { SortableContext, rectSortingStrategy } from '@dnd-kit/sortable';
import { getForecast } from '../../api';
import type { ForecastResponse } from '../../types';
import { CashFlowChart } from './widgets/CashFlowChart';
import {
  useEditLayout,
  useCustomizationSensors,
  EditToolbar,
  WidgetWrapper,
  AddWidgetDrawer,
  type OverviewWidgetId,
} from '../customization';
import '../../styles/customization.css';

export function OverviewPage() {
  const [data, setData] = useState<ForecastResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Milestone 10.2 Edit Mode and Widget Controls Hook
  const {
    isEditing,
    activeLayout,
    drawerOpen,
    setDrawerOpen,
    hasUnsavedChanges,
    startEditing,
    cancelEditing,
    saveEditing,
    reorderWidgets,
    changeWidgetSize,
    changeWidgetColor,
    removeWidget,
    addWidget,
    resetDraftToDefaults,
  } = useEditLayout('overview');

  const sensors = useCustomizationSensors();

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      reorderWidgets(String(active.id), String(over.id));
    }
  };

  const fetchOverview = useCallback(async () => {
    setLoading(true);
    setError(null);
      setData(null);
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

  // Format currency helpers
  const formatCurrency = (cents: number, curr = 'USD') => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: curr,
      maximumFractionDigits: 0,
    }).format(cents / 100);
  };

  // Calculations from data
  const currency = data?.currency || 'USD';
  const days = data?.days || [];
  const safetyReserveCents = data?.safety_reserve_cents || 100000;

  const currentBalanceCents = days.length > 0 ? days[days.length - 1].closing_balance_cents : 400000;
  const totalInflowsCents = days.reduce((sum, d) => sum + d.receipts_cents, 0);
  const totalOutflowsCents = days.reduce((sum, d) => sum + d.expenses_cents, 0);
  const netFlowCents = totalInflowsCents - totalOutflowsCents;

  const breachDate = data?.first_reserve_breach_date || null;
  const isBreached = breachDate !== null || currentBalanceCents < safetyReserveCents;
  const reserveRatio = Math.round((currentBalanceCents / safetyReserveCents) * 100);

  // Loading skeleton state
  if (loading) {
    return (
      <div className="dashboard-content">
        <div className="kpi-cards-grid">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="kpi-card" style={{ height: 140 }}>
              <div className="skeleton-box" style={{ width: '50%', height: 16 }} />
              <div className="skeleton-box" style={{ width: '80%', height: 32 }} />
              <div className="skeleton-box" style={{ width: '60%', height: 14 }} />
            </div>
          ))}
        </div>
        <div className="chart-card" style={{ height: 380 }}>
          <div className="skeleton-box" style={{ width: '30%', height: 24 }} />
          <div className="skeleton-box" style={{ width: '100%', height: 280 }} />
        </div>
      </div>
    );
  }

  // Error state
  if (error || !data) {
    return (
      <div className="dashboard-content">
        <div className="dashboard-error-state">
          <AlertTriangle size={32} color="#f87171" />
          <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0, color: '#E7E9ED' }}>
            Failed to Load Forecast Data
          </h2>
          <p style={{ fontSize: 13, color: '#9AA6B5', margin: 0, maxWidth: 400 }}>
            {error || 'Unable to retrieve forecast projections from the backend service.'}
          </p>
          <button type="button" className="error-retry-btn" onClick={fetchOverview}>
            <RefreshCw size={14} style={{ display: 'inline', marginRight: 6 }} />
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  // Render individual widget contents
  const renderWidgetContent = (widgetId: OverviewWidgetId) => {
    switch (widgetId) {
      case 'overview-demo-disclaimer':
        return data.is_demo ? (
          <div className="overview-demo-banner" role="status" style={{ margin: 0 }}>
            <div className="demo-banner-text">
              <Sparkles size={16} color="#7896B0" />
              <div>
                <strong>Demo Projections Active:</strong> Connected to FastAPI{' '}
                <code>/api/v1/forecast</code>. Projections are calculated by the integrated financial engine using fictional business data.
              </div>
            </div>
            <span className="demo-banner-tag">Demo Business Data</span>
          </div>
        ) : null;

      case 'overview-kpi-summary':
        return (
          <div className="kpi-cards-grid" style={{ margin: 0 }}>
            {/* KPI 1: Cash Balance */}
            <div className="kpi-card">
              <div className="kpi-header">
                <span className="kpi-title">Cash Balance</span>
                <span className="kpi-pill positive">
                  <ArrowUpRight size={12} />
                  <span>+12.6%</span>
                </span>
              </div>
              <div className="kpi-value-row">
                <div>
                  <div className="kpi-value">{formatCurrency(currentBalanceCents, currency)}</div>
                  <div className="kpi-subtext">
                    Net flow {netFlowCents >= 0 ? '+' : ''}{formatCurrency(netFlowCents, currency)} • Operating liquidity
                  </div>
                </div>
                <div className="kpi-mini-bars" aria-hidden="true">
                  <span className="kpi-bar" style={{ height: '40%' }} />
                  <span className="kpi-bar" style={{ height: '60%' }} />
                  <span className="kpi-bar" style={{ height: '50%' }} />
                  <span className="kpi-bar active" style={{ height: '85%' }} />
                  <span className="kpi-bar active" style={{ height: '75%' }} />
                </div>
              </div>
            </div>

            {/* KPI 2: Projected Inflows */}
            <div className="kpi-card">
              <div className="kpi-header">
                <span className="kpi-title">Projected Inflows</span>
                <span className="kpi-pill positive">
                  <TrendingUp size={12} />
                  <span>+25.2%</span>
                </span>
              </div>
              <div className="kpi-value-row">
                <div>
                  <div className="kpi-value">{formatCurrency(totalInflowsCents, currency)}</div>
                  <div className="kpi-subtext">Customer payments & receipts</div>
                </div>
                <div className="kpi-mini-bars" aria-hidden="true">
                  <span className="kpi-bar green" style={{ height: '30%' }} />
                  <span className="kpi-bar green" style={{ height: '80%' }} />
                  <span className="kpi-bar green" style={{ height: '20%' }} />
                  <span className="kpi-bar green" style={{ height: '90%' }} />
                  <span className="kpi-bar green" style={{ height: '50%' }} />
                </div>
              </div>
            </div>

            {/* KPI 3: Projected Outflows */}
            <div className="kpi-card">
              <div className="kpi-header">
                <span className="kpi-title">Projected Outflows</span>
                <span className="kpi-pill neutral">
                  <TrendingDown size={12} />
                  <span>-12.2%</span>
                </span>
              </div>
              <div className="kpi-value-row">
                <div>
                  <div className="kpi-value">{formatCurrency(totalOutflowsCents, currency)}</div>
                  <div className="kpi-subtext">Payroll & vendor obligations</div>
                </div>
                <div className="kpi-mini-bars" aria-hidden="true">
                  <span className="kpi-bar mauve" style={{ height: '60%' }} />
                  <span className="kpi-bar mauve" style={{ height: '45%' }} />
                  <span className="kpi-bar mauve" style={{ height: '85%' }} />
                  <span className="kpi-bar mauve" style={{ height: '30%' }} />
                  <span className="kpi-bar mauve" style={{ height: '55%' }} />
                </div>
              </div>
            </div>

            {/* KPI 4: Safety Reserve & Breach Status */}
            <div className="kpi-card">
              <div className="kpi-header">
                <span className="kpi-title">Safety Reserve</span>
                <span className={`kpi-pill ${isBreached ? 'warning' : 'positive'}`}>
                  <Shield size={12} />
                  <span>{isBreached ? 'Breach Risk' : 'Safe Runway'}</span>
                </span>
              </div>
              <div className="kpi-value-row">
                <div>
                  <div className="kpi-value">{formatCurrency(safetyReserveCents, currency)}</div>
                  <div className="kpi-subtext">
                    {breachDate ? `Breach on ${breachDate}` : `${reserveRatio}% coverage ratio`}
                  </div>
                </div>
                <div style={{ position: 'relative', width: 44, height: 44 }} aria-hidden="true">
                  <svg width="44" height="44" viewBox="0 0 44 44">
                    <circle
                      cx="22"
                      cy="22"
                      r="18"
                      fill="none"
                      stroke="rgba(120, 150, 176, 0.15)"
                      strokeWidth="4"
                    />
                    <circle
                      cx="22"
                      cy="22"
                      r="18"
                      fill="none"
                      stroke={isBreached ? '#fbbf24' : '#34d399'}
                      strokeWidth="4"
                      strokeDasharray="113"
                      strokeDashoffset={113 - (113 * Math.min(100, reserveRatio)) / 100}
                      strokeLinecap="round"
                      transform="rotate(-90 22 22)"
                    />
                  </svg>
                  <div
                    style={{
                      position: 'absolute',
                      inset: 0,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: 10,
                      fontWeight: 700,
                      color: '#E7E9ED',
                    }}
                  >
                    {Math.min(999, reserveRatio)}%
                  </div>
                </div>
              </div>
            </div>
          </div>
        );

      case 'overview-forecast-chart':
        return (
          <CashFlowChart
            days={days}
            safetyReserveCents={safetyReserveCents}
            currency={currency}
          />
        );

      case 'overview-rescue-recommendation':
        return (
          <div className="side-widget-card" style={{ height: '100%', margin: 0 }}>
            <div className="side-widget-header">
              <div className="side-widget-title">
                <Sparkles size={16} color="#7896B0" />
                <span>AI Rescue Recommendation</span>
              </div>
              <span className="kpi-pill warning" style={{ fontSize: 10 }}>
                High Priority
              </span>
            </div>

            <div className="rescue-card-body">
              <div className="rescue-impact-badge">
                <ArrowUpRight size={13} />
                <span>Explore evidence-based recommendations</span>
              </div>
              <div className="rescue-action-title">
                Accelerate Overdue Invoices via PayPal Sandbox
              </div>
              <div className="rescue-action-desc">
                Projected cash dip on Oct 14 can be averted without high-cost financing by triggering
                automated customer reminders for invoice #INV-2041.
              </div>
            </div>

            <Link
              to="/dashboard/rescue"
              className="rescue-action-btn"
              style={{ textDecoration: 'none' }}
            >
              <span>Simulate Recovery Action</span>
              <ArrowUpRight size={13} />
            </Link>

            <div style={{ fontSize: 10, color: '#9AA6B5', textAlign: 'center', marginTop: 8 }}>
              Simulation only • No real funds or notifications dispatched
            </div>
          </div>
        );

      case 'overview-recent-activity':
        return (
          <div className="side-widget-card" style={{ height: '100%', margin: 0 }}>
            <div className="side-widget-header">
              <div className="side-widget-title">
                <Clock size={16} color="#7896B0" />
                <span>Illustrative Activity (not ledger records)</span>
              </div>
              <Link to="/dashboard/payments" style={{ fontSize: 11, color: '#7896B0', textDecoration: 'none' }}>
                View Ledger
              </Link>
            </div>

            <div className="activity-list">
              <div className="activity-item">
                <div className="activity-item-left">
                  <div className="activity-icon-pill inflow">
                    <ArrowDownRight size={14} />
                  </div>
                  <div className="activity-details">
                    <span className="activity-name">Customer Retainer #INV-2041</span>
                    <span className="activity-date">Oct 11 • Projected Inflow</span>
                  </div>
                </div>
                <span className="activity-amount positive">+$1,500</span>
              </div>

              <div className="activity-item">
                <div className="activity-item-left">
                  <div className="activity-icon-pill outflow">
                    <ArrowUpRight size={14} />
                  </div>
                  <div className="activity-details">
                    <span className="activity-name">AWS Cloud Infrastructure</span>
                    <span className="activity-date">Oct 11 • Committed Expense</span>
                  </div>
                </div>
                <span className="activity-amount negative">-$500</span>
              </div>

              <div className="activity-item">
                <div className="activity-item-left">
                  <div className="activity-icon-pill outflow">
                    <ArrowUpRight size={14} />
                  </div>
                  <div className="activity-details">
                    <span className="activity-name">Bi-Weekly Team Payroll</span>
                    <span className="activity-date">Oct 12 • Scheduled Outflow</span>
                  </div>
                </div>
                <span className="activity-amount negative">-$2,000</span>
              </div>

              <div className="activity-item">
                <div className="activity-item-left">
                  <div className="activity-icon-pill inflow">
                    <CheckCircle2 size={14} />
                  </div>
                  <div className="activity-details">
                    <span className="activity-name">Illustrative receipt example</span>
                    <span className="activity-date">Oct 13 • Simulated Transfer</span>
                  </div>
                </div>
                <span className="activity-amount positive">+$500</span>
              </div>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  const visibleWidgets = activeLayout.widgets.filter((w) => w.visible);

  return (
    <div className="dashboard-content">
      {/* Overview Header Row */}
      <div
        className="overview-header-row"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: isEditing ? 8 : 16,
        }}
      >
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
            Overview
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: '2px 0 0 0' }}>
            Live liquidity, deterministic runway, and autonomous rescue recommendations
          </p>
        </div>

        {!isEditing && (
          <EditToolbar
            isEditing={false}
            pageName="Overview"
            hasUnsavedChanges={false}
            onStartEditing={startEditing}
            onCancelEditing={cancelEditing}
            onSaveEditing={saveEditing}
            onOpenAddWidget={() => setDrawerOpen(true)}
            onResetDefaults={resetDraftToDefaults}
          />
        )}
      </div>

      {/* Edit Mode Sticky Banner */}
      {isEditing && (
        <EditToolbar
          isEditing={true}
          pageName="Overview"
          hasUnsavedChanges={hasUnsavedChanges}
          onStartEditing={startEditing}
          onCancelEditing={cancelEditing}
          onSaveEditing={saveEditing}
          onOpenAddWidget={() => setDrawerOpen(true)}
          onResetDefaults={resetDraftToDefaults}
        />
      )}

      {/* Dynamic Modular Widget Grid */}
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext
          items={visibleWidgets.map((w) => w.widgetId)}
          strategy={rectSortingStrategy}
        >
          <div className="customization-dashboard-grid">
            {visibleWidgets.map((item) => {
              const content = renderWidgetContent(item.widgetId as OverviewWidgetId);
              if (!content) return null;

              return (
                <WidgetWrapper
                  key={item.widgetId}
                  item={item}
                  isEditing={isEditing}
                  onChangeSize={(sz) => changeWidgetSize(item.widgetId, sz)}
                  onChangeColor={(clr) => changeWidgetColor(item.widgetId, clr)}
                  onRemove={() => removeWidget(item.widgetId)}
                >
                  {content}
                </WidgetWrapper>
              );
            })}
          </div>
        </SortableContext>
      </DndContext>

      {/* Add Widget Drawer Library */}
      <AddWidgetDrawer
        isOpen={drawerOpen}
        pageId="overview"
        pageName="Overview"
        currentLayout={activeLayout}
        onAddWidget={addWidget}
        onClose={() => setDrawerOpen(false)}
      />
    </div>
  );
}
