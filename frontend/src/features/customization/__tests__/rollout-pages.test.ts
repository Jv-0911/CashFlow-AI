import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import {
  createDefaultPageLayout,
  LAYOUT_SCHEMA_VERSION,
} from '../defaults.ts';
import {
  CUSTOMIZATION_STORAGE_KEY,
  loadPageLayout,
  savePageLayout,
  loadCustomizationState,
} from '../storage.ts';
import {
  WIDGET_REGISTRY,
  isWidgetRequired,
  isWidgetSafetyCritical,
  getWidgetsForPage,
} from '../widget-registry.ts';
import type {
  DashboardPageId,
  MutedColorId,
  PageLayout,
  WidgetId,
  WidgetSize,
} from '../types.ts';

// In-memory localStorage mock for Node test runner
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

/**
 * Test harness replicating the state machine of useEditLayout hook
 */
function createPageEditHarness(pageId: DashboardPageId) {
  let savedLayout = loadPageLayout(pageId);
  let draftLayout = JSON.parse(JSON.stringify(savedLayout)) as PageLayout;
  let isEditing = false;
  let drawerOpen = false;

  const startEditing = () => {
    savedLayout = loadPageLayout(pageId);
    draftLayout = JSON.parse(JSON.stringify(savedLayout));
    isEditing = true;
    drawerOpen = false;
  };

  const cancelEditing = () => {
    draftLayout = JSON.parse(JSON.stringify(savedLayout));
    isEditing = false;
    drawerOpen = false;
  };

  const saveEditing = () => {
    const res = savePageLayout(pageId, draftLayout);
    if (res.success) {
      savedLayout = JSON.parse(JSON.stringify(draftLayout));
      isEditing = false;
      drawerOpen = false;
    }
    return res;
  };

  const reorderWidgets = (sourceId: string, targetId: string) => {
    const items = [...draftLayout.widgets];
    const sourceIndex = items.findIndex((w) => w.widgetId === sourceId);
    const targetIndex = items.findIndex((w) => w.widgetId === targetId);
    if (sourceIndex === -1 || targetIndex === -1 || sourceIndex === targetIndex) return;

    const [moved] = items.splice(sourceIndex, 1);
    items.splice(targetIndex, 0, moved);
    draftLayout.widgets = items.map((w, idx) => ({ ...w, order: idx }));
  };

  const changeWidgetSize = (widgetId: string, newSize: WidgetSize) => {
    const widgetDef = WIDGET_REGISTRY[widgetId as WidgetId];
    if (!widgetDef || !widgetDef.allowedSizes.includes(newSize)) return;

    draftLayout.widgets = draftLayout.widgets.map((w) =>
      w.widgetId === widgetId ? { ...w, size: newSize } : w
    );
  };

  const changeWidgetColor = (widgetId: string, newColor: MutedColorId) => {
    draftLayout.widgets = draftLayout.widgets.map((w) =>
      w.widgetId === widgetId ? { ...w, accentColor: newColor } : w
    );
  };

  const removeWidget = (widgetId: string) => {
    const widgetDef = WIDGET_REGISTRY[widgetId as WidgetId];
    if (!widgetDef) return;
    if (widgetDef.isRequired || widgetDef.isSafetyCritical) {
      return; // Protected
    }
    draftLayout.widgets = draftLayout.widgets.map((w) =>
      w.widgetId === widgetId ? { ...w, visible: false } : w
    );
  };

  const addWidget = (widgetId: string) => {
    const widgetDef = WIDGET_REGISTRY[widgetId as WidgetId];
    if (!widgetDef || !widgetDef.compatiblePages.includes(pageId)) return;

    const existing = draftLayout.widgets.find((w) => w.widgetId === widgetId);
    if (existing) {
      if (!existing.visible) {
        draftLayout.widgets = draftLayout.widgets.map((w) =>
          w.widgetId === widgetId ? { ...w, visible: true } : w
        );
      }
      return;
    }

    draftLayout.widgets.push({
      widgetId: widgetId as WidgetId,
      size: widgetDef.defaultSize,
      accentColor: widgetDef.defaultColor,
      visible: true,
      order: draftLayout.widgets.length,
    });
  };

  const resetDraftToDefaults = () => {
    draftLayout = createDefaultPageLayout(pageId);
  };

  const hasUnsavedChanges = () => {
    return JSON.stringify(draftLayout) !== JSON.stringify(savedLayout);
  };

  return {
    get savedLayout() {
      return savedLayout;
    },
    get draftLayout() {
      return draftLayout;
    },
    get isEditing() {
      return isEditing;
    },
    get drawerOpen() {
      return drawerOpen;
    },
    setDrawerOpen: (open: boolean) => {
      drawerOpen = open;
    },
    startEditing,
    cancelEditing,
    saveEditing,
    reorderWidgets,
    changeWidgetSize,
    changeWidgetColor,
    removeWidget,
    addWidget,
    resetDraftToDefaults,
    hasUnsavedChanges,
  };
}

