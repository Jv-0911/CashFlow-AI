import React, { useState, useCallback, useMemo } from 'react';
import type {
  DashboardCustomizationState,
  DashboardPageId,
  PageLayout,
  WidgetId,
  WidgetLayoutItem,
} from './types.ts';
import {
  loadCustomizationState,
  savePageLayout as persistPageLayout,
  resetPageLayout as storageResetPageLayout,
  resetAllCustomizationState as storageResetAll,
} from './storage.ts';
import { createDefaultPageLayout } from './defaults.ts';
import { CustomizationContext, type CustomizationContextValue } from './customization-context.ts';

export interface CustomizationProviderProps {
  children: React.ReactNode;
}

export const CustomizationProvider: React.FC<CustomizationProviderProps> = ({ children }) => {
  const [state, setState] = useState<DashboardCustomizationState>(() => loadCustomizationState());

  const getPageLayout = useCallback(
    (pageId: DashboardPageId): PageLayout => {
      return state.layouts[pageId] || createDefaultPageLayout(pageId);
    },
    [state]
  );

  const updatePageLayout = useCallback(
    (pageId: DashboardPageId, layout: PageLayout) => {
      const result = persistPageLayout(pageId, layout);
      if (result.success) {
        setState((prev) => ({
          ...prev,
          updatedAt: new Date().toISOString(),
          layouts: {
            ...prev.layouts,
            [pageId]: result.layout,
          },
        }));
      }
      return { success: result.success, errors: result.errors };
    },
    []
  );

  const updateWidgetInPage = useCallback(
    (
      pageId: DashboardPageId,
      widgetId: WidgetId,
      updates: Partial<Pick<WidgetLayoutItem, 'size' | 'visible' | 'accentColor' | 'order'>>
    ) => {
      const currentLayout = state.layouts[pageId] || createDefaultPageLayout(pageId);
      const updatedWidgets = currentLayout.widgets.map((w) => {
        if (w.widgetId === widgetId) {
          return {
            ...w,
            ...updates,
          };
        }
        return w;
      });

      return updatePageLayout(pageId, {
        ...currentLayout,
        widgets: updatedWidgets,
      });
    },
    [state.layouts, updatePageLayout]
  );

  const resetPageLayout = useCallback((pageId: DashboardPageId) => {
    const defaultLayout = storageResetPageLayout(pageId);
    setState((prev) => ({
      ...prev,
      updatedAt: new Date().toISOString(),
      layouts: {
        ...prev.layouts,
        [pageId]: defaultLayout,
      },
    }));
  }, []);

  const resetAllPages = useCallback(() => {
    const freshDefaultState = storageResetAll();
    setState(freshDefaultState);
  }, []);

  const isCustomized = useCallback(
    (pageId: DashboardPageId): boolean => {
      const current = state.layouts[pageId];
      if (!current) return false;
      const canonical = createDefaultPageLayout(pageId);

      if (current.widgets.length !== canonical.widgets.length) return true;

      for (let i = 0; i < current.widgets.length; i++) {
        const c = current.widgets[i];
        const d = canonical.widgets[i];
        if (
          !d ||
          c.widgetId !== d.widgetId ||
          c.order !== d.order ||
          c.size !== d.size ||
          c.visible !== d.visible ||
          c.accentColor !== d.accentColor
        ) {
          return true;
        }
      }
      return false;
    },
    [state.layouts]
  );

  const contextValue = useMemo<CustomizationContextValue>(
    () => ({
      state,
      getPageLayout,
      updatePageLayout,
      updateWidgetInPage,
      resetPageLayout,
      resetAllPages,
      isCustomized,
    }),
    [
      state,
      getPageLayout,
      updatePageLayout,
      updateWidgetInPage,
      resetPageLayout,
      resetAllPages,
      isCustomized,
    ]
  );

  return (
    <CustomizationContext.Provider value={contextValue}>
      {children}
    </CustomizationContext.Provider>
  );
};
