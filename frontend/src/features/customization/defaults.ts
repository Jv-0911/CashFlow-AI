import type {
  DashboardCustomizationState,
  DashboardPageId,
  PageLayout,
  WidgetId,
  WidgetLayoutItem,
} from './types.ts';
import { getWidgetsForPage, WIDGET_REGISTRY } from './widget-registry.ts';

export const LAYOUT_SCHEMA_VERSION = 1;

/**
 * Canonical ordering of widgets for each dashboard page.
 */
export const CANONICAL_PAGE_WIDGET_ORDERS: Record<DashboardPageId, readonly WidgetId[]> = {
  overview: [
    'overview-demo-disclaimer',
    'overview-kpi-summary',
    'overview-forecast-chart',
    'overview-rescue-recommendation',
    'overview-recent-activity',
  ],
  forecast: [
    'forecast-demo-disclaimer',
    'forecast-breach-alert',
    'forecast-horizon-controls',
    'forecast-metrics-summary',
    'forecast-chart',
    'forecast-table',
  ],
  rescue: [
    'rescue-backend-notice',
    'rescue-cash-risk-summary',
    'rescue-breach-explanation',
    'rescue-actions-list',
    'rescue-simulation-view',
  ],
  scenarios: [
    'scenarios-backend-notice',
    'scenarios-controls',
    'scenarios-comparison-card',
    'scenarios-chart',
    'scenarios-table',
  ],
  payments: [
    'payments-backend-notice',
    'payments-summary-cards',
    'payments-controls',
    'payments-table',
    'payments-detail-drawer',
  ],
  analytics: [
    'analytics-demo-notice',
    'analytics-kpi-cards',
    'analytics-trend-chart',
    'analytics-period-comparison',
  ],
  settings: [
    'settings-business-profile',
    'settings-policy-governance',
    'settings-display-preferences',
  ],
};

/**
 * Creates a pristine default PageLayout for a specific dashboard page.
 */
export function createDefaultPageLayout(pageId: DashboardPageId): PageLayout {
  const orderedIds = CANONICAL_PAGE_WIDGET_ORDERS[pageId] || [];
  const widgetsForPage = getWidgetsForPage(pageId);

  // Index widgets based on canonical order first, then any extra registered ones
  const orderedList: WidgetId[] = [...orderedIds];
  for (const w of widgetsForPage) {
    if (!orderedList.includes(w.id)) {
      orderedList.push(w.id);
    }
  }

  const widgetItems: WidgetLayoutItem[] = [];
  for (let i = 0; i < orderedList.length; i++) {
    const widgetId = orderedList[i];
    const def = WIDGET_REGISTRY[widgetId];
    if (def) {
      widgetItems.push({
        widgetId,
        order: widgetItems.length,
        size: def.defaultSize,
        visible: true,
        accentColor: def.defaultColor,
      });
    }
  }

  return {
    pageId,
    version: LAYOUT_SCHEMA_VERSION,
    updatedAt: new Date().toISOString(),
    widgets: widgetItems,
  };
}

/**
 * Creates the complete default customization state spanning all 7 supported pages.
 */
export function createDefaultCustomizationState(): DashboardCustomizationState {
  const now = new Date().toISOString();
  return {
    version: LAYOUT_SCHEMA_VERSION,
    updatedAt: now,
    layouts: {
      overview: createDefaultPageLayout('overview'),
      forecast: createDefaultPageLayout('forecast'),
      rescue: createDefaultPageLayout('rescue'),
      scenarios: createDefaultPageLayout('scenarios'),
      payments: createDefaultPageLayout('payments'),
      analytics: createDefaultPageLayout('analytics'),
      settings: createDefaultPageLayout('settings'),
    },
  };
}

export const DEFAULT_PAGE_LAYOUTS: Readonly<Record<DashboardPageId, PageLayout>> =
  Object.freeze({
    overview: createDefaultPageLayout('overview'),
    forecast: createDefaultPageLayout('forecast'),
    rescue: createDefaultPageLayout('rescue'),
    scenarios: createDefaultPageLayout('scenarios'),
    payments: createDefaultPageLayout('payments'),
    analytics: createDefaultPageLayout('analytics'),
    settings: createDefaultPageLayout('settings'),
  });
