import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Sparkles,
  RefreshCw,
  AlertTriangle,
  ArrowLeft,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  DndContext,
  closestCenter,
  type DragEndEvent,
} from '@dnd-kit/core';
import { SortableContext, rectSortingStrategy } from '@dnd-kit/sortable';
import { getForecast } from '../../api/forecast';
import { getRescue } from '../../api/rescue';
import type { ForecastResponse, RescueResponse, ForecastDay } from '../../types';
import { rankRescueActions } from './ranking';
import { runRecoverySimulation } from './simulation';
import { CashRiskSummary } from './CashRiskSummary';
import { BreachExplanationCard } from './BreachExplanationCard';
import { RescueActionsList } from './RescueActionsList';
import { SimulatedRecoveryView } from './SimulatedRecoveryView';
import { EmptyRescueState } from './EmptyRescueState';
import {
  useEditLayout,
  useCustomizationSensors,
  EditToolbar,
  WidgetWrapper,
  AddWidgetDrawer,
  type RescueWidgetId,
} from '../customization';
import '../../styles/rescue.css';
import '../../styles/customization.css';

export const RescuePage: React.FC = () => {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [rescue, setRescue] = useState<RescueResponse | null>(null);
  const [selectedActionIds, setSelectedActionIds] = useState<string[]>([]);
  const [retrying, setRetrying] = useState<boolean>(false);

  // Milestone 10.3 Customization
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
  } = useEditLayout('rescue');

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

      const [forecastRes, rescueRes] = await Promise.all([
        getForecast(),
        getRescue(),
      ]);

      setForecast(forecastRes.data);
      setRescue(rescueRes.data);

      const ranked = rankRescueActions(rescueRes.data.recommended_actions || []);
      if (ranked.length > 0) {
        setSelectedActionIds([ranked[0].action_id]);
      } else {
        setSelectedActionIds([]);
      }
    } catch (err) {
      console.error('Failed to load rescue suite data:', err);
      setError(err instanceof Error ? err.message : 'Unknown error loading rescue data');
    } finally {
      setLoading(false);
      setRetrying(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    Promise.all([getForecast(), getRescue()])
      .then(([forecastRes, rescueRes]) => {
        if (active) {
          setForecast(forecastRes.data);
          setRescue(rescueRes.data);
          const ranked = rankRescueActions(rescueRes.data.recommended_actions || []);
          if (ranked.length > 0) {
            setSelectedActionIds([ranked[0].action_id]);
          } else {
            setSelectedActionIds([]);
          }
          setLoading(false);
        }
      })
      .catch((err) => {
        if (active) {
          setError(err instanceof Error ? err.message : 'Unknown error loading rescue data');
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

  // Deterministically ranked actions
  const rankedActions = useMemo(() => {
    if (!rescue || !rescue.recommended_actions) return [];
    return rankRescueActions(rescue.recommended_actions);
  }, [rescue]);

  // Selected action objects
  const selectedActions = useMemo(() => {
    return rankedActions.filter((a) => selectedActionIds.includes(a.action_id));
  }, [rankedActions, selectedActionIds]);

  // Forecast metrics
  const safetyReserveCents = forecast?.safety_reserve_cents ?? 100000;
  const currency = forecast?.currency || 'USD';
  const days: ForecastDay[] = useMemo(() => forecast?.days || [], [forecast]);
  const earliestBreachDate = forecast?.first_reserve_breach_date || null;

  // Identify lowest balance and breach day
  const { lowestBalanceCents, breachDay } = useMemo(() => {
    if (days.length === 0) return { lowestBalanceCents: 0, breachDay: undefined };
    let lowest = days[0].closing_balance_cents;
    let bDay: ForecastDay | undefined = undefined;

    for (const d of days) {
      if (d.closing_balance_cents < lowest) {
        lowest = d.closing_balance_cents;
      }
      if (!bDay && d.closing_balance_cents < safetyReserveCents) {
        bDay = d;
      }
    }
    return { lowestBalanceCents: lowest, breachDay: bDay };
  }, [days, safetyReserveCents]);

  const projectedShortfallCents = Math.max(0, safetyReserveCents - lowestBalanceCents);

  // Run timing-based simulation
  const simulation = useMemo(() => {
    return runRecoverySimulation(
      days,
      safetyReserveCents,
      selectedActions,
      earliestBreachDate
    );
  }, [days, safetyReserveCents, selectedActions, earliestBreachDate]);

  // Toggle single action selection
  const handleToggleAction = (actionId: string) => {
    setSelectedActionIds((prev) =>
      prev.includes(actionId) ? prev.filter((id) => id !== actionId) : [...prev, actionId]
    );
  };

  // Select all actions
  const handleSelectAll = () => {
    setSelectedActionIds(rankedActions.map((a) => a.action_id));
  };

  // Clear all selections
  const handleClearAll = () => {
    setSelectedActionIds([]);
  };

  // Reset simulation
  const handleResetSimulation = () => {
    setSelectedActionIds([]);
  };

  // Loading skeleton
  if (loading && !retrying) {
    return (
      <div className="rescue-page-container">
        <div className="rescue-loading-skeleton">
          <div className="skeleton-bar title-bar" />
          <div className="skeleton-box hero-card" />
          <div className="skeleton-box action-card" />
          <div className="skeleton-box action-card" />
        </div>
      </div>
    );
  }

  // Error state
  if (error && !forecast && !rescue) {
    return (
      <div className="rescue-page-container">
        <div className="rescue-error-card">
          <AlertTriangle size={32} className="text-danger" />
          <h3>Unable to Load AI Rescue Suite</h3>
          <p>{error}</p>
          <button type="button" className="empty-primary-btn" onClick={handleRetry}>
            <RefreshCw size={14} className={retrying ? 'spin' : ''} />
            <span>Retry Connection</span>
          </button>
        </div>
      </div>
    );
  }

  const isDemo = !!rescue?.is_demo || !!forecast?.is_demo;
  const isBackendUnavailable = !!rescue?.backend_unavailable;

  const renderWidgetContent = (widgetId: RescueWidgetId) => {
    switch (widgetId) {
      case 'rescue-backend-notice':
        return isBackendUnavailable ? (
          <div className="backend-unavailable-notice" data-testid="backend-unavailable-banner" style={{ margin: 0 }}>
            <div className="notice-left">
              <AlertTriangle size={18} className="text-warning flex-shrink-0" />
              <div>
                <span className="notice-title">
                  Backend Service Notice: <code>/api/v1/rescue</code> is Currently Unreachable
                </span>
                <p className="notice-desc">
                  Displaying contract-grounded demo recommendations conforming strictly to{' '}
                  <code>contracts/rescue-response.example.json</code>. No synthetic transactions or hallucinated dates are injected.
                </p>
              </div>
            </div>
            <button
              type="button"
              className="notice-retry-btn"
              onClick={handleRetry}
              disabled={retrying}
            >
              <RefreshCw size={12} className={retrying ? 'spin' : ''} />
              <span>{retrying ? 'Retrying...' : 'Retry Endpoint'}</span>
            </button>
          </div>
        ) : null;

      case 'rescue-cash-risk-summary':
        return (
          <CashRiskSummary
            safetyReserveCents={safetyReserveCents}
            projectedShortfallCents={projectedShortfallCents}
            earliestBreachDate={earliestBreachDate}
            riskLevel={rescue?.risk_level || (projectedShortfallCents > 0 ? 'high' : 'low')}
            currency={currency}
            isDemo={isDemo}
            lowestProjectedBalanceCents={lowestBalanceCents}
          />
        );

      case 'rescue-breach-explanation':
        return (
          <BreachExplanationCard
            summary={
              rescue?.summary ||
              (projectedShortfallCents > 0
                ? 'Projected closing cash drops below the configured safety reserve.'
                : 'Projected closing cash maintains the configured liquidity buffer.')
            }
            breachDate={earliestBreachDate}
            breachDay={breachDay}
            safetyReserveCents={safetyReserveCents}
            evidenceIds={rescue?.evidence_ids || []}
            currency={currency}
          />
        );

      case 'rescue-actions-list':
        return rankedActions.length > 0 ? (
          <RescueActionsList
            actions={rankedActions}
            currency={currency}
            selectedActionIds={selectedActionIds}
            onToggleAction={handleToggleAction}
            onSelectAll={handleSelectAll}
            onClearAll={handleClearAll}
          />
        ) : (
          <EmptyRescueState
            safetyReserveCents={safetyReserveCents}
            currency={currency}
          />
        );

      case 'rescue-simulation-view':
        return rankedActions.length > 0 ? (
          <SimulatedRecoveryView
            simulation={simulation}
            currency={currency}
            onResetSimulation={handleResetSimulation}
          />
        ) : null;

      default:
        return null;
    }
  };

  const visibleWidgets = activeLayout.widgets.filter((w) => w.visible);

  return (
    <div className="rescue-page-container">
      {/* Top Breadcrumb & Action Bar */}
      <div className="rescue-top-bar" style={{ marginBottom: isEditing ? 8 : 16 }}>
        <div className="top-bar-left">
          <Link to="/dashboard/forecast" className="back-nav-btn">
            <ArrowLeft size={14} />
            <span>Forecast Horizon</span>
          </Link>
          <div className="title-with-badge">
            <Sparkles size={20} className="text-accent" />
            <h1 className="rescue-page-title">AI Rescue Suite</h1>
            <span className="milestone-badge">Milestone 6</span>
          </div>
        </div>

        <div className="top-bar-right">
          {!isEditing && (
            <EditToolbar
              isEditing={false}
              pageName="AI Rescue"
              hasUnsavedChanges={false}
              onStartEditing={startEditing}
              onCancelEditing={cancelEditing}
              onSaveEditing={saveEditing}
              onOpenAddWidget={() => setDrawerOpen(true)}
              onResetDefaults={resetDraftToDefaults}
            />
          )}

          <button
            type="button"
            className="refresh-btn"
            onClick={handleRetry}
            disabled={retrying}
            title="Reload live data and test API connection"
          >
            <RefreshCw size={13} className={retrying ? 'spin' : ''} />
            <span>{retrying ? 'Connecting...' : 'Refresh Engine'}</span>
          </button>
        </div>
      </div>

      {/* Edit Mode Sticky Banner */}
      {isEditing && (
        <EditToolbar
          isEditing={true}
          pageName="AI Rescue"
          hasUnsavedChanges={hasUnsavedChanges}
          onStartEditing={startEditing}
          onCancelEditing={cancelEditing}
          onSaveEditing={saveEditing}
          onOpenAddWidget={() => setDrawerOpen(true)}
          onResetDefaults={resetDraftToDefaults}
        />
      )}

      {/* Dynamic Customizable Widget Grid */}
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext
          items={visibleWidgets.map((w) => w.widgetId)}
          strategy={rectSortingStrategy}
        >
          <div className="customization-dashboard-grid">
            {visibleWidgets.map((item) => {
              const content = renderWidgetContent(item.widgetId as RescueWidgetId);
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

      {/* Add Widget Drawer */}
      <AddWidgetDrawer
        isOpen={drawerOpen}
        pageId="rescue"
        pageName="AI Rescue"
        currentLayout={activeLayout}
        onAddWidget={addWidget}
        onClose={() => setDrawerOpen(false)}
      />
    </div>
  );
};
