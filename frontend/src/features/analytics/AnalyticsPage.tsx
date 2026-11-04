import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  BarChart3,
  RefreshCw,
  AlertTriangle,
  ArrowLeft,
  Sparkles,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  DndContext,
  closestCenter,
  type DragEndEvent,
} from '@dnd-kit/core';
import { SortableContext, rectSortingStrategy } from '@dnd-kit/sortable';
import { getForecast } from '../../api/forecast';
import { getLedgerEntries } from '../../api/ledger';
import type { ForecastResponse } from '../../types/forecast';
import type { LedgerEntry } from '../../types/ledger';
import { calculateCashFlowAnalytics } from './analytics-math';
import { AnalyticsKpiCards } from './AnalyticsKpiCards';
import { CashFlowTrendChart } from './CashFlowTrendChart';
import { PeriodComparisonCard } from './PeriodComparisonCard';
import {
  useEditLayout,
  useCustomizationSensors,
  EditToolbar,
  WidgetWrapper,
  AddWidgetDrawer,
  type AnalyticsWidgetId,
} from '../customization';
import '../../styles/analytics.css';
import '../../styles/customization.css';

export const AnalyticsPage: React.FC = () => {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [forecastData, setForecastData] = useState<ForecastResponse | null>(null);
  const [ledgerEntries, setLedgerEntries] = useState<LedgerEntry[]>([]);
  const [retrying, setRetrying] = useState<boolean>(false);

  // Milestone 10.3 Edit Mode & Customization
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
  } = useEditLayout('analytics');

  const sensors = useCustomizationSensors();

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      reorderWidgets(String(active.id), String(over.id));
    }
  };

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      setForecastData(null);

      const [forecastRes, ledgerRes] = await Promise.all([
        getForecast(),
        getLedgerEntries(),
      ]);

      setForecastData(forecastRes.data);
      setLedgerEntries(ledgerRes.data?.entries || []);
    } catch (err) {
      console.error('Failed to load data for cash analytics:', err);
      setError(
        err instanceof Error ? err.message : 'Unable to load analytics data sources.'
      );
    } finally {
      setLoading(false);
      setRetrying(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    Promise.all([getForecast(), getLedgerEntries()])
      .then(([forecastRes, ledgerRes]) => {
        if (active) {
          setForecastData(forecastRes.data);
          setLedgerEntries(ledgerRes.data?.entries || []);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (active) {
          setError(
            err instanceof Error ? err.message : 'Unable to load analytics data sources.'
          );
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  const handleRetry = () => {
    setRetrying(true);
    loadData();
  };

  const days = useMemo(() => forecastData?.days || [], [forecastData]);
  const safetyReserveCents = forecastData?.safety_reserve_cents || 100000;
  const currency = forecastData?.currency || 'USD';
  const isDemo = Boolean(forecastData?.is_demo);

  const analytics = useMemo(() => {
    return calculateCashFlowAnalytics(days, safetyReserveCents, ledgerEntries);
  }, [days, safetyReserveCents, ledgerEntries]);

  // Widget content renderer
  const renderWidgetContent = (widgetId: AnalyticsWidgetId) => {
    switch (widgetId) {
      case 'analytics-demo-notice':
        return isDemo || isEditing ? (
          <div className="analytics-demo-notice" role="status" style={{ margin: 0 }}>
            <AlertTriangle size={18} className="text-warning flex-shrink-0" />
            <div>
              <span className="notice-title">Demo Projections & Sample Settlement Data</span>
              <p className="notice-desc">
                Analytics metrics are computed from demo forecast fixtures and sample PayPal Sandbox ledger entries.
                Values clearly distinguish between <strong>Forecast Projections</strong> and{' '}
                <strong>Verified Actuals</strong>. No live banking connections or ERP records are simulated.
              </p>
            </div>
          </div>
        ) : null;

      case 'analytics-kpi-cards':
        return <AnalyticsKpiCards analytics={analytics} currency={currency} />;

      case 'analytics-trend-chart':
        return (
          <CashFlowTrendChart
            days={days}
            safetyReserveCents={safetyReserveCents}
            currency={currency}
          />
        );

      case 'analytics-period-comparison':
        return <PeriodComparisonCard days={days} currency={currency} />;

      default:
        return null;
    }
  };

  // Loading Skeleton State
  if (loading && !retrying) {
    return (
      <div className="analytics-page-container">
        <div className="analytics-loading-skeleton">
          <div className="skeleton-bar title-bar" />
          <div className="skeleton-kpi-grid">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="skeleton-kpi-box" />
            ))}
          </div>
          <div className="skeleton-chart-box" />
        </div>
      </div>
    );
  }

  // Error State
  if (error && !forecastData) {
    return (
      <div className="analytics-page-container">
        <div className="analytics-error-card">
          <AlertTriangle size={36} className="text-danger" />
          <h3>Analytics Data Unavailable</h3>
          <p>{error}</p>
          <button type="button" className="empty-primary-btn" onClick={handleRetry}>
            <RefreshCw size={14} className={retrying ? 'spin' : ''} />
            <span>Retry Connection</span>
          </button>
        </div>
      </div>
    );
  }

  const visibleWidgets = activeLayout.widgets.filter((w) => w.visible);

  return (
    <div className="analytics-page-container">
      {/* Top Bar Navigation */}
      <div className="analytics-top-bar" style={{ marginBottom: isEditing ? 8 : 16 }}>
        <div className="top-bar-left">
          <Link to="/dashboard" className="back-nav-btn">
            <ArrowLeft size={14} />
            <span>Overview Dashboard</span>
          </Link>
          <div className="title-with-badge">
            <BarChart3 size={20} className="text-accent" />
            <h1 className="analytics-page-title">Cash Analytics & Performance</h1>
            <span className="milestone-badge">Milestone 9</span>
          </div>
        </div>

        <div className="top-bar-right">
          {!isEditing && (
            <EditToolbar
              isEditing={false}
              pageName="Analytics"
              hasUnsavedChanges={false}
              onStartEditing={startEditing}
              onCancelEditing={cancelEditing}
              onSaveEditing={saveEditing}
              onOpenAddWidget={() => setDrawerOpen(true)}
              onResetDefaults={resetDraftToDefaults}
            />
          )}

          <Link to="/dashboard/rescue" className="back-nav-btn">
            <Sparkles size={13} className="text-accent" />
            <span>AI Rescue Actions</span>
          </Link>

          <button
            type="button"
            className="refresh-btn"
            onClick={handleRetry}
            disabled={retrying}
            title="Reload forecast and ledger data"
          >
            <RefreshCw size={13} className={retrying ? 'spin' : ''} />
            <span>{retrying ? 'Connecting...' : 'Refresh Analytics'}</span>
          </button>
        </div>
      </div>

      {/* Edit Mode Sticky Banner */}
      {isEditing && (
        <EditToolbar
          isEditing={true}
          pageName="Analytics"
          hasUnsavedChanges={hasUnsavedChanges}
          onStartEditing={startEditing}
          onCancelEditing={cancelEditing}
          onSaveEditing={saveEditing}
          onOpenAddWidget={() => setDrawerOpen(true)}
          onResetDefaults={resetDraftToDefaults}
        />
      )}

      {/* Main Customizable Dashboard Grid */}
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={visibleWidgets.map((item) => item.widgetId)}
          strategy={rectSortingStrategy}
        >
          <div className="customization-dashboard-grid" data-editing={isEditing}>
            {visibleWidgets.map((item) => {
              const content = renderWidgetContent(item.widgetId as AnalyticsWidgetId);
              if (!content) return null;
              return (
                <WidgetWrapper
                  key={item.widgetId}
                  item={item}
                  isEditing={isEditing}
                  onChangeSize={(size) => changeWidgetSize(item.widgetId, size)}
                  onChangeColor={(color) => changeWidgetColor(item.widgetId, color)}
                  onRemove={() => removeWidget(item.widgetId)}
                >
                  {content}
                </WidgetWrapper>
              );
            })}
          </div>
        </SortableContext>
      </DndContext>

      {/* Add Widget Drawer */}
      <AddWidgetDrawer
        isOpen={drawerOpen}
        pageId="analytics"
        pageName="Analytics"
        currentLayout={activeLayout}
        onClose={() => setDrawerOpen(false)}
        onAddWidget={(id) => addWidget(id)}
      />
    </div>
  );
};

export default AnalyticsPage;
