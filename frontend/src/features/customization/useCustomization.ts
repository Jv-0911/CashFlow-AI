import { useContext } from 'react';
import { CustomizationContext, type CustomizationContextValue } from './customization-context.ts';
import type { DashboardPageId, PageLayout } from './types.ts';

export function useCustomization(): CustomizationContextValue {
  const context = useContext(CustomizationContext);
  if (!context) {
    throw new Error('useCustomization must be used within a <CustomizationProvider>');
  }
  return context;
}

/**
 * Convenience hook to access and manage layout customization for a specific page.
 */
export function usePageCustomization(pageId: DashboardPageId): {
  layout: PageLayout;
  updateLayout: (layout: PageLayout) => { success: boolean; errors?: string[] };
  resetLayout: () => void;
  isCustomized: boolean;
} {
  const { getPageLayout, updatePageLayout, resetPageLayout, isCustomized } = useCustomization();

  return {
    layout: getPageLayout(pageId),
    updateLayout: (layout: PageLayout) => updatePageLayout(pageId, layout),
    resetLayout: () => resetPageLayout(pageId),
    isCustomized: isCustomized(pageId),
  };
}
