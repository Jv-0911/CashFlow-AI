import { createContext } from 'react';
import type {
  DashboardCustomizationState,
  DashboardPageId,
  PageLayout,
  WidgetId,
  WidgetLayoutItem,
} from './types.ts';

export interface CustomizationContextValue {
  state: DashboardCustomizationState;
  getPageLayout: (pageId: DashboardPageId) => PageLayout;
  updatePageLayout: (
    pageId: DashboardPageId,
    layout: PageLayout
  ) => { success: boolean; errors?: string[] };
  updateWidgetInPage: (
    pageId: DashboardPageId,
    widgetId: WidgetId,
    updates: Partial<Pick<WidgetLayoutItem, 'size' | 'visible' | 'accentColor' | 'order'>>
  ) => { success: boolean; errors?: string[] };
  resetPageLayout: (pageId: DashboardPageId) => void;
  resetAllPages: () => void;
  isCustomized: (pageId: DashboardPageId) => boolean;
}

export const CustomizationContext = createContext<CustomizationContextValue | null>(null);
