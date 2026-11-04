import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import {
  CURATED_PALETTE,
  PALETTE_COLOR_IDS,
  getMutedColorToken,
  isValidMutedColor,
} from '../palette.ts';
import {
  WIDGET_REGISTRY,
  ALL_WIDGET_IDS,
  getAllWidgets,
  getWidget,
  getWidgetsForPage,
  isWidgetCompatible,
  isWidgetRequired,
  isWidgetSafetyCritical,
  DASHBOARD_PAGES,
} from '../widget-registry.ts';
import {
  createDefaultPageLayout,
  createDefaultCustomizationState,
  LAYOUT_SCHEMA_VERSION,
  CANONICAL_PAGE_WIDGET_ORDERS,
} from '../defaults.ts';
import {
  CUSTOMIZATION_STORAGE_KEY,
  SUPPORTED_PAGES,
  validateWidgetLayoutItem,
  validatePageLayout,
  validateCustomizationState,
  loadCustomizationState,
  loadPageLayout,
  savePageLayout,
  saveAllCustomizationState,
  resetPageLayout,
  resetAllCustomizationState,
} from '../storage.ts';
import type { DashboardPageId, PageLayout } from '../types.ts';

// Ensure in-memory localStorage mock for Node test runner
if (typeof globalThis.localStorage === 'undefined') {
  let store: Record<string, string> = {};
  globalThis.localStorage = {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = String(value);
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
    key: (index: number) => Object.keys(store)[index] || null,
    get length() {
      return Object.keys(store).length;
    },
  } as unknown as Storage;
}

