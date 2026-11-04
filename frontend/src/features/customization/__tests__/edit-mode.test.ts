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
  validatePageLayout,
  validateCustomizationState,
  loadCustomizationState,
} from '../storage.ts';
import { WIDGET_REGISTRY, isWidgetRequired } from '../widget-registry.ts';
import type {
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
 * Pure test harness modeling the exact mutation logic of useEditLayout hook
 */
function createEditHarness(initialLayout: PageLayout) {
  let savedLayout = JSON.parse(JSON.stringify(initialLayout)) as PageLayout;
  let draftLayout = JSON.parse(JSON.stringify(initialLayout)) as PageLayout;
  let isEditing = false;
  let drawerOpen = false;

  const startEditing = () => {
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
    const res = savePageLayout(savedLayout.pageId, draftLayout);
    if (res.success) {
      savedLayout = JSON.parse(JSON.stringify(res.layout));
      draftLayout = JSON.parse(JSON.stringify(res.layout));
      isEditing = false;
      drawerOpen = false;
    }
    return res;
  };

  const reorderWidgets = (activeId: string, overId: string) => {
    if (activeId === overId) return;
    const oldIndex = draftLayout.widgets.findIndex((w) => w.widgetId === activeId);
    const newIndex = draftLayout.widgets.findIndex((w) => w.widgetId === overId);
    if (oldIndex === -1 || newIndex === -1) return;

    const items = [...draftLayout.widgets];
    const [moved] = items.splice(oldIndex, 1);
    items.splice(newIndex, 0, moved);

    draftLayout.widgets = items.map((item, idx) => ({ ...item, order: idx }));
    draftLayout.updatedAt = new Date().toISOString();
  };

  const changeWidgetSize = (widgetId: WidgetId, size: WidgetSize) => {
    const def = WIDGET_REGISTRY[widgetId];
    if (!def || !def.allowedSizes.includes(size)) return;
    draftLayout.widgets = draftLayout.widgets.map((w) =>
      w.widgetId === widgetId ? { ...w, size } : w
    );
    draftLayout.updatedAt = new Date().toISOString();
  };

  const changeWidgetColor = (widgetId: WidgetId, color: MutedColorId) => {
    draftLayout.widgets = draftLayout.widgets.map((w) =>
      w.widgetId === widgetId ? { ...w, accentColor: color } : w
    );
    draftLayout.updatedAt = new Date().toISOString();
  };

  const removeWidget = (widgetId: WidgetId) => {
    const def = WIDGET_REGISTRY[widgetId];
    if (def?.isRequired) return; // Cannot remove required widgets
    draftLayout.widgets = draftLayout.widgets.map((w) =>
      w.widgetId === widgetId ? { ...w, visible: false } : w
    );
    draftLayout.updatedAt = new Date().toISOString();
  };

  const addWidget = (widgetId: WidgetId) => {
    const def = WIDGET_REGISTRY[widgetId];
    if (!def) return;
    const idx = draftLayout.widgets.findIndex((w) => w.widgetId === widgetId);
    if (idx !== -1) {
      draftLayout.widgets[idx] = { ...draftLayout.widgets[idx], visible: true };
    } else {
      draftLayout.widgets.push({
        widgetId,
        order: draftLayout.widgets.length,
        size: def.defaultSize,
        visible: true,
        accentColor: def.defaultColor,
      });
    }
    draftLayout.updatedAt = new Date().toISOString();
  };

  const resetDraftToDefaults = () => {
    draftLayout = createDefaultPageLayout(savedLayout.pageId);
  };

  const hasUnsavedChanges = () => {
    if (!isEditing) return false;
    return JSON.stringify(draftLayout.widgets) !== JSON.stringify(savedLayout.widgets);
  };

  return {
    get savedLayout() { return savedLayout; },
    get draftLayout() { return draftLayout; },
    get isEditing() { return isEditing; },
    get drawerOpen() { return drawerOpen; },
    setDrawerOpen: (o: boolean) => { drawerOpen = o; },
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
  };
}

describe('Milestone 10.2 — Edit Mode & Widget Controls (Overview Pilot)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  // =========================================================================
  // 1. Edit Mode Lifecycle & Unsaved-Changes Handling
  // =========================================================================
  describe('Edit Mode Lifecycle & State Transitions', () => {
    it('enters edit mode with an exact snapshot of saved layout and zero initial unsaved changes', () => {
      const defaultLayout = createDefaultPageLayout('overview');
      savePageLayout('overview', defaultLayout);

      const harness = createEditHarness(defaultLayout);
      assert.strictEqual(harness.isEditing, false);

      harness.startEditing();
      assert.strictEqual(harness.isEditing, true);
      assert.strictEqual(harness.hasUnsavedChanges(), false);
      assert.deepStrictEqual(harness.draftLayout.widgets, harness.savedLayout.widgets);
    });

    it('detects unsaved changes when any widget property is mutated in draft', () => {
      const defaultLayout = createDefaultPageLayout('overview');
      const harness = createEditHarness(defaultLayout);

      harness.startEditing();
      assert.strictEqual(harness.hasUnsavedChanges(), false);

      // Mutate color on first widget
      harness.changeWidgetColor('overview-forecast-chart', 'pink');
      assert.strictEqual(harness.hasUnsavedChanges(), true);
    });

    it('cancelEditing completely discards draft changes and restores original saved layout', () => {
      const defaultLayout = createDefaultPageLayout('overview');
      savePageLayout('overview', defaultLayout);

      const harness = createEditHarness(defaultLayout);
      harness.startEditing();

      // Make changes
      harness.changeWidgetColor('overview-forecast-chart', 'rose');
      harness.changeWidgetSize('overview-forecast-chart', 'md');
      assert.strictEqual(harness.hasUnsavedChanges(), true);

      // Cancel
      harness.cancelEditing();
      assert.strictEqual(harness.isEditing, false);
      assert.strictEqual(harness.hasUnsavedChanges(), false);

      // Verify draft reverted to saved
      const chartWidget = harness.draftLayout.widgets.find((w) => w.widgetId === 'overview-forecast-chart');
      assert.strictEqual(chartWidget?.accentColor, 'blue');
      assert.strictEqual(chartWidget?.size, 'lg');
    });

    it('saveEditing validates and persists modified draft layout to localStorage', () => {
      const defaultLayout = createDefaultPageLayout('overview');
      savePageLayout('overview', defaultLayout);

      const harness = createEditHarness(defaultLayout);
      harness.startEditing();

      harness.changeWidgetColor('overview-kpi-summary', 'emerald');
      harness.changeWidgetSize('overview-forecast-chart', 'full');

      const saveRes = harness.saveEditing();
      assert.strictEqual(saveRes.success, true);
      assert.strictEqual(harness.isEditing, false);

      // Verify persisted in localStorage
      assert.ok(localStorage.getItem(CUSTOMIZATION_STORAGE_KEY));
      const reloaded = loadPageLayout('overview');
      const kpi = reloaded.widgets.find((w) => w.widgetId === 'overview-kpi-summary');
      const chart = reloaded.widgets.find((w) => w.widgetId === 'overview-forecast-chart');

      assert.strictEqual(kpi?.accentColor, 'emerald');
      assert.strictEqual(chart?.size, 'full');
    });
  });

  // =========================================================================
  // 2. Drag-and-Drop Reordering
  // =========================================================================
  describe('Widget Reordering Discipline', () => {
    it('moves a widget forward and normalizes contiguous order indices', () => {
      const defaultLayout = createDefaultPageLayout('overview');
      const harness = createEditHarness(defaultLayout);
      harness.startEditing();

      // Default order:
      // 0: overview-demo-disclaimer
      // 1: overview-kpi-summary
      // 2: overview-forecast-chart
      // 3: overview-rescue-recommendation
      // 4: overview-recent-activity

      // Move overview-demo-disclaimer down past overview-forecast-chart (swap to index 2)
      harness.reorderWidgets('overview-demo-disclaimer', 'overview-forecast-chart');

      const widgetIds = harness.draftLayout.widgets.map((w) => w.widgetId);
      assert.strictEqual(widgetIds[0], 'overview-kpi-summary');
      assert.strictEqual(widgetIds[1], 'overview-forecast-chart');
      assert.strictEqual(widgetIds[2], 'overview-demo-disclaimer');

      // Orders are contiguous: 0, 1, 2, 3, 4
      const orders = harness.draftLayout.widgets.map((w) => w.order);
      assert.deepStrictEqual(orders, [0, 1, 2, 3, 4]);
    });

    it('moves a widget backward towards the top', () => {
      const defaultLayout = createDefaultPageLayout('overview');
      const harness = createEditHarness(defaultLayout);
      harness.startEditing();

      // Move overview-recent-activity from end (index 4) to top (index 0)
      harness.reorderWidgets('overview-recent-activity', 'overview-demo-disclaimer');

      const widgetIds = harness.draftLayout.widgets.map((w) => w.widgetId);
      assert.strictEqual(widgetIds[0], 'overview-recent-activity');
      assert.strictEqual(widgetIds[1], 'overview-demo-disclaimer');
      assert.deepStrictEqual(harness.draftLayout.widgets.map((w) => w.order), [0, 1, 2, 3, 4]);
    });

    it('gracefully ignores no-op reorders when active equals over or IDs are invalid', () => {
      const defaultLayout = createDefaultPageLayout('overview');
      const harness = createEditHarness(defaultLayout);
      harness.startEditing();

      const initialOrder = harness.draftLayout.widgets.map((w) => w.widgetId);

      harness.reorderWidgets('overview-kpi-summary', 'overview-kpi-summary');
      assert.deepStrictEqual(harness.draftLayout.widgets.map((w) => w.widgetId), initialOrder);

      harness.reorderWidgets('non_existent', 'overview-kpi-summary');
      assert.deepStrictEqual(harness.draftLayout.widgets.map((w) => w.widgetId), initialOrder);
    });
  });

  // =========================================================================
  // 3. Widget Sizing & Allowed Sizes Constraint
  // =========================================================================
  describe('Widget Sizing & Allowed Size Constraints', () => {
    it('permits resizing to allowed sizes defined in the widget registry', () => {
      const defaultLayout = createDefaultPageLayout('overview');
      const harness = createEditHarness(defaultLayout);
      harness.startEditing();

      // overview-forecast-chart allowed sizes: ['full', 'lg', 'md']
      harness.changeWidgetSize('overview-forecast-chart', 'full');
      let chart = harness.draftLayout.widgets.find((w) => w.widgetId === 'overview-forecast-chart');
      assert.strictEqual(chart?.size, 'full');

      harness.changeWidgetSize('overview-forecast-chart', 'md');
      chart = harness.draftLayout.widgets.find((w) => w.widgetId === 'overview-forecast-chart');
      assert.strictEqual(chart?.size, 'md');
    });

    it('blocks attempting to resize a widget to a forbidden size', () => {
      const defaultLayout = createDefaultPageLayout('overview');
      const harness = createEditHarness(defaultLayout);
      harness.startEditing();

      // overview-demo-disclaimer allowed sizes: ['full'] only
      harness.changeWidgetSize('overview-demo-disclaimer', 'sm');
      const disclaimer = harness.draftLayout.widgets.find((w) => w.widgetId === 'overview-demo-disclaimer');
      assert.strictEqual(disclaimer?.size, 'full', 'Must reject forbidden size "sm"');

      // overview-forecast-chart forbidden size: 'sm'
      harness.changeWidgetSize('overview-forecast-chart', 'sm');
      const chart = harness.draftLayout.widgets.find((w) => w.widgetId === 'overview-forecast-chart');
      assert.strictEqual(chart?.size, 'lg', 'Must reject forbidden size "sm" for forecast chart');
    });
  });

  // =========================================================================
  // 4. Accent Color Customization
  // =========================================================================
  describe('Curated Color Customization', () => {
    it('applies selected curated color to widget in draft layout', () => {
      const defaultLayout = createDefaultPageLayout('overview');
      const harness = createEditHarness(defaultLayout);
      harness.startEditing();

      const testColors: MutedColorId[] = ['purple', 'amber', 'cyan', 'rose'];
      for (const clr of testColors) {
        harness.changeWidgetColor('overview-kpi-summary', clr);
        const kpi = harness.draftLayout.widgets.find((w) => w.widgetId === 'overview-kpi-summary');
        assert.strictEqual(kpi?.accentColor, clr);
      }
    });
  });

  // =========================================================================
  // 5. Widget Removal & Addition (Drawer)
  // =========================================================================
  describe('Widget Visibility & Add Drawer Operations', () => {
    it('hides optional widgets on remove', () => {
      const defaultLayout = createDefaultPageLayout('overview');
      const harness = createEditHarness(defaultLayout);
      harness.startEditing();

      // Remove optional recent activity widget
      harness.removeWidget('overview-recent-activity');
      const activity = harness.draftLayout.widgets.find((w) => w.widgetId === 'overview-recent-activity');
      assert.strictEqual(activity?.visible, false);
      assert.strictEqual(harness.hasUnsavedChanges(), true);
    });

    it('restores hidden widget via addWidget', () => {
      const defaultLayout = createDefaultPageLayout('overview');
      const harness = createEditHarness(defaultLayout);
      harness.startEditing();

      harness.removeWidget('overview-rescue-recommendation');
      assert.strictEqual(
        harness.draftLayout.widgets.find((w) => w.widgetId === 'overview-rescue-recommendation')?.visible,
        false
      );

      // Restore via addWidget
      harness.addWidget('overview-rescue-recommendation');
      assert.strictEqual(
        harness.draftLayout.widgets.find((w) => w.widgetId === 'overview-rescue-recommendation')?.visible,
        true
      );
    });
  });

  // =========================================================================
  // 6. Required & Safety-Critical Widget Protection
  // =========================================================================
  describe('Required Safety & Disclaimer Protection', () => {
    it('strictly prevents removing required demo disclaimers and notices', () => {
      const defaultLayout = createDefaultPageLayout('overview');
      const harness = createEditHarness(defaultLayout);
      harness.startEditing();

      assert.strictEqual(isWidgetRequired('overview-demo-disclaimer'), true);

      // Attempt to remove required disclaimer
      harness.removeWidget('overview-demo-disclaimer');
      const disclaimer = harness.draftLayout.widgets.find((w) => w.widgetId === 'overview-demo-disclaimer');

      assert.ok(disclaimer);
      assert.strictEqual(disclaimer.visible, true, 'Required demo disclaimer must remain visible: true');
    });

    it('storage validator forces visible: true even if draft maliciously attempts to hide required widget', () => {
      const malformedLayout: PageLayout = {
        pageId: 'overview',
        version: LAYOUT_SCHEMA_VERSION,
        updatedAt: new Date().toISOString(),
        widgets: [
          { widgetId: 'overview-demo-disclaimer', order: 0, size: 'full', visible: false },
        ],
      };

      const result = validatePageLayout(malformedLayout, 'overview');
      const disclaimer = result.data.widgets.find((w) => w.widgetId === 'overview-demo-disclaimer');
      assert.strictEqual(disclaimer?.visible, true, 'Schema validator must force visible: true on required widget');
    });
  });

  // =========================================================================
  // 7. Reset to Defaults Workflow
  // =========================================================================
  describe('Reset Draft to Defaults', () => {
    it('resets draft to canonical defaults while allowing user to cancel or save', () => {
      const defaultLayout = createDefaultPageLayout('overview');
      savePageLayout('overview', defaultLayout);

      const harness = createEditHarness(defaultLayout);
      harness.startEditing();

      // Scramble draft
      harness.reorderWidgets('overview-recent-activity', 'overview-demo-disclaimer');
      harness.changeWidgetColor('overview-forecast-chart', 'purple');
      harness.removeWidget('overview-kpi-summary');

      // Trigger reset
      harness.resetDraftToDefaults();

      const kpi = harness.draftLayout.widgets.find((w) => w.widgetId === 'overview-kpi-summary');
      const chart = harness.draftLayout.widgets.find((w) => w.widgetId === 'overview-forecast-chart');

      assert.strictEqual(kpi?.visible, true);
      assert.strictEqual(chart?.accentColor, 'blue');
      assert.strictEqual(harness.draftLayout.widgets[0].widgetId, 'overview-demo-disclaimer');

      // User decides to Cancel -> restores previously saved state
      harness.cancelEditing();
      assert.strictEqual(harness.isEditing, false);
      const reloaded = loadPageLayout('overview');
      assert.strictEqual(reloaded.widgets[0].widgetId, 'overview-demo-disclaimer');
    });
  });

  // =========================================================================
  // 8. Milestone 10.1 Storage Schema Compliance
  // =========================================================================
  describe('Milestone 10.1 Schema Interoperability', () => {
    it('saved layout matches root customization state schema perfectly', () => {
      const defaultLayout = createDefaultPageLayout('overview');
      const harness = createEditHarness(defaultLayout);

      harness.startEditing();
      harness.changeWidgetSize('overview-forecast-chart', 'full');
      harness.changeWidgetColor('overview-kpi-summary', 'slate');
      harness.saveEditing();

      const rootState = loadCustomizationState();
      const validation = validateCustomizationState(rootState);

      assert.strictEqual(validation.valid, true);
      assert.strictEqual(validation.errors.length, 0);
      assert.strictEqual(rootState.version, LAYOUT_SCHEMA_VERSION);

      const savedOverview = rootState.layouts.overview;
      assert.strictEqual(savedOverview.widgets.find((w) => w.widgetId === 'overview-forecast-chart')?.size, 'full');
      assert.strictEqual(savedOverview.widgets.find((w) => w.widgetId === 'overview-kpi-summary')?.accentColor, 'slate');
    });
  });
});
