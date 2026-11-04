/**
 * CashFlow AI — Milestone 10.1: Customization Foundation Types
 *
 * Strict type definitions for widget registries, page layout configurations,
 * color palettes, and persistence models.
 *
 * Financial data and calculation engines are strictly decoupled from these
 * layout presentation types.
 */

export type DashboardPageId =
  | 'overview'
  | 'forecast'
  | 'rescue'
  | 'scenarios'
  | 'payments'
  | 'analytics'
  | 'settings';

export type WidgetSize = 'sm' | 'md' | 'lg' | 'full';

export type WidgetCategory =
  | 'disclaimer'
  | 'alert'
  | 'kpi'
  | 'chart'
  | 'table'
  | 'controls'
  | 'action'
  | 'detail'
  | 'settings';

export type MutedColorId =
  | 'blue'
  | 'cyan'
  | 'pink'
  | 'purple'
  | 'emerald'
  | 'amber'
  | 'rose'
  | 'slate';

export interface MutedColorToken {
  readonly id: MutedColorId;
  readonly name: string;
  readonly cssVariable: string;
  readonly value: string; // hex
  readonly borderClass: string;
  readonly textClass: string;
  readonly bgSubtle: string;
}

export type OverviewWidgetId =
  | 'overview-demo-disclaimer'
  | 'overview-kpi-summary'
  | 'overview-forecast-chart'
  | 'overview-rescue-recommendation'
  | 'overview-recent-activity';

export type ForecastWidgetId =
  | 'forecast-demo-disclaimer'
  | 'forecast-breach-alert'
  | 'forecast-horizon-controls'
  | 'forecast-metrics-summary'
  | 'forecast-chart'
  | 'forecast-table';

export type RescueWidgetId =
  | 'rescue-backend-notice'
  | 'rescue-cash-risk-summary'
  | 'rescue-breach-explanation'
  | 'rescue-actions-list'
  | 'rescue-simulation-view';

export type ScenariosWidgetId =
  | 'scenarios-backend-notice'
  | 'scenarios-controls'
  | 'scenarios-comparison-card'
  | 'scenarios-chart'
  | 'scenarios-table';

export type PaymentsWidgetId =
  | 'payments-backend-notice'
  | 'payments-summary-cards'
  | 'payments-controls'
  | 'payments-table'
  | 'payments-detail-drawer';

export type AnalyticsWidgetId =
  | 'analytics-demo-notice'
  | 'analytics-kpi-cards'
  | 'analytics-trend-chart'
  | 'analytics-period-comparison';

export type SettingsWidgetId =
  | 'settings-business-profile'
  | 'settings-policy-governance'
  | 'settings-display-preferences';

export type WidgetId =
  | OverviewWidgetId
  | ForecastWidgetId
  | RescueWidgetId
  | ScenariosWidgetId
  | PaymentsWidgetId
  | AnalyticsWidgetId
  | SettingsWidgetId;

export interface WidgetDefinition {
  readonly id: WidgetId;
  readonly title: string;
  readonly description: string;
  readonly category: WidgetCategory;
  readonly compatiblePages: readonly DashboardPageId[];
  readonly defaultSize: WidgetSize;
  readonly allowedSizes: readonly WidgetSize[];
  readonly defaultColor: MutedColorId;
  /**
   * If true, this widget is mandatory and cannot be hidden or removed
   * from the page (e.g. regulatory disclaimers, demo notices, breach warnings).
   */
  readonly isRequired: boolean;
  /**
   * Flags critical notices, safety buffer alerts, or payment verification proofs.
   */
  readonly isSafetyCritical: boolean;
}

export interface WidgetLayoutItem {
  widgetId: WidgetId;
  order: number;
  size: WidgetSize;
  visible: boolean;
  accentColor?: MutedColorId;
}

export interface PageLayout {
  pageId: DashboardPageId;
  version: number;
  updatedAt: string;
  widgets: WidgetLayoutItem[];
}

export interface DashboardCustomizationState {
  version: number;
  updatedAt: string;
  layouts: Record<DashboardPageId, PageLayout>;
}

export interface CustomizationValidationResult<T> {
  valid: boolean;
  data: T;
  errors: string[];
}
