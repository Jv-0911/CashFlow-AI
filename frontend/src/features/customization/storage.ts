import type {
  CustomizationValidationResult,
  DashboardCustomizationState,
  DashboardPageId,
  MutedColorId,
  PageLayout,
  WidgetId,
  WidgetLayoutItem,
  WidgetSize,
} from './types.ts';
import {
  createDefaultCustomizationState,
  createDefaultPageLayout,
  LAYOUT_SCHEMA_VERSION,
} from './defaults.ts';
import { isValidMutedColor } from './palette.ts';
import { getWidgetsForPage, isWidgetCompatible, WIDGET_REGISTRY } from './widget-registry.ts';

export const CUSTOMIZATION_STORAGE_KEY = 'cashflow_ai_page_layouts';

export const SUPPORTED_PAGES: readonly DashboardPageId[] = [
  'overview',
  'forecast',
  'rescue',
  'scenarios',
  'payments',
  'analytics',
  'settings',
] as const;

export function isSupportedPageId(pageId: unknown): pageId is DashboardPageId {
  return typeof pageId === 'string' && (SUPPORTED_PAGES as readonly string[]).includes(pageId);
}

/**
 * Validates and normalizes an individual widget layout item.
 */
export function validateWidgetLayoutItem(
  item: unknown,
  pageId: DashboardPageId,
  fallbackOrder: number
): { valid: boolean; item: WidgetLayoutItem | null; error?: string } {
  if (!item || typeof item !== 'object') {
    return { valid: false, item: null, error: 'Widget layout item must be an object.' };
  }

  const raw = item as Record<string, unknown>;
  const widgetId = raw.widgetId as WidgetId;

  if (typeof widgetId !== 'string' || !WIDGET_REGISTRY[widgetId]) {
    return { valid: false, item: null, error: `Unknown widget ID: ${String(widgetId)}.` };
  }

  if (!isWidgetCompatible(widgetId, pageId)) {
    return {
      valid: false,
      item: null,
      error: `Widget ${widgetId} is not compatible with page "${pageId}".`,
    };
  }

  const def = WIDGET_REGISTRY[widgetId];

  // Validate size
  let size: WidgetSize = def.defaultSize;
  if (typeof raw.size === 'string' && (def.allowedSizes as readonly string[]).includes(raw.size)) {
    size = raw.size as WidgetSize;
  }

  // Validate visibility — SAFETY CRITICAL RULE:
  // Required widgets (e.g. demo disclaimers, breach alerts, backend notices) MUST NEVER be hidden.
  let visible = typeof raw.visible === 'boolean' ? raw.visible : true;
  if (def.isRequired) {
    visible = true;
  }

  // Validate accent color
  let accentColor: MutedColorId = def.defaultColor;
  if (isValidMutedColor(raw.accentColor)) {
    accentColor = raw.accentColor;
  }

  // Validate order index
  let order = fallbackOrder;
  if (typeof raw.order === 'number' && !isNaN(raw.order) && raw.order >= 0) {
    order = Math.floor(raw.order);
  }

  return {
    valid: true,
    item: {
      widgetId,
      order,
      size,
      visible,
      accentColor,
    },
  };
}

/**
 * Validates and normalizes a full PageLayout object.
 *
 * Enforces:
 *  - Compatible widget IDs only
 *  - Duplicate widget elimination
 *  - Mandatory re-insertion of required/safety widgets
 *  - Ordered contiguous layout indices (0, 1, 2, ...)
 *  - Protection of required alerts and disclaimers (visible: true)
 */
