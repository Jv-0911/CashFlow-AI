import type {
  DashboardPageId,
  WidgetDefinition,
  WidgetId,
} from './types.ts';

export interface DashboardPageMetadata {
  readonly id: DashboardPageId;
  readonly name: string;
  readonly path: string;
  readonly description: string;
}

export const DASHBOARD_PAGES: readonly DashboardPageMetadata[] = [
  {
    id: 'overview',
    name: 'Overview',
    path: '/dashboard/overview',
    description: 'Executive liquidity summary, cash position, and primary forecast chart',
  },
  {
    id: 'forecast',
    name: 'Forecast',
    path: '/dashboard/forecast',
    description: 'Deterministic liquidity projections, runway buffers, and daily ledger tables',
  },
  {
    id: 'rescue',
    name: 'AI Rescue',
    path: '/dashboard/rescue',
    description: 'Autonomous recovery actions, grounded evidence tracing, and simulation engine',
  },
  {
    id: 'scenarios',
    name: 'Scenarios',
    path: '/dashboard/scenarios',
    description: 'What-if stress testing, delayed receivables, and comparative trajectories',
  },
  {
    id: 'payments',
    name: 'Payments & Ledger',
    path: '/dashboard/payments',
    description: 'Verified settlement ledger, transaction audits, and gateway synchronization',
  },
  {
    id: 'analytics',
    name: 'Analytics',
    path: '/dashboard/analytics',
    description: 'Burn rate, runway days, forecast variance, and historical cash flow trends',
  },
  {
    id: 'settings',
    name: 'Settings',
    path: '/dashboard/settings',
    description: 'Business profile, safety reserve policy governance, and display preferences',
  },
] as const;

/**
 * Authoritative Widget Registry
 *
 * Defines all modular dashboard widgets supported across the CashFlow AI suite.
 * Each widget declares compatible pages, sizing constraints, default accent colors,
 * and mandatory safety/disclaimer constraints.
 */
