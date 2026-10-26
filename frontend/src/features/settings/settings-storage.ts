export type SupportedCurrency = 'USD' | 'EUR' | 'GBP' | 'CAD';

export interface AppSettings {
  business_name: string;
  owner_name: string;
  business_email: string;
  safety_reserve_cents: number;
  currency: SupportedCurrency;
  breach_alert_days: number;
  theme: 'dark' | 'light';
}

export const SETTINGS_STORAGE_KEY = 'cashflow_ai_settings';

export const DEFAULT_SETTINGS: AppSettings = {
  business_name: 'NovaCraft Studio',
  owner_name: 'Alex Morgan',
  business_email: 'alex@novacraft.io',
  safety_reserve_cents: 100000, // $1,000.00 default reserve
  currency: 'USD',
  breach_alert_days: 7,
  theme: 'dark',
};

const SUPPORTED_CURRENCIES: SupportedCurrency[] = ['USD', 'EUR', 'GBP', 'CAD'];
const SUPPORTED_ALERT_DAYS = [3, 7, 14, 30];

/**
 * Validates settings values to ensure financial integrity.
 */
export function validateSettings(settings: AppSettings): {
  valid: boolean;
  errors: Record<string, string>;
} {
  const errors: Record<string, string> = {};

  if (!settings.business_name || settings.business_name.trim().length === 0) {
    errors.business_name = 'Business name is required.';
  }

  if (!settings.owner_name || settings.owner_name.trim().length === 0) {
    errors.owner_name = 'Owner name is required.';
  }

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!settings.business_email || !emailRegex.test(settings.business_email.trim())) {
    errors.business_email = 'Valid business email is required.';
  }

  if (
    typeof settings.safety_reserve_cents !== 'number' ||
    isNaN(settings.safety_reserve_cents) ||
    settings.safety_reserve_cents < 0
  ) {
    errors.safety_reserve_cents = 'Safety reserve must be a non-negative integer in cents.';
  }

  if (!SUPPORTED_CURRENCIES.includes(settings.currency)) {
    errors.currency = `Currency must be one of: ${SUPPORTED_CURRENCIES.join(', ')}`;
  }

  if (!SUPPORTED_ALERT_DAYS.includes(settings.breach_alert_days)) {
    errors.breach_alert_days = `Alert horizon must be one of: ${SUPPORTED_ALERT_DAYS.join(', ')} days.`;
  }

  return {
    valid: Object.keys(errors).length === 0,
    errors,
  };
}

/**
 * Loads preferences from localStorage, falling back to defaults.
 */
export function loadSettings(): AppSettings {
  try {
    const raw = localStorage.getItem(SETTINGS_STORAGE_KEY);
    if (!raw) return { ...DEFAULT_SETTINGS };

    const parsed = JSON.parse(raw);
    const candidate: AppSettings = {
      business_name:
        typeof parsed.business_name === 'string'
          ? parsed.business_name
          : DEFAULT_SETTINGS.business_name,
      owner_name:
        typeof parsed.owner_name === 'string'
          ? parsed.owner_name
          : DEFAULT_SETTINGS.owner_name,
      business_email:
        typeof parsed.business_email === 'string'
          ? parsed.business_email
          : DEFAULT_SETTINGS.business_email,
      safety_reserve_cents:
        typeof parsed.safety_reserve_cents === 'number' &&
        !isNaN(parsed.safety_reserve_cents) &&
        parsed.safety_reserve_cents >= 0
          ? Math.round(parsed.safety_reserve_cents)
          : DEFAULT_SETTINGS.safety_reserve_cents,
      currency: SUPPORTED_CURRENCIES.includes(parsed.currency)
        ? parsed.currency
        : DEFAULT_SETTINGS.currency,
      breach_alert_days: SUPPORTED_ALERT_DAYS.includes(parsed.breach_alert_days)
        ? parsed.breach_alert_days
        : DEFAULT_SETTINGS.breach_alert_days,
      theme: parsed.theme === 'light' ? 'light' : 'dark',
    };

    return candidate;
  } catch (err) {
    console.warn('Unable to read local settings from storage; using defaults:', err);
    return { ...DEFAULT_SETTINGS };
  }
}

/**
 * Persists validated preferences to localStorage.
 */
export function saveSettings(settings: AppSettings): {
  success: boolean;
  errors?: Record<string, string>;
} {
  const validation = validateSettings(settings);
  if (!validation.valid) {
    return { success: false, errors: validation.errors };
  }

  try {
    localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(settings));
    return { success: true };
  } catch (err) {
    console.error('Failed to write settings to local storage:', err);
    return {
      success: false,
      errors: { storage: 'Local browser storage is unavailable or quota exceeded.' },
    };
  }
}

/**
 * Resets preferences to factory defaults.
 */
export function resetSettings(): AppSettings {
  try {
    localStorage.removeItem(SETTINGS_STORAGE_KEY);
  } catch {
    // Ignore storage errors on removal
  }
  return { ...DEFAULT_SETTINGS };
}