export function validatePageLayout(
  candidate: unknown,
  pageId: DashboardPageId
): CustomizationValidationResult<PageLayout> {
  const errors: string[] = [];
  const defaultLayout = createDefaultPageLayout(pageId);

  if (!candidate || typeof candidate !== 'object') {
    errors.push(`Layout for page "${pageId}" is not a valid object; using defaults.`);
    return { valid: false, data: defaultLayout, errors };
  }

  const raw = candidate as Record<string, unknown>;

  if (raw.pageId !== pageId) {
    errors.push(`Layout pageId mismatch (expected "${pageId}", received "${String(raw.pageId)}").`);
  }

  if (raw.version !== LAYOUT_SCHEMA_VERSION) {
    errors.push(
      `Layout schema version ${String(raw.version)} does not match supported version ${LAYOUT_SCHEMA_VERSION}.`
    );
  }

  if (!Array.isArray(raw.widgets)) {
    errors.push(`Widgets property for page "${pageId}" is not an array; using default widgets.`);
    return { valid: false, data: defaultLayout, errors };
  }

  const seenWidgetIds = new Set<WidgetId>();
  const validItems: WidgetLayoutItem[] = [];

  for (let i = 0; i < raw.widgets.length; i++) {
    const rawItem = raw.widgets[i];
    const validation = validateWidgetLayoutItem(rawItem, pageId, i);

    if (!validation.valid || !validation.item) {
      if (validation.error) errors.push(validation.error);
      continue;
    }

    // Eliminate duplicates (keep first occurrence)
    if (seenWidgetIds.has(validation.item.widgetId)) {
      errors.push(`Duplicate widget ID "${validation.item.widgetId}" removed from page "${pageId}".`);
      continue;
    }

    seenWidgetIds.add(validation.item.widgetId);
    validItems.push(validation.item);
  }

  // Ensure all registered widgets for this page exist in layout.
  // Missing required or optional widgets are reinstated from registry defaults.
  const registeredWidgets = getWidgetsForPage(pageId);
  for (const def of registeredWidgets) {
    if (!seenWidgetIds.has(def.id)) {
      if (def.isRequired) {
        errors.push(`Required safety widget "${def.id}" was missing; re-inserted into layout.`);
      }
      validItems.push({
        widgetId: def.id,
        order: validItems.length,
        size: def.defaultSize,
        visible: true,
        accentColor: def.defaultColor,
      });
      seenWidgetIds.add(def.id);
    }
  }

  // Sort by order ascending and normalize to contiguous indices: 0, 1, 2, ...
  validItems.sort((a, b) => a.order - b.order);
  const normalizedWidgets = validItems.map((item, index) => ({
    ...item,
    order: index,
  }));

  const normalizedLayout: PageLayout = {
    pageId,
    version: LAYOUT_SCHEMA_VERSION,
    updatedAt:
      typeof raw.updatedAt === 'string' && raw.updatedAt.trim().length > 0
        ? raw.updatedAt
        : new Date().toISOString(),
    widgets: normalizedWidgets,
  };

  return {
    valid: errors.length === 0,
    data: normalizedLayout,
    errors,
  };
}

/**
 * Validates the full root Customization state spanning all 7 pages.
 */
export function validateCustomizationState(
  candidate: unknown
): CustomizationValidationResult<DashboardCustomizationState> {
  const errors: string[] = [];
  const defaultState = createDefaultCustomizationState();

  if (!candidate || typeof candidate !== 'object') {
    errors.push('Customization root state is not a valid object; falling back to default layouts.');
    return { valid: false, data: defaultState, errors };
  }

  const raw = candidate as Record<string, unknown>;

  if (raw.version !== LAYOUT_SCHEMA_VERSION) {
    errors.push(
      `Customization root schema version ${String(raw.version)} does not match current version ${LAYOUT_SCHEMA_VERSION}; using defaults.`
    );
    return { valid: false, data: defaultState, errors };
  }

  const rawLayouts = (raw.layouts && typeof raw.layouts === 'object'
    ? raw.layouts
    : {}) as Record<string, unknown>;

  const validatedLayouts: Record<DashboardPageId, PageLayout> = { ...defaultState.layouts };

  for (const pageId of SUPPORTED_PAGES) {
    const pageCandidate = rawLayouts[pageId];
    const pageResult = validatePageLayout(pageCandidate, pageId);
    if (!pageResult.valid) {
      errors.push(...pageResult.errors);
    }
    validatedLayouts[pageId] = pageResult.data;
  }

  const validatedState: DashboardCustomizationState = {
    version: LAYOUT_SCHEMA_VERSION,
    updatedAt:
      typeof raw.updatedAt === 'string' && raw.updatedAt.trim().length > 0
        ? raw.updatedAt
        : new Date().toISOString(),
    layouts: validatedLayouts,
  };

  return {
    valid: errors.length === 0,
    data: validatedState,
    errors,
  };
}