describe('Customization Foundation — Milestone 10.1 Suite', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  // =========================================================================
  // 1. Curated Palette
  // =========================================================================
  describe('Curated Color Palette', () => {
    it('defines all 8 muted palette tokens matching CashFlow AI CSS variables', () => {
      const expectedTokens = [
        'blue',
        'cyan',
        'pink',
        'purple',
        'emerald',
        'amber',
        'rose',
        'slate',
      ];

      for (const token of expectedTokens) {
        assert.ok(token in CURATED_PALETTE, `Missing palette token: ${token}`);
        const info = CURATED_PALETTE[token as keyof typeof CURATED_PALETTE];
        assert.strictEqual(info.id, token);
        assert.ok(info.value.startsWith('#'), `Token ${token} value must be a valid hex color`);
        assert.ok(info.cssVariable.length > 0, `Token ${token} must specify a CSS variable`);
        assert.ok(info.bgSubtle.startsWith('rgba'), `Token ${token} must specify subtle RGBA background`);
      }

      assert.strictEqual(PALETTE_COLOR_IDS.length, 8);
    });

    it('identifies valid and invalid muted color keys', () => {
      assert.strictEqual(isValidMutedColor('blue'), true);
      assert.strictEqual(isValidMutedColor('emerald'), true);
      assert.strictEqual(isValidMutedColor('neon_green'), false);
      assert.strictEqual(isValidMutedColor(null), false);
      assert.strictEqual(isValidMutedColor(123), false);
    });

    it('retrieves color tokens with safe fallback on unknown keys', () => {
      const blueToken = getMutedColorToken('blue');
      assert.strictEqual(blueToken.id, 'blue');

      // @ts-expect-error - testing invalid runtime input fallback
      const fallback = getMutedColorToken('non_existent');
      assert.strictEqual(fallback.id, 'blue');
    });
  });

  // =========================================================================
  // 2. Widget Registry
  // =========================================================================
  describe('Widget Registry & Metadata Integrity', () => {
    it('contains registered widgets for all 7 dashboard pages', () => {
      assert.ok(ALL_WIDGET_IDS.length >= 25, `Expected at least 25 registered widgets, found ${ALL_WIDGET_IDS.length}`);
      const allWidgets = getAllWidgets();
      assert.strictEqual(allWidgets.length, ALL_WIDGET_IDS.length);

      for (const page of DASHBOARD_PAGES) {
        const pageWidgets = getWidgetsForPage(page.id);
        assert.ok(
          pageWidgets.length >= 3,
          `Page "${page.id}" must have at least 3 registered widgets (found ${pageWidgets.length})`
        );
      }
    });

    it('ensures each widget has valid default sizes, allowed sizes, and default colors', () => {
      assert.strictEqual(getWidget('overview-forecast-chart')?.category, 'chart');
      // @ts-expect-error - checking runtime undefined fallback
      assert.strictEqual(getWidget('invalid_id'), undefined);

      for (const widget of getAllWidgets()) {
        assert.ok(widget.id.length > 0, 'Widget must have non-empty ID');
        assert.ok(widget.title.length > 0, `Widget ${widget.id} must have title`);
        assert.ok(widget.description.length > 0, `Widget ${widget.id} must have description`);
        assert.ok(widget.compatiblePages.length > 0, `Widget ${widget.id} must specify compatible pages`);
        assert.ok(
          widget.allowedSizes.includes(widget.defaultSize),
          `Widget ${widget.id} defaultSize must be in allowedSizes`
        );
        assert.ok(
          isValidMutedColor(widget.defaultColor),
          `Widget ${widget.id} defaultColor must be in curated palette`
        );
      }
    });

    it('flags required regulatory disclaimers, breach alerts, and notices as non-hideable', () => {
      const requiredWidgetIds = [
        'overview-demo-disclaimer',
        'forecast-demo-disclaimer',
        'forecast-breach-alert',
        'rescue-backend-notice',
        'scenarios-backend-notice',
        'payments-backend-notice',
        'analytics-demo-notice',
      ];

      for (const id of requiredWidgetIds) {
        // @ts-expect-error - checked at runtime
        assert.strictEqual(isWidgetRequired(id), true, `Widget ${id} must be marked isRequired: true`);
        // @ts-expect-error - checked at runtime
        assert.strictEqual(isWidgetSafetyCritical(id), true, `Widget ${id} must be marked isSafetyCritical: true`);
      }
    });

    it('correctly reports page compatibility for cross-page isolation', () => {
      assert.strictEqual(isWidgetCompatible('overview-forecast-chart', 'overview'), true);
      assert.strictEqual(isWidgetCompatible('overview-forecast-chart', 'analytics'), false);
      assert.strictEqual(isWidgetCompatible('forecast-table', 'forecast'), true);
      assert.strictEqual(isWidgetCompatible('forecast-table', 'settings'), false);
    });
  });

  // =========================================================================
  // 3. Default Layouts
  // =========================================================================
  describe('Default Page Layouts', () => {
    it('generates pristine default layouts for each supported page', () => {
      for (const pageId of SUPPORTED_PAGES) {
        const layout = createDefaultPageLayout(pageId);
        assert.strictEqual(layout.pageId, pageId);
        assert.strictEqual(layout.version, LAYOUT_SCHEMA_VERSION);
        assert.ok(layout.widgets.length > 0, `Layout for ${pageId} must contain widgets`);

        // Check sequential ordering starting from 0
        layout.widgets.forEach((w, index) => {
          assert.strictEqual(w.order, index, `Widget ${w.widgetId} on ${pageId} order mismatch`);
          assert.strictEqual(w.visible, true, `Default widget ${w.widgetId} on ${pageId} must be visible`);
          assert.ok(w.size, `Widget ${w.widgetId} must have size`);
        });

        // Ensure all canonical page widgets are included
        const canonical = CANONICAL_PAGE_WIDGET_ORDERS[pageId];
        for (const expectedId of canonical) {
          const found = layout.widgets.find((w) => w.widgetId === expectedId);
          assert.ok(found, `Canonical widget "${expectedId}" must exist in default layout for ${pageId}`);
        }
      }
    });

    it('creates root customization state with all 7 pages initialized', () => {
      const rootState = createDefaultCustomizationState();
      assert.strictEqual(rootState.version, LAYOUT_SCHEMA_VERSION);
      assert.ok(rootState.updatedAt);

      for (const pageId of SUPPORTED_PAGES) {
        assert.ok(rootState.layouts[pageId], `Root state missing page: ${pageId}`);
        assert.strictEqual(rootState.layouts[pageId].pageId, pageId);
      }
    });
  });

  // =========================================================================
  // 4. Schema Validation & Normalization
  // =========================================================================
  describe('Schema Validation & Normalization', () => {
    it('validates a pristine default layout with zero errors', () => {
      const defaultOverview = createDefaultPageLayout('overview');
      const result = validatePageLayout(defaultOverview, 'overview');
      assert.strictEqual(result.valid, true);
      assert.strictEqual(result.errors.length, 0);
      assert.strictEqual(result.data.widgets.length, defaultOverview.widgets.length);

      const rootValidation = validateCustomizationState(createDefaultCustomizationState());
      assert.strictEqual(rootValidation.valid, true);
      assert.strictEqual(rootValidation.errors.length, 0);
    });

    it('rejects non-object candidates and falls back to default layout', () => {
      const resultNull = validatePageLayout(null, 'forecast');
      assert.strictEqual(resultNull.valid, false);
      assert.strictEqual(resultNull.data.pageId, 'forecast');
      assert.ok(resultNull.errors.length > 0);

      const resultString = validatePageLayout('corrupted_string', 'forecast');
      assert.strictEqual(resultString.valid, false);
      assert.strictEqual(resultString.data.pageId, 'forecast');
    });

    it('eliminates duplicate widget IDs, preserving the first instance', () => {
      const candidate: PageLayout = {
        pageId: 'overview',
        version: LAYOUT_SCHEMA_VERSION,
        updatedAt: new Date().toISOString(),
        widgets: [
          { widgetId: 'overview-demo-disclaimer', order: 0, size: 'full', visible: true },
          { widgetId: 'overview-kpi-summary', order: 1, size: 'full', visible: true },
          // Duplicate insertion
          { widgetId: 'overview-kpi-summary', order: 2, size: 'lg', visible: false },
          { widgetId: 'overview-forecast-chart', order: 3, size: 'lg', visible: true },
        ],
      };

      const result = validatePageLayout(candidate, 'overview');
      assert.strictEqual(result.valid, false);
      assert.ok(result.errors.some((e) => e.includes('Duplicate widget ID')));

      const kpiInstances = result.data.widgets.filter((w) => w.widgetId === 'overview-kpi-summary');
      assert.strictEqual(kpiInstances.length, 1);
      assert.strictEqual(kpiInstances[0].size, 'full'); // preserved first instance
    });

    it('filters out incompatible widgets from foreign pages', () => {
      const candidate: PageLayout = {
        pageId: 'overview',
        version: LAYOUT_SCHEMA_VERSION,
        updatedAt: new Date().toISOString(),
        widgets: [
          { widgetId: 'overview-demo-disclaimer', order: 0, size: 'full', visible: true },
          // Foreign widget belonging to settings
          { widgetId: 'settings-business-profile', order: 1, size: 'full', visible: true },
        ],
      };

      const result = validatePageLayout(candidate, 'overview');
      assert.strictEqual(result.valid, false);
      const foreign = result.data.widgets.find((w) => w.widgetId === 'settings-business-profile');
      assert.strictEqual(foreign, undefined);
    });

    it('CRITICAL SAFETY: Enforces visible: true on required disclaimers and warnings', () => {
      const candidate: PageLayout = {
        pageId: 'forecast',
        version: LAYOUT_SCHEMA_VERSION,
        updatedAt: new Date().toISOString(),
        widgets: [
          // Attempting to hide mandatory breach alert and demo notice
          { widgetId: 'forecast-demo-disclaimer', order: 0, size: 'full', visible: false },
          { widgetId: 'forecast-breach-alert', order: 1, size: 'full', visible: false },
          { widgetId: 'forecast-metrics-summary', order: 2, size: 'full', visible: false },
        ],
      };

      const result = validatePageLayout(candidate, 'forecast');
      const disclaimer = result.data.widgets.find((w) => w.widgetId === 'forecast-demo-disclaimer');
      const alert = result.data.widgets.find((w) => w.widgetId === 'forecast-breach-alert');
      const metrics = result.data.widgets.find((w) => w.widgetId === 'forecast-metrics-summary');

      assert.ok(disclaimer);
      assert.strictEqual(disclaimer.visible, true, 'Required disclaimer MUST be forced visible');

      assert.ok(alert);
      assert.strictEqual(alert.visible, true, 'Required breach alert MUST be forced visible');

      assert.ok(metrics);
      assert.strictEqual(metrics.visible, false, 'Non-required widget may be hidden');
    });

    it('re-inserts missing registered widgets if omitted from payload', () => {
      const candidate: PageLayout = {
        pageId: 'scenarios',
        version: LAYOUT_SCHEMA_VERSION,
        updatedAt: new Date().toISOString(),
        widgets: [
          // Omitted scenarios-backend-notice and scenarios-table
          { widgetId: 'scenarios-controls', order: 0, size: 'full', visible: true },
          { widgetId: 'scenarios-chart', order: 1, size: 'full', visible: true },
        ],
      };

      const result = validatePageLayout(candidate, 'scenarios');
      const notice = result.data.widgets.find((w) => w.widgetId === 'scenarios-backend-notice');
      const table = result.data.widgets.find((w) => w.widgetId === 'scenarios-table');

      assert.ok(notice, 'Missing required notice must be re-inserted');
      assert.strictEqual(notice.visible, true);
      assert.ok(table, 'Missing registered table must be re-inserted');
    });

    it('falls back invalid widget size to allowed default', () => {
      const itemValidation = validateWidgetLayoutItem(
        {
          widgetId: 'overview-demo-disclaimer',
          size: 'invalid_mini_size',
          visible: true,
          order: 0,
        },
        'overview',
        0
      );

      assert.strictEqual(itemValidation.valid, true);
      assert.strictEqual(itemValidation.item?.size, 'full');
    });

    it('falls back invalid accent color to widget default color', () => {
      const itemValidation = validateWidgetLayoutItem(
        {
          widgetId: 'overview-forecast-chart',
          accentColor: 'non_existent_neon',
          visible: true,
          order: 0,
        },
        'overview',
        0
      );

      assert.strictEqual(itemValidation.valid, true);
      assert.strictEqual(itemValidation.item?.accentColor, 'blue');
    });

    it('normalizes non-contiguous order numbers to contiguous sequential integers', () => {
      const candidate: PageLayout = {
        pageId: 'rescue',
        version: LAYOUT_SCHEMA_VERSION,
        updatedAt: new Date().toISOString(),
        widgets: [
          { widgetId: 'rescue-backend-notice', order: 50, size: 'full', visible: true },
          { widgetId: 'rescue-cash-risk-summary', order: 12, size: 'full', visible: true },
          { widgetId: 'rescue-breach-explanation', order: 100, size: 'full', visible: true },
          { widgetId: 'rescue-actions-list', order: 2, size: 'full', visible: true },
          { widgetId: 'rescue-simulation-view', order: 34, size: 'full', visible: true },
        ],
      };

      const result = validatePageLayout(candidate, 'rescue');
      const orders = result.data.widgets.map((w) => w.order);
      assert.deepStrictEqual(orders, [0, 1, 2, 3, 4]);

      // Check sorting: lowest original order (rescue-actions-list @ order 2) is at index 0
      assert.strictEqual(result.data.widgets[0].widgetId, 'rescue-actions-list');
    });
  });

  // =========================================================================
  // 5. Page Isolation
  // =========================================================================
  describe('Page Layout Isolation', () => {
    it('modifying one page layout does not affect or mutate other pages', () => {
      const overviewLayout = createDefaultPageLayout('overview');
      // Reorder widgets for overview
      overviewLayout.widgets.reverse();
      overviewLayout.widgets.forEach((w, idx) => {
        w.order = idx;
      });

      const saveRes = savePageLayout('overview', overviewLayout);
      assert.strictEqual(saveRes.success, true);

      // Verify overview has new order
      const loadedOverview = loadPageLayout('overview');
      assert.strictEqual(loadedOverview.widgets[0].widgetId, overviewLayout.widgets[0].widgetId);

      // Verify all other 6 pages remain untouched canonical defaults
      const otherPages: DashboardPageId[] = [
        'forecast',
        'rescue',
        'scenarios',
        'payments',
        'analytics',
        'settings',
      ];

      for (const otherPageId of otherPages) {
        const loadedOther = loadPageLayout(otherPageId);
        const defaultOther = createDefaultPageLayout(otherPageId);
        assert.strictEqual(loadedOther.widgets.length, defaultOther.widgets.length);
        assert.strictEqual(loadedOther.widgets[0].widgetId, defaultOther.widgets[0].widgetId);
      }
    });

    it('persisting distinct layouts across multiple pages maintains independent configurations', () => {
      // Modify Forecast
      const forecastLayout = createDefaultPageLayout('forecast');
      const forecastMetrics = forecastLayout.widgets.find((w) => w.widgetId === 'forecast-metrics-summary');
      if (forecastMetrics) forecastMetrics.accentColor = 'emerald';
      savePageLayout('forecast', forecastLayout);

      // Modify Payments
      const paymentsLayout = createDefaultPageLayout('payments');
      const paymentsTable = paymentsLayout.widgets.find((w) => w.widgetId === 'payments-table');
      if (paymentsTable) paymentsTable.accentColor = 'purple';
      savePageLayout('payments', paymentsLayout);

      // Verify both preserved independently
      const reloadedForecast = loadPageLayout('forecast');
      const reloadedPayments = loadPageLayout('payments');

      const reloadedMetrics = reloadedForecast.widgets.find((w) => w.widgetId === 'forecast-metrics-summary');
      const reloadedTable = reloadedPayments.widgets.find((w) => w.widgetId === 'payments-table');

      assert.strictEqual(reloadedMetrics?.accentColor, 'emerald');
      assert.strictEqual(reloadedTable?.accentColor, 'purple');
    });
  });

  // =========================================================================
  // 6. Storage Persistence & Corrupted Storage Handling
  // =========================================================================
  describe('Storage Persistence & Resilience', () => {
    it('returns default customization state when storage is empty', () => {
      localStorage.clear();
      const state = loadCustomizationState();
      assert.strictEqual(state.version, LAYOUT_SCHEMA_VERSION);
      assert.ok(state.layouts.overview);
      assert.ok(state.layouts.forecast);
    });

    it('faithfully persists and reloads root customization state', () => {
      const state = createDefaultCustomizationState();
      const overviewKpi = state.layouts.overview.widgets.find((w) => w.widgetId === 'overview-kpi-summary');
      if (overviewKpi) overviewKpi.accentColor = 'pink';

      const result = saveAllCustomizationState(state);
      assert.strictEqual(result.success, true);

      const loaded = loadCustomizationState();
      const loadedKpi = loaded.layouts.overview.widgets.find((w) => w.widgetId === 'overview-kpi-summary');
      assert.strictEqual(loadedKpi?.accentColor, 'pink');
    });

    it('recovers gracefully from corrupted JSON in localStorage without throwing', () => {
      localStorage.setItem(CUSTOMIZATION_STORAGE_KEY, '{ invalid_malformed_json ::: !!!');
      const loaded = loadCustomizationState();

      assert.strictEqual(loaded.version, LAYOUT_SCHEMA_VERSION);
      assert.ok(loaded.layouts.overview);
      assert.ok(loaded.layouts.rescue);
    });

    it('falls back to defaults when stored value is not an object (e.g. primitive number or array)', () => {
      localStorage.setItem(CUSTOMIZATION_STORAGE_KEY, '42');
      const loadedFromNumber = loadCustomizationState();
      assert.strictEqual(loadedFromNumber.version, LAYOUT_SCHEMA_VERSION);

      localStorage.setItem(CUSTOMIZATION_STORAGE_KEY, '["array_instead_of_state"]');
      const loadedFromArray = loadCustomizationState();
      assert.strictEqual(loadedFromArray.version, LAYOUT_SCHEMA_VERSION);
    });

    it('falls back to defaults when stored schema version is unsupported', () => {
      const incompatible = {
        version: 999, // unsupported future schema version
        updatedAt: new Date().toISOString(),
        layouts: {},
      };
      localStorage.setItem(CUSTOMIZATION_STORAGE_KEY, JSON.stringify(incompatible));

      const loaded = loadCustomizationState();
      assert.strictEqual(loaded.version, LAYOUT_SCHEMA_VERSION);
      assert.ok(loaded.layouts.forecast);
    });

    it('handles simulated quota exceeded error on write gracefully', () => {
      const originalSetItem = localStorage.setItem;
      localStorage.setItem = () => {
        throw new Error('QuotaExceededError: storage full');
      };

      try {
        const defaultLayout = createDefaultPageLayout('overview');
        const res = savePageLayout('overview', defaultLayout);
        assert.strictEqual(res.success, false);
        assert.ok(res.errors && res.errors.length > 0);
      } finally {
        localStorage.setItem = originalSetItem;
      }
    });
  });

  // =========================================================================
  // 7. Reset Behavior
  // =========================================================================
  describe('Reset Operations', () => {
    it('resetPageLayout resets only the specified page while leaving other pages intact', () => {
      // Customize Overview and Scenarios
      const overview = createDefaultPageLayout('overview');
      overview.widgets[1].accentColor = 'rose';
      savePageLayout('overview', overview);

      const scenarios = createDefaultPageLayout('scenarios');
      scenarios.widgets[1].accentColor = 'cyan';
      savePageLayout('scenarios', scenarios);

      // Reset Scenarios only
      const resetScenarios = resetPageLayout('scenarios');
      assert.strictEqual(resetScenarios.pageId, 'scenarios');

      // Verify Scenarios is back to default
      const loadedScenarios = loadPageLayout('scenarios');
      assert.strictEqual(loadedScenarios.widgets[1].accentColor, WIDGET_REGISTRY[loadedScenarios.widgets[1].widgetId].defaultColor);

      // Verify Overview retained custom color
      const loadedOverview = loadPageLayout('overview');
      assert.strictEqual(loadedOverview.widgets[1].accentColor, 'rose');
    });

    it('resetAllCustomizationState removes storage key and returns canonical defaults for all pages', () => {
      const overview = createDefaultPageLayout('overview');
      overview.widgets[1].accentColor = 'rose';
      savePageLayout('overview', overview);

      assert.ok(localStorage.getItem(CUSTOMIZATION_STORAGE_KEY));

      const resetState = resetAllCustomizationState();
      assert.strictEqual(localStorage.getItem(CUSTOMIZATION_STORAGE_KEY), null);
      assert.strictEqual(resetState.version, LAYOUT_SCHEMA_VERSION);

      for (const pageId of SUPPORTED_PAGES) {
        assert.ok(resetState.layouts[pageId]);
      }
    });
  });

  // =========================================================================
  // 8. Strict Financial Data Separation
  // =========================================================================
  describe('Financial Data Separation Discipline', () => {
    it('customization state contains strictly layout presentation properties with zero financial balances', () => {
      const state = createDefaultCustomizationState();
      const serialized = JSON.stringify(state);

      // Financial balance fields that MUST NOT exist in customization storage
      const forbiddenFinancialKeys = [
        'closing_balance_cents',
        'receipts_cents',
        'expenses_cents',
        'safety_reserve_cents',
        'projected_shortfall_cents',
        'burn_rate_daily_cents',
        'net_variance_cents',
        'settlement_amount_cents',
        'bank_account',
      ];

      for (const key of forbiddenFinancialKeys) {
        assert.strictEqual(
          serialized.includes(`"${key}"`),
          false,
          `Customization state must not contain financial data field "${key}"`
        );
      }
    });
  });
});