describe('Milestone 10.3: Seven-Page Customization Rollout Integration Tests', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  // =========================================================================
  // 1. Forecast Page Integration
  // =========================================================================
  describe('ForecastPage Customization', () => {
    it('initializes with default forecast layout and protections', () => {
      const harness = createPageEditHarness('forecast');
      assert.strictEqual(harness.savedLayout.pageId, 'forecast');
      assert.ok(harness.savedLayout.widgets.length >= 6);

      // Verify safety critical & required widgets
      assert.strictEqual(isWidgetRequired('forecast-demo-disclaimer'), true);
      assert.strictEqual(isWidgetSafetyCritical('forecast-demo-disclaimer'), true);
      assert.strictEqual(isWidgetSafetyCritical('forecast-breach-alert'), true);
    });

    it('prevents removing required or safety-critical forecast widgets', () => {
      const harness = createPageEditHarness('forecast');
      harness.startEditing();

      // Attempt to remove required demo disclaimer
      harness.removeWidget('forecast-demo-disclaimer');
      const disclaimer = harness.draftLayout.widgets.find((w) => w.widgetId === 'forecast-demo-disclaimer');
      assert.strictEqual(disclaimer?.visible, true, 'forecast-demo-disclaimer must remain visible');

      // Attempt to remove safety-critical breach alert
      harness.removeWidget('forecast-breach-alert');
      const alert = harness.draftLayout.widgets.find((w) => w.widgetId === 'forecast-breach-alert');
      assert.strictEqual(alert?.visible, true, 'forecast-breach-alert must remain visible');

      // Optional widget can be removed
      harness.removeWidget('forecast-table');
      const table = harness.draftLayout.widgets.find((w) => w.widgetId === 'forecast-table');
      assert.strictEqual(table?.visible, false, 'Optional forecast table can be hidden');
    });

    it('reorders, resizes, recolors, and saves forecast layout', () => {
      const harness = createPageEditHarness('forecast');
      harness.startEditing();

      // Reorder
      harness.reorderWidgets('forecast-table', 'forecast-chart');
      // Resize
      harness.changeWidgetSize('forecast-metrics-summary', 'lg');
      // Recolor using valid palette color
      harness.changeWidgetColor('forecast-chart', 'purple');

      assert.strictEqual(harness.hasUnsavedChanges(), true);
      const saveRes = harness.saveEditing();
      assert.strictEqual(saveRes.success, true);

      // Verify reloaded layout
      const reloaded = loadPageLayout('forecast');
      const chart = reloaded.widgets.find((w) => w.widgetId === 'forecast-chart');
      assert.strictEqual(chart?.accentColor, 'purple');
      assert.strictEqual(chart?.size, 'full');
    });
  });

  // =========================================================================
  // 2. Rescue Page Integration
  // =========================================================================
  describe('RescuePage Customization', () => {
    it('initializes with default rescue widgets', () => {
      const harness = createPageEditHarness('rescue');
      assert.strictEqual(harness.savedLayout.pageId, 'rescue');
      const widgetIds = harness.savedLayout.widgets.map((w) => w.widgetId);
      assert.ok(widgetIds.includes('rescue-backend-notice'));
      assert.ok(widgetIds.includes('rescue-cash-risk-summary'));
      assert.ok(widgetIds.includes('rescue-breach-explanation'));
      assert.ok(widgetIds.includes('rescue-actions-list'));
      assert.ok(widgetIds.includes('rescue-simulation-view'));
    });

    it('enforces safety-critical protection on rescue simulation view', () => {
      const harness = createPageEditHarness('rescue');
      harness.startEditing();

      assert.strictEqual(isWidgetSafetyCritical('rescue-simulation-view'), true);
      harness.removeWidget('rescue-simulation-view');

      const sim = harness.draftLayout.widgets.find((w) => w.widgetId === 'rescue-simulation-view');
      assert.strictEqual(sim?.visible, true, 'Simulation view cannot be removed');
    });

    it('supports reordering and palette accenting for rescue cards', () => {
      const harness = createPageEditHarness('rescue');
      harness.startEditing();

      harness.changeWidgetColor('rescue-actions-list', 'emerald');
      harness.changeWidgetSize('rescue-actions-list', 'lg');
      harness.saveEditing();

      const reloaded = loadPageLayout('rescue');
      const actions = reloaded.widgets.find((w) => w.widgetId === 'rescue-actions-list');
      assert.strictEqual(actions?.accentColor, 'emerald');
      assert.strictEqual(actions?.size, 'lg');
    });
  });

  // =========================================================================
  // 3. Scenario Page Integration
  // =========================================================================
  describe('ScenarioPage Customization', () => {
    it('initializes with default scenario widgets and protects backend notice', () => {
      const harness = createPageEditHarness('scenarios');
      assert.strictEqual(harness.savedLayout.pageId, 'scenarios');

      assert.strictEqual(isWidgetRequired('scenarios-backend-notice'), true);
      assert.strictEqual(isWidgetSafetyCritical('scenarios-backend-notice'), true);

      harness.startEditing();
      harness.removeWidget('scenarios-backend-notice');
      const notice = harness.draftLayout.widgets.find((w) => w.widgetId === 'scenarios-backend-notice');
      assert.strictEqual(notice?.visible, true, 'Backend notice must never be hidden');
    });

    it('allows hiding and restoring optional controls and chart widgets', () => {
      const harness = createPageEditHarness('scenarios');
      harness.startEditing();

      // Hide table
      harness.removeWidget('scenarios-table');
      assert.strictEqual(
        harness.draftLayout.widgets.find((w) => w.widgetId === 'scenarios-table')?.visible,
        false
      );

      // Restore via addWidget
      harness.addWidget('scenarios-table');
      assert.strictEqual(
        harness.draftLayout.widgets.find((w) => w.widgetId === 'scenarios-table')?.visible,
        true
      );
    });
  });

  // =========================================================================
  // 4. Payments & Ledger Page Integration
  // =========================================================================
  describe('PaymentsLedgerPage Customization', () => {
    it('initializes with payment ledger widgets and enforces verified ledger protection', () => {
      const harness = createPageEditHarness('payments');
      assert.strictEqual(harness.savedLayout.pageId, 'payments');

      // Check required & safety critical flags
      assert.strictEqual(isWidgetRequired('payments-backend-notice'), true);
      assert.strictEqual(isWidgetSafetyCritical('payments-backend-notice'), true);
      assert.strictEqual(isWidgetSafetyCritical('payments-table'), true);

      harness.startEditing();

      // Attempt to remove notice
      harness.removeWidget('payments-backend-notice');
      assert.strictEqual(
        harness.draftLayout.widgets.find((w) => w.widgetId === 'payments-backend-notice')?.visible,
        true
      );

      // Attempt to remove table
      harness.removeWidget('payments-table');
      assert.strictEqual(
        harness.draftLayout.widgets.find((w) => w.widgetId === 'payments-table')?.visible,
        true
      );
    });

    it('allows customizing summary cards and search controls', () => {
      const harness = createPageEditHarness('payments');
      harness.startEditing();

      harness.changeWidgetColor('payments-summary-cards', 'blue');
      harness.changeWidgetSize('payments-summary-cards', 'lg');
      harness.saveEditing();

      const reloaded = loadPageLayout('payments');
      const cards = reloaded.widgets.find((w) => w.widgetId === 'payments-summary-cards');
      assert.strictEqual(cards?.accentColor, 'blue');
      assert.strictEqual(cards?.size, 'lg');
    });
  });

  // =========================================================================
  // 5. Analytics Page Integration
  // =========================================================================
  describe('AnalyticsPage Customization', () => {
    it('initializes with analytics widgets and protects demo notice', () => {
      const harness = createPageEditHarness('analytics');
      assert.strictEqual(harness.savedLayout.pageId, 'analytics');

      assert.strictEqual(isWidgetRequired('analytics-demo-notice'), true);
      assert.strictEqual(isWidgetSafetyCritical('analytics-demo-notice'), true);

      harness.startEditing();
      harness.removeWidget('analytics-demo-notice');
      assert.strictEqual(
        harness.draftLayout.widgets.find((w) => w.widgetId === 'analytics-demo-notice')?.visible,
        true
      );
    });

    it('supports customizing KPI cards, cash flow trend chart, and comparison card', () => {
      const harness = createPageEditHarness('analytics');
      harness.startEditing();

      harness.changeWidgetColor('analytics-trend-chart', 'purple');
      harness.changeWidgetSize('analytics-kpi-cards', 'lg');
      harness.saveEditing();

      const reloaded = loadPageLayout('analytics');
      assert.strictEqual(
        reloaded.widgets.find((w) => w.widgetId === 'analytics-trend-chart')?.accentColor,
        'purple'
      );
      assert.strictEqual(
        reloaded.widgets.find((w) => w.widgetId === 'analytics-kpi-cards')?.size,
        'lg'
      );
    });
  });

  // =========================================================================
  // 6. Settings Page Integration
  // =========================================================================
  describe('SettingsPage Customization', () => {
    it('initializes with settings cards and protects policy governance card', () => {
      const harness = createPageEditHarness('settings');
      assert.strictEqual(harness.savedLayout.pageId, 'settings');

      assert.strictEqual(isWidgetSafetyCritical('settings-policy-governance'), true);

      harness.startEditing();
      harness.removeWidget('settings-policy-governance');
      assert.strictEqual(
        harness.draftLayout.widgets.find((w) => w.widgetId === 'settings-policy-governance')?.visible,
        true,
        'Safety reserve policy governance card cannot be removed'
      );
    });

    it('supports reordering profile, governance, and display cards', () => {
      const harness = createPageEditHarness('settings');
      harness.startEditing();

      // Reorder display preferences to top
      harness.reorderWidgets('settings-display-preferences', 'settings-business-profile');
      harness.changeWidgetColor('settings-display-preferences', 'cyan');
      harness.saveEditing();

      const reloaded = loadPageLayout('settings');
      assert.strictEqual(reloaded.widgets[0].widgetId, 'settings-display-preferences');
      assert.strictEqual(reloaded.widgets[0].accentColor, 'cyan');
    });
  });

  // =========================================================================
  // 7. Multi-Page Independence & Storage Isolation
  // =========================================================================
  describe('Seven-Page Layout Independence & Persistence', () => {
    it('ensures every dashboard page maintains a completely isolated saved layout', () => {
      const pages: DashboardPageId[] = [
        'overview',
        'forecast',
        'rescue',
        'scenarios',
        'payments',
        'analytics',
        'settings',
      ];

      // Mutate every page with distinct colors and sizes
      for (const pageId of pages) {
        const harness = createPageEditHarness(pageId);
        harness.startEditing();
        const firstWidget = harness.draftLayout.widgets[0];
        if (firstWidget) {
          harness.changeWidgetColor(firstWidget.widgetId, 'rose');
        }
        harness.saveEditing();
      }

      // Verify each page's distinct persisted state
      for (const pageId of pages) {
        const layout = loadPageLayout(pageId);
        assert.strictEqual(layout.pageId, pageId);
        assert.strictEqual(layout.widgets[0].accentColor, 'rose');
      }

      // Mutate only forecast to amber
      const forecastHarness = createPageEditHarness('forecast');
      forecastHarness.startEditing();
      forecastHarness.changeWidgetColor(forecastHarness.draftLayout.widgets[0].widgetId, 'amber');
      forecastHarness.saveEditing();

      // Check that Overview and other pages were NOT modified
      const overviewLayout = loadPageLayout('overview');
      assert.strictEqual(overviewLayout.widgets[0].accentColor, 'rose');

      const forecastLayout = loadPageLayout('forecast');
      assert.strictEqual(forecastLayout.widgets[0].accentColor, 'amber');
    });

    it('rejects cross-page widget injection and enforces page compatibility', () => {
      const harness = createPageEditHarness('analytics');
      harness.startEditing();

      // Attempt to add a widget from forecast onto analytics
      harness.addWidget('forecast-breach-alert');
      const injected = harness.draftLayout.widgets.find((w) => w.widgetId === ('forecast-breach-alert' as WidgetId));
      assert.strictEqual(injected, undefined, 'Cannot add forecast widget onto analytics page');

      // Verify compatible widgets only
      const compatibleDefs = getWidgetsForPage('analytics');
      for (const def of compatibleDefs) {
        assert.ok(def.compatiblePages.includes('analytics'));
      }
    });

    it('handles corrupted single-page storage with graceful per-page fallback', () => {
      // Setup valid customizations across pages
      const state = loadCustomizationState();
      state.layouts.overview.widgets[0].accentColor = 'rose';
      localStorage.setItem(CUSTOMIZATION_STORAGE_KEY, JSON.stringify(state));

      // Now inject corrupted JSON for 'rescue' in the raw storage object
      const rawStored = JSON.parse(localStorage.getItem(CUSTOMIZATION_STORAGE_KEY) || '{}');
      rawStored.layouts.rescue = { corrupted: true }; // invalid structure
      localStorage.setItem(CUSTOMIZATION_STORAGE_KEY, JSON.stringify(rawStored));

      // Loading rescue recovers default layout safely
      const rescueLayout = loadPageLayout('rescue');
      assert.strictEqual(rescueLayout.pageId, 'rescue');
      assert.strictEqual(rescueLayout.version, LAYOUT_SCHEMA_VERSION);

      // Loading overview preserves the valid customized state
      const overviewLayout = loadPageLayout('overview');
      assert.strictEqual(overviewLayout.widgets[0].accentColor, 'rose');
    });

    it('retains customizations after simulated browser refresh', () => {
      // Edit and save scenarios layout
      const harness = createPageEditHarness('scenarios');
      harness.startEditing();
      harness.changeWidgetColor('scenarios-chart', 'purple');
      harness.changeWidgetSize('scenarios-controls', 'lg');
      harness.saveEditing();

      // Simulate full browser reload: re-read directly from storage engine
      const rehydrated = loadPageLayout('scenarios');
      const chart = rehydrated.widgets.find((w) => w.widgetId === 'scenarios-chart');
      const controls = rehydrated.widgets.find((w) => w.widgetId === 'scenarios-controls');

      assert.strictEqual(chart?.accentColor, 'purple');
      assert.strictEqual(controls?.size, 'lg');
    });

    it('allows resetting any single page to default without affecting other pages', () => {
      // Customize payments and analytics with valid palette colors
      const paymentsHarness = createPageEditHarness('payments');
      paymentsHarness.startEditing();
      paymentsHarness.changeWidgetColor('payments-summary-cards', 'purple');
      paymentsHarness.saveEditing();

      const analyticsHarness = createPageEditHarness('analytics');
      analyticsHarness.startEditing();
      analyticsHarness.changeWidgetColor('analytics-trend-chart', 'purple');
      analyticsHarness.saveEditing();

      // Reset only payments
      paymentsHarness.startEditing();
      paymentsHarness.resetDraftToDefaults();
      paymentsHarness.saveEditing();

      // Payments is reset to default
      const resetPayments = loadPageLayout('payments');
      const defaultPayments = createDefaultPageLayout('payments');
      assert.deepStrictEqual(resetPayments.widgets, defaultPayments.widgets);

      // Analytics retains its custom purple accent
      const retainedAnalytics = loadPageLayout('analytics');
      const chart = retainedAnalytics.widgets.find((w) => w.widgetId === 'analytics-trend-chart');
      assert.strictEqual(chart?.accentColor, 'purple');
    });
  });

  // =========================================================================
  // 8. Direct-Manipulation Visual Layout Editor Tests
  // =========================================================================
  describe('Direct-Manipulation Drag-and-Drop Visual Layout Editor', () => {
    const allPages: DashboardPageId[] = [
      'overview',
      'forecast',
      'rescue',
      'scenarios',
      'payments',
      'analytics',
      'settings',
    ];

    it('activates draggable state across all 7 pages only when edit mode is toggled', () => {
      for (const pageId of allPages) {
        const harness = createPageEditHarness(pageId);
        // Before edit mode
        assert.strictEqual(harness.isEditing, false);

        // Click Edit Dashboard
        harness.startEditing();
        assert.strictEqual(harness.isEditing, true);

        // Reordering becomes active in draft layout
        const initialOrder = harness.draftLayout.widgets.map((w) => w.widgetId);
        if (initialOrder.length >= 2) {
          harness.reorderWidgets(initialOrder[1], initialOrder[0]);
          assert.strictEqual(harness.draftLayout.widgets[0].widgetId, initialOrder[1]);
          assert.strictEqual(harness.draftLayout.widgets[1].widgetId, initialOrder[0]);
        }

        // Cancel restores non-editing state and discards drag
        harness.cancelEditing();
        assert.strictEqual(harness.isEditing, false);
        const restoredOrder = harness.savedLayout.widgets.map((w) => w.widgetId);
        assert.deepStrictEqual(restoredOrder, initialOrder);
      }
    });

    it('automatically rearranges other widgets to make room during drag-and-drop', () => {
      const harness = createPageEditHarness('forecast');
      harness.startEditing();

      // Original order: [disclaimer, breach-alert, horizon-controls, metrics-summary, chart, table]
      const originalIds = harness.draftLayout.widgets.map((w) => w.widgetId);
      const lastWidgetId = originalIds[originalIds.length - 1]; // forecast-table
      const firstWidgetId = originalIds[0]; // forecast-demo-disclaimer

      // Drag last widget to very top
      harness.reorderWidgets(lastWidgetId, firstWidgetId);

      // Other widgets automatically slide down by one position
      assert.strictEqual(harness.draftLayout.widgets[0].widgetId, lastWidgetId);
      assert.strictEqual(harness.draftLayout.widgets[1].widgetId, firstWidgetId);

      // Ensure contiguous order indices: 0, 1, 2, ...
      harness.draftLayout.widgets.forEach((item, idx) => {
        assert.strictEqual(item.order, idx, `Widget at index ${idx} must have order ${idx}`);
      });

      // No widgets lost or duplicated
      const newIds = harness.draftLayout.widgets.map((w) => w.widgetId);
      assert.strictEqual(newIds.length, originalIds.length);
      assert.strictEqual(new Set(newIds).size, originalIds.length);
    });

    it('persists exact manual drag-and-drop order independently across refresh', () => {
      // 1. Manually drag widgets on Analytics
      const analyticsHarness = createPageEditHarness('analytics');
      analyticsHarness.startEditing();
      const initialAnalytics = analyticsHarness.draftLayout.widgets.map((w) => w.widgetId);
      // Move last widget to position 1
      analyticsHarness.reorderWidgets(initialAnalytics[initialAnalytics.length - 1], initialAnalytics[1]);
      analyticsHarness.saveEditing();

      // 2. Manually drag widgets on Settings
      const settingsHarness = createPageEditHarness('settings');
      settingsHarness.startEditing();
      // Move display preferences to top
      settingsHarness.reorderWidgets('settings-display-preferences', 'settings-business-profile');
      settingsHarness.saveEditing();

      // 3. Simulate browser reload / storage rehydration
      const rehydratedAnalytics = loadPageLayout('analytics');
      assert.strictEqual(
        rehydratedAnalytics.widgets[1].widgetId,
        initialAnalytics[initialAnalytics.length - 1]
      );

      const rehydratedSettings = loadPageLayout('settings');
      assert.strictEqual(
        rehydratedSettings.widgets[0].widgetId,
        'settings-display-preferences'
      );
    });

    it('retains all existing features (resize, color, add, remove, reset) alongside direct drag-and-drop', () => {
      const harness = createPageEditHarness('scenarios');
      harness.startEditing();

      // 1. Direct drag reorder
      harness.reorderWidgets('scenarios-chart', 'scenarios-controls');
      assert.strictEqual(harness.draftLayout.widgets[1].widgetId, 'scenarios-chart');

      // 2. Resize
      harness.changeWidgetSize('scenarios-chart', 'lg');
      assert.strictEqual(
        harness.draftLayout.widgets.find((w) => w.widgetId === 'scenarios-chart')?.size,
        'lg'
      );

      // 3. Color picker
      harness.changeWidgetColor('scenarios-chart', 'rose');
      assert.strictEqual(
        harness.draftLayout.widgets.find((w) => w.widgetId === 'scenarios-chart')?.accentColor,
        'rose'
      );

      // 4. Hide optional widget
      harness.removeWidget('scenarios-table');
      assert.strictEqual(
        harness.draftLayout.widgets.find((w) => w.widgetId === 'scenarios-table')?.visible,
        false
      );

      // 5. Restore widget from drawer
      harness.addWidget('scenarios-table');
      assert.strictEqual(
        harness.draftLayout.widgets.find((w) => w.widgetId === 'scenarios-table')?.visible,
        true
      );

      // 6. Save layout
      const saveRes = harness.saveEditing();
      assert.strictEqual(saveRes.success, true);

      // 7. Reset to defaults
      harness.startEditing();
      harness.resetDraftToDefaults();
      assert.deepStrictEqual(
        harness.draftLayout.widgets,
        createDefaultPageLayout('scenarios').widgets
      );
    });
  });
});