export const WIDGET_REGISTRY: Record<WidgetId, WidgetDefinition> = {
  // ---------------------------------------------------------------------------
  // 1. Overview Widgets
  // ---------------------------------------------------------------------------
  'overview-demo-disclaimer': {
    id: 'overview-demo-disclaimer',
    title: 'Demo Projections Notice',
    description: 'Transparency banner indicating demo fixture projections from FastAPI /api/v1/forecast',
    category: 'disclaimer',
    compatiblePages: ['overview'],
    defaultSize: 'full',
    allowedSizes: ['full'],
    defaultColor: 'amber',
    isRequired: true,
    isSafetyCritical: true,
  },
  'overview-kpi-summary': {
    id: 'overview-kpi-summary',
    title: 'Executive Liquidity KPIs',
    description: 'Four key metrics: Cash Balance, Projected Inflows, Projected Outflows, and Safety Reserve ratio',
    category: 'kpi',
    compatiblePages: ['overview'],
    defaultSize: 'full',
    allowedSizes: ['full', 'lg'],
    defaultColor: 'blue',
    isRequired: false,
    isSafetyCritical: false,
  },
  'overview-forecast-chart': {
    id: 'overview-forecast-chart',
    title: 'Cash-Flow Forecast Chart',
    description: 'Primary visual projection chart showing closing balances against safety buffer threshold',
    category: 'chart',
    compatiblePages: ['overview'],
    defaultSize: 'lg',
    allowedSizes: ['full', 'lg', 'md'],
    defaultColor: 'blue',
    isRequired: false,
    isSafetyCritical: false,
  },
  'overview-rescue-recommendation': {
    id: 'overview-rescue-recommendation',
    title: 'AI Rescue Recommendation',
    description: 'High-priority autonomous recovery action card with quick simulation launcher',
    category: 'action',
    compatiblePages: ['overview'],
    defaultSize: 'sm',
    allowedSizes: ['full', 'lg', 'md', 'sm'],
    defaultColor: 'amber',
    isRequired: false,
    isSafetyCritical: false,
  },
  'overview-recent-activity': {
    id: 'overview-recent-activity',
    title: 'Recent Activity Feed',
    description: 'Stream of recent inflows, committed outflows, and PayPal Sandbox settlement events',
    category: 'detail',
    compatiblePages: ['overview'],
    defaultSize: 'sm',
    allowedSizes: ['full', 'lg', 'md', 'sm'],
    defaultColor: 'slate',
    isRequired: false,
    isSafetyCritical: false,
  },

  // ---------------------------------------------------------------------------
  // 2. Forecast Widgets
  // ---------------------------------------------------------------------------
  'forecast-demo-disclaimer': {
    id: 'forecast-demo-disclaimer',
    title: 'Forecast Transparency Notice',
    description: 'Notice confirming contract-compliant fixture data from /api/v1/forecast',
    category: 'disclaimer',
    compatiblePages: ['forecast'],
    defaultSize: 'full',
    allowedSizes: ['full'],
    defaultColor: 'amber',
    isRequired: true,
    isSafetyCritical: true,
  },
  'forecast-breach-alert': {
    id: 'forecast-breach-alert',
    title: 'Reserve Breach & Runway Alert',
    description: 'Critical warning banner detailing projected safety reserve breaches, dates, and shortfall amounts',
    category: 'alert',
    compatiblePages: ['forecast'],
    defaultSize: 'full',
    allowedSizes: ['full'],
    defaultColor: 'amber',
    isRequired: true,
    isSafetyCritical: true,
  },
  'forecast-horizon-controls': {
    id: 'forecast-horizon-controls',
    title: 'Horizon Controls',
    description: 'Forecast horizon toggle selector allowing switching between 7, 14, and 30 projection days',
    category: 'controls',
    compatiblePages: ['forecast'],
    defaultSize: 'full',
    allowedSizes: ['full', 'lg'],
    defaultColor: 'slate',
    isRequired: false,
    isSafetyCritical: false,
  },
  'forecast-metrics-summary': {
    id: 'forecast-metrics-summary',
    title: 'Forecast Summary Metrics',
    description: 'Summary KPI cards for ending balance, total receipts, total expenses, and minimum balance',
    category: 'kpi',
    compatiblePages: ['forecast'],
    defaultSize: 'full',
    allowedSizes: ['full', 'lg'],
    defaultColor: 'blue',
    isRequired: false,
    isSafetyCritical: false,
  },
  'forecast-chart': {
    id: 'forecast-chart',
    title: 'Cash-Flow Horizon Chart',
    description: 'Full interactive multi-day trajectory chart with safety reserve line and daily tooltips',
    category: 'chart',
    compatiblePages: ['forecast'],
    defaultSize: 'full',
    allowedSizes: ['full', 'lg'],
    defaultColor: 'blue',
    isRequired: false,
    isSafetyCritical: false,
  },
  'forecast-table': {
    id: 'forecast-table',
    title: 'Daily Breakdown Table',
    description: 'Granular tabular view of receipts, expenses, closing balances, and daily buffer deltas',
    category: 'table',
    compatiblePages: ['forecast'],
    defaultSize: 'full',
    allowedSizes: ['full', 'lg'],
    defaultColor: 'slate',
    isRequired: false,
    isSafetyCritical: false,
  },

  // ---------------------------------------------------------------------------
  // 3. AI Rescue Widgets
  // ---------------------------------------------------------------------------
  'rescue-backend-notice': {
    id: 'rescue-backend-notice',
    title: 'Rescue Engine Service Notice',
    description: 'Status notice displaying backend endpoint availability and contract compliance mode',
    category: 'disclaimer',
    compatiblePages: ['rescue'],
    defaultSize: 'full',
    allowedSizes: ['full'],
    defaultColor: 'amber',
    isRequired: true,
    isSafetyCritical: true,
  },
  'rescue-cash-risk-summary': {
    id: 'rescue-cash-risk-summary',
    title: 'Cash Risk Summary',
    description: 'Risk level assessment, projected shortfall amount, and earliest breach timing details',
    category: 'alert',
    compatiblePages: ['rescue'],
    defaultSize: 'full',
    allowedSizes: ['full', 'lg'],
    defaultColor: 'rose',
    isRequired: false,
    isSafetyCritical: true,
  },
  'rescue-breach-explanation': {
    id: 'rescue-breach-explanation',
    title: 'Breach Cause & Evidence Tracing',
    description: 'Root cause explanation grounded in verified transaction IDs and expense obligations',
    category: 'detail',
    compatiblePages: ['rescue'],
    defaultSize: 'full',
    allowedSizes: ['full', 'lg'],
    defaultColor: 'blue',
    isRequired: false,
    isSafetyCritical: false,
  },
  'rescue-actions-list': {
    id: 'rescue-actions-list',
    title: 'Ranked Rescue Actions',
    description: 'Prioritized list of deterministic rescue actions with selectable multi-action toggles',
    category: 'action',
    compatiblePages: ['rescue'],
    defaultSize: 'full',
    allowedSizes: ['full', 'lg'],
    defaultColor: 'emerald',
    isRequired: false,
    isSafetyCritical: false,
  },
  'rescue-simulation-view': {
    id: 'rescue-simulation-view',
    title: 'Recovery Simulation Engine',
    description: 'Simulation trajectory chart comparing baseline vs recovered cash curves, with required disclaimer',
    category: 'chart',
    compatiblePages: ['rescue'],
    defaultSize: 'full',
    allowedSizes: ['full', 'lg'],
    defaultColor: 'purple',
    isRequired: false,
    isSafetyCritical: true,
  },

  // ---------------------------------------------------------------------------
  // 4. Scenarios Widgets
  // ---------------------------------------------------------------------------
  'scenarios-backend-notice': {
    id: 'scenarios-backend-notice',
    title: 'Scenario Engine Service Notice',
    description: 'Notice indicating client fallback or live endpoint simulation calculations',
    category: 'disclaimer',
    compatiblePages: ['scenarios'],
    defaultSize: 'full',
    allowedSizes: ['full'],
    defaultColor: 'amber',
    isRequired: true,
    isSafetyCritical: true,
  },
  'scenarios-controls': {
    id: 'scenarios-controls',
    title: 'Scenario Modifiers & Presets',
    description: 'What-If presets (Revenue Dip, Cost Hike, Delayed Receivables) and customized modifier sliders',
    category: 'controls',
    compatiblePages: ['scenarios'],
    defaultSize: 'full',
    allowedSizes: ['full', 'lg'],
    defaultColor: 'blue',
    isRequired: false,
    isSafetyCritical: false,
  },
  'scenarios-comparison-card': {
    id: 'scenarios-comparison-card',
    title: 'Scenario Variance Comparison',
    description: 'Variance scorecard reporting ending balance delta and breach date divergence',
    category: 'kpi',
    compatiblePages: ['scenarios'],
    defaultSize: 'full',
    allowedSizes: ['full', 'lg'],
    defaultColor: 'cyan',
    isRequired: false,
    isSafetyCritical: false,
  },
  'scenarios-chart': {
    id: 'scenarios-chart',
    title: 'Comparative Trajectory Chart',
    description: 'Dual-curve chart contrasting baseline forecast against simulated scenario outcomes',
    category: 'chart',
    compatiblePages: ['scenarios'],
    defaultSize: 'full',
    allowedSizes: ['full', 'lg'],
    defaultColor: 'blue',
    isRequired: false,
    isSafetyCritical: false,
  },
  'scenarios-table': {
    id: 'scenarios-table',
    title: 'Scenario Divergence Table',
    description: 'Day-by-day tabular comparison of baseline and scenario closing balances and net variances',
    category: 'table',
    compatiblePages: ['scenarios'],
    defaultSize: 'full',
    allowedSizes: ['full', 'lg'],
    defaultColor: 'slate',
    isRequired: false,
    isSafetyCritical: false,
  },

  // ---------------------------------------------------------------------------
  // 5. Payments & Ledger Widgets
  // ---------------------------------------------------------------------------
  'payments-backend-notice': {
    id: 'payments-backend-notice',
    title: 'Gateway & Ledger Notice',
    description: 'Notice detailing live PayPal Sandbox synchronization and synthetic recovery record status',
    category: 'disclaimer',
    compatiblePages: ['payments'],
    defaultSize: 'full',
    allowedSizes: ['full'],
    defaultColor: 'amber',
    isRequired: true,
    isSafetyCritical: true,
  },
  'payments-summary-cards': {
    id: 'payments-summary-cards',
    title: 'Settlement & Verification KPIs',
    description: 'Real-time metrics: Total Settled, Pending Verification, Simulated Recovery, and Settlement Rate',
    category: 'kpi',
    compatiblePages: ['payments'],
    defaultSize: 'full',
    allowedSizes: ['full', 'lg'],
    defaultColor: 'emerald',
    isRequired: false,
    isSafetyCritical: false,
  },
  'payments-controls': {
    id: 'payments-controls',
    title: 'Ledger Filter & Search Controls',
    description: 'Status filter tabs (All, Verified, Pending, Failed, Reversed) and search input',
    category: 'controls',
    compatiblePages: ['payments'],
    defaultSize: 'full',
    allowedSizes: ['full', 'lg'],
    defaultColor: 'slate',
    isRequired: false,
    isSafetyCritical: false,
  },
  'payments-table': {
    id: 'payments-table',
    title: 'Verified Transaction Ledger',
    description: 'Audit-ready transaction records with authoritative verification timestamps and status badges',
    category: 'table',
    compatiblePages: ['payments'],
    defaultSize: 'full',
    allowedSizes: ['full', 'lg'],
    defaultColor: 'blue',
    isRequired: false,
    isSafetyCritical: true,
  },
  'payments-detail-drawer': {
    id: 'payments-detail-drawer',
    title: 'Payment Detail & Audit Drawer',
    description: 'Slideover drawer showing granular transaction receipts, net fee breakdown, and webhook trace',
    category: 'detail',
    compatiblePages: ['payments'],
    defaultSize: 'md',
    allowedSizes: ['full', 'lg', 'md'],
    defaultColor: 'purple',
    isRequired: false,
    isSafetyCritical: false,
  },

  // ---------------------------------------------------------------------------
  // 6. Analytics Widgets
  // ---------------------------------------------------------------------------
  'analytics-demo-notice': {
    id: 'analytics-demo-notice',
    title: 'Analytics Provenance Notice',
    description: 'Notice separating Forecast Projections from Verified Actual settlement statistics',
    category: 'disclaimer',
    compatiblePages: ['analytics'],
    defaultSize: 'full',
    allowedSizes: ['full'],
    defaultColor: 'amber',
    isRequired: true,
    isSafetyCritical: true,
  },
  'analytics-kpi-cards': {
    id: 'analytics-kpi-cards',
    title: 'Performance Analytics KPIs',
    description: 'Key metrics: Daily Burn Rate, Cash Runway Days, Forecast Variance, and Recovery Efficiency',
    category: 'kpi',
    compatiblePages: ['analytics'],
    defaultSize: 'full',
    allowedSizes: ['full', 'lg'],
    defaultColor: 'blue',
    isRequired: false,
    isSafetyCritical: false,
  },
  'analytics-trend-chart': {
    id: 'analytics-trend-chart',
    title: 'Cash Flow Trend Chart',
    description: 'Dual-axis trend chart plotting daily net flow bars and closing liquidity line',
    category: 'chart',
    compatiblePages: ['analytics'],
    defaultSize: 'full',
    allowedSizes: ['full', 'lg'],
    defaultColor: 'cyan',
    isRequired: false,
    isSafetyCritical: false,
  },
  'analytics-period-comparison': {
    id: 'analytics-period-comparison',
    title: 'Period-Over-Period Comparison',
    description: 'Comparative breakdown of inflows, outflows, and net cash trajectory across two halves of horizon',
    category: 'detail',
    compatiblePages: ['analytics'],
    defaultSize: 'full',
    allowedSizes: ['full', 'lg'],
    defaultColor: 'purple',
    isRequired: false,
    isSafetyCritical: false,
  },

  // ---------------------------------------------------------------------------
  // 7. Settings Widgets
  // ---------------------------------------------------------------------------
  'settings-business-profile': {
    id: 'settings-business-profile',
    title: 'Business Profile Information',
    description: 'Legal entity name, executive owner, and business contact email configuration',
    category: 'settings',
    compatiblePages: ['settings'],
    defaultSize: 'full',
    allowedSizes: ['full', 'lg'],
    defaultColor: 'blue',
    isRequired: false,
    isSafetyCritical: false,
  },
  'settings-policy-governance': {
    id: 'settings-policy-governance',
    title: 'Safety Reserve Governance Policy',
    description: 'Configured minimum liquidity safety buffer and proactive breach alert horizon days',
    category: 'settings',
    compatiblePages: ['settings'],
    defaultSize: 'full',
    allowedSizes: ['full', 'lg'],
    defaultColor: 'amber',
    isRequired: false,
    isSafetyCritical: true,
  },
  'settings-display-preferences': {
    id: 'settings-display-preferences',
    title: 'Currency & Display Preferences',
    description: 'Operating currency selection (USD, EUR, GBP, CAD) and dark/light color mode',
    category: 'settings',
    compatiblePages: ['settings'],
    defaultSize: 'full',
    allowedSizes: ['full', 'lg'],
    defaultColor: 'slate',
    isRequired: false,
    isSafetyCritical: false,
  },
};

export const ALL_WIDGET_IDS: readonly WidgetId[] = Object.keys(WIDGET_REGISTRY) as WidgetId[];

export function getAllWidgets(): readonly WidgetDefinition[] {
  return Object.values(WIDGET_REGISTRY);
}

export function getWidget(id: WidgetId): WidgetDefinition | undefined {
  return WIDGET_REGISTRY[id];
}

export function getWidgetsForPage(pageId: DashboardPageId): WidgetDefinition[] {
  return getAllWidgets().filter((widget) => widget.compatiblePages.includes(pageId));
}

export function isWidgetCompatible(widgetId: WidgetId, pageId: DashboardPageId): boolean {
  const widget = WIDGET_REGISTRY[widgetId];
  return Boolean(widget && widget.compatiblePages.includes(pageId));
}

export function isWidgetRequired(widgetId: WidgetId): boolean {
  return Boolean(WIDGET_REGISTRY[widgetId]?.isRequired);
}

export function isWidgetSafetyCritical(widgetId: WidgetId): boolean {
  return Boolean(WIDGET_REGISTRY[widgetId]?.isSafetyCritical);
}