/**
 * Loads the complete customization state from localStorage, falling back safely
 * to defaults if corrupted or uninitialized.
 */
export function loadCustomizationState(): DashboardCustomizationState {
  try {
    if (typeof localStorage === 'undefined') {
      return createDefaultCustomizationState();
    }

    const raw = localStorage.getItem(CUSTOMIZATION_STORAGE_KEY);
    if (!raw) {
      return createDefaultCustomizationState();
    }

    const parsed = JSON.parse(raw);
    const validation = validateCustomizationState(parsed);
    return validation.data;
  } catch (err) {
    console.warn('Unable to load customization state from localStorage; falling back to defaults:', err);
    return createDefaultCustomizationState();
  }
}

/**
 * Loads the saved PageLayout for a specific dashboard page with full isolation.
 */
export function loadPageLayout(pageId: DashboardPageId): PageLayout {
  const state = loadCustomizationState();
  return state.layouts[pageId] || createDefaultPageLayout(pageId);
}

/**
 * Saves a page layout into localStorage with strict page isolation and schema validation.
 * Updating one page will NOT mutate or corrupt layouts of other dashboard pages.
 */
export function savePageLayout(
  pageId: DashboardPageId,
  layout: PageLayout
): { success: boolean; layout: PageLayout; errors?: string[] } {
  try {
    const currentState = loadCustomizationState();
    const validation = validatePageLayout(layout, pageId);

    currentState.layouts[pageId] = validation.data;
    currentState.updatedAt = new Date().toISOString();

    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(CUSTOMIZATION_STORAGE_KEY, JSON.stringify(currentState));
    }

    return {
      success: true,
      layout: validation.data,
      errors: validation.errors.length > 0 ? validation.errors : undefined,
    };
  } catch (err) {
    console.error(`Failed to save layout for page "${pageId}":`, err);
    return {
      success: false,
      layout: validatePageLayout(layout, pageId).data,
      errors: [err instanceof Error ? err.message : 'Storage write failed or quota exceeded.'],
    };
  }
}

/**
 * Persists the entire customization state across all 7 pages.
 */
export function saveAllCustomizationState(
  state: DashboardCustomizationState
): { success: boolean; state: DashboardCustomizationState; errors?: string[] } {
  try {
    const validation = validateCustomizationState(state);
    const validatedState = validation.data;
    validatedState.updatedAt = new Date().toISOString();

    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(CUSTOMIZATION_STORAGE_KEY, JSON.stringify(validatedState));
    }

    return {
      success: true,
      state: validatedState,
      errors: validation.errors.length > 0 ? validation.errors : undefined,
    };
  } catch (err) {
    console.error('Failed to save root customization state:', err);
    return {
      success: false,
      state: validateCustomizationState(state).data,
      errors: [err instanceof Error ? err.message : 'Storage write failed.'],
    };
  }
}

/**
 * Resets a single page's layout to canonical factory defaults, preserving
 * custom layouts on all other dashboard pages.
 */
export function resetPageLayout(pageId: DashboardPageId): PageLayout {
  try {
    const state = loadCustomizationState();
    const defaultLayout = createDefaultPageLayout(pageId);
    state.layouts[pageId] = defaultLayout;
    state.updatedAt = new Date().toISOString();

    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(CUSTOMIZATION_STORAGE_KEY, JSON.stringify(state));
    }

    return defaultLayout;
  } catch (err) {
    console.warn(`Error during reset of page "${pageId}":`, err);
    return createDefaultPageLayout(pageId);
  }
}

/**
 * Resets all dashboard pages to factory defaults and removes stored customization data.
 */
export function resetAllCustomizationState(): DashboardCustomizationState {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem(CUSTOMIZATION_STORAGE_KEY);
    }
  } catch (err) {
    console.warn('Error clearing customization storage key:', err);
  }
  return createDefaultCustomizationState();
}
