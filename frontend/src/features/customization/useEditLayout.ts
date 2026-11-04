import { useState, useCallback, useMemo } from 'react';
import type {
  DashboardPageId,
  MutedColorId,
  PageLayout,
  WidgetId,
  WidgetLayoutItem,
  WidgetSize,
} from './types.ts';
import { useCustomization } from './useCustomization.ts';
import { WIDGET_REGISTRY } from './widget-registry.ts';
import { createDefaultPageLayout } from './defaults.ts';

/**
 * Custom hook to encapsulate all Edit Mode state, draft mutations,
 * unsaved-changes tracking, and cancellation/persistence workflows.
 */
export function useEditLayout(pageId: DashboardPageId) {
  const { getPageLayout, updatePageLayout } = useCustomization();
  const savedLayout = getPageLayout(pageId);

  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [draftLayout, setDraftLayout] = useState<PageLayout>(savedLayout);
  const [drawerOpen, setDrawerOpen] = useState<boolean>(false);

  // Synchronize draft when not editing
  const activeLayout = isEditing ? draftLayout : savedLayout;

  const startEditing = useCallback(() => {
    // Clone saved layout into draft state
    setDraftLayout(JSON.parse(JSON.stringify(savedLayout)));
    setIsEditing(true);
    setDrawerOpen(false);
  }, [savedLayout]);

  const cancelEditing = useCallback(() => {
    // Revert draft to saved layout
    setDraftLayout(JSON.parse(JSON.stringify(savedLayout)));
    setIsEditing(false);
    setDrawerOpen(false);
  }, [savedLayout]);

  const saveEditing = useCallback((): { success: boolean; errors?: string[] } => {
    const result = updatePageLayout(pageId, draftLayout);
    if (result.success) {
      setIsEditing(false);
      setDrawerOpen(false);
    }
    return result;
  }, [pageId, draftLayout, updatePageLayout]);

  // Reorder widgets (drag-and-drop handler)
  const reorderWidgets = useCallback((activeId: string, overId: string) => {
    if (activeId === overId) return;

    setDraftLayout((prev) => {
      const oldIndex = prev.widgets.findIndex((w) => w.widgetId === activeId);
      const newIndex = prev.widgets.findIndex((w) => w.widgetId === overId);

      if (oldIndex === -1 || newIndex === -1) return prev;

      const items = [...prev.widgets];
      const [movedItem] = items.splice(oldIndex, 1);
      items.splice(newIndex, 0, movedItem);

      // Re-index contiguous order numbers: 0, 1, 2, ...
      const reindexed = items.map((item, index) => ({
        ...item,
        order: index,
      }));

      return {
        ...prev,
        updatedAt: new Date().toISOString(),
        widgets: reindexed,
      };
    });
  }, []);

  // Change widget size
  const changeWidgetSize = useCallback((widgetId: WidgetId, size: WidgetSize) => {
    const def = WIDGET_REGISTRY[widgetId];
    if (!def || !def.allowedSizes.includes(size)) return;

    setDraftLayout((prev) => ({
      ...prev,
      updatedAt: new Date().toISOString(),
      widgets: prev.widgets.map((w) =>
        w.widgetId === widgetId ? { ...w, size } : w
      ),
    }));
  }, []);

  // Change widget accent color
  const changeWidgetColor = useCallback((widgetId: WidgetId, color: MutedColorId) => {
    setDraftLayout((prev) => ({
      ...prev,
      updatedAt: new Date().toISOString(),
      widgets: prev.widgets.map((w) =>
        w.widgetId === widgetId ? { ...w, accentColor: color } : w
      ),
    }));
  }, []);

  // Remove / hide widget (enforcing required safety check)
  const removeWidget = useCallback((widgetId: WidgetId) => {
    const def = WIDGET_REGISTRY[widgetId];
    if (def?.isRequired) {
      // Safety critical / required widgets cannot be removed
      return;
    }

    setDraftLayout((prev) => ({
      ...prev,
      updatedAt: new Date().toISOString(),
      widgets: prev.widgets.map((w) =>
        w.widgetId === widgetId ? { ...w, visible: false } : w
      ),
    }));
  }, []);

  // Add / restore widget to visible state
  const addWidget = useCallback(
    (widgetId: WidgetId) => {
      const def = WIDGET_REGISTRY[widgetId];
      if (!def) return;

      setDraftLayout((prev) => {
        const existingIdx = prev.widgets.findIndex((w) => w.widgetId === widgetId);
        if (existingIdx !== -1) {
          // Re-enable existing widget
          const nextWidgets = [...prev.widgets];
          nextWidgets[existingIdx] = {
            ...nextWidgets[existingIdx],
            visible: true,
          };
          return {
            ...prev,
            updatedAt: new Date().toISOString(),
            widgets: nextWidgets,
          };
        } else {
          // Append new widget
          const newItem: WidgetLayoutItem = {
            widgetId,
            order: prev.widgets.length,
            size: def.defaultSize,
            visible: true,
            accentColor: def.defaultColor,
          };
          return {
            ...prev,
            updatedAt: new Date().toISOString(),
            widgets: [...prev.widgets, newItem],
          };
        }
      });
    },
    []
  );

  // Reset draft to factory defaults
  const resetDraftToDefaults = useCallback(() => {
    const defaults = createDefaultPageLayout(pageId);
    setDraftLayout(defaults);
  }, [pageId]);

  // Determine whether draft differs from savedLayout
  const hasUnsavedChanges = useMemo(() => {
    if (!isEditing) return false;
    return JSON.stringify(draftLayout.widgets) !== JSON.stringify(savedLayout.widgets);
  }, [isEditing, draftLayout.widgets, savedLayout.widgets]);

  return {
    isEditing,
    activeLayout,
    draftLayout,
    savedLayout,
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
  };
}
