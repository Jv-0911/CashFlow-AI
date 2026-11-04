import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import {
  DEFAULT_SETTINGS,
  SETTINGS_STORAGE_KEY,
  validateSettings,
  loadSettings,
  saveSettings,
  resetSettings,
  type AppSettings,
} from '../settings-storage.ts';
import { formatCents, formatCentsCompact } from '../../../utils/currency.ts';

// Ensure localStorage mock is available in Node test runner
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

describe('Settings Suite — Validation, Persistence & Currency Formatting', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  describe('Settings Validation', () => {
    it('passes for valid default settings', () => {
      const validation = validateSettings(DEFAULT_SETTINGS);
      assert.strictEqual(validation.valid, true);
      assert.deepStrictEqual(validation.errors, {});
    });

    it('rejects empty or whitespace-only business name', () => {
      const invalid = { ...DEFAULT_SETTINGS, business_name: '   ' };
      const validation = validateSettings(invalid);
      assert.strictEqual(validation.valid, false);
      assert.ok(validation.errors.business_name);
    });

    it('rejects empty owner name', () => {
      const invalid = { ...DEFAULT_SETTINGS, owner_name: '' };
      const validation = validateSettings(invalid);
      assert.strictEqual(validation.valid, false);
      assert.ok(validation.errors.owner_name);
    });

    it('rejects malformed email addresses', () => {
      const invalid = { ...DEFAULT_SETTINGS, business_email: 'not-an-email' };
      const validation = validateSettings(invalid);
      assert.strictEqual(validation.valid, false);
      assert.ok(validation.errors.business_email);
    });

    it('rejects negative safety reserve target', () => {
      const invalid = { ...DEFAULT_SETTINGS, safety_reserve_cents: -50000 };
      const validation = validateSettings(invalid);
      assert.strictEqual(validation.valid, false);
      assert.ok(validation.errors.safety_reserve_cents);
    });

    it('rejects NaN or non-number safety reserve target', () => {
      const invalid = { ...DEFAULT_SETTINGS, safety_reserve_cents: NaN };
      const validation = validateSettings(invalid);
      assert.strictEqual(validation.valid, false);
      assert.ok(validation.errors.safety_reserve_cents);
    });

    it('rejects unsupported currencies', () => {
      const invalid = { ...DEFAULT_SETTINGS, currency: 'JPY' as any };
      const validation = validateSettings(invalid);
      assert.strictEqual(validation.valid, false);
      assert.ok(validation.errors.currency);
    });

    it('rejects unsupported breach alert days', () => {
      const invalid = { ...DEFAULT_SETTINGS, breach_alert_days: 45 };
      const validation = validateSettings(invalid);
      assert.strictEqual(validation.valid, false);
      assert.ok(validation.errors.breach_alert_days);
    });
  });

  describe('Storage Persistence & Fallback', () => {
    it('loads default settings when local storage is empty', () => {
      const loaded = loadSettings();
      assert.deepStrictEqual(loaded, DEFAULT_SETTINGS);
    });

    it('saves and reloads valid modified settings', () => {
      const custom: AppSettings = {
        business_name: 'Apex Robotics',
        owner_name: 'Dr. Clara Vance',
        business_email: 'clara@apexrobotics.co',
        safety_reserve_cents: 250000, // $2,500.00
        currency: 'EUR',
        breach_alert_days: 14,
        theme: 'light',
      };

      const result = saveSettings(custom);
      assert.strictEqual(result.success, true);

      const loaded = loadSettings();
      assert.deepStrictEqual(loaded, custom);
    });

    it('refuses to save invalid settings and preserves existing storage', () => {
      saveSettings(DEFAULT_SETTINGS);

      const invalid = { ...DEFAULT_SETTINGS, safety_reserve_cents: -100 };
      const result = saveSettings(invalid);

      assert.strictEqual(result.success, false);
      assert.ok(result.errors?.safety_reserve_cents);

      // Verify storage was untouched
      const loaded = loadSettings();
      assert.deepStrictEqual(loaded, DEFAULT_SETTINGS);
    });

    it('recovers gracefully from corrupted JSON in storage', () => {
      localStorage.setItem(SETTINGS_STORAGE_KEY, '{ invalid_json :::');

      const loaded = loadSettings();
      assert.deepStrictEqual(loaded, DEFAULT_SETTINGS);
    });

    it('resetSettings clears storage and returns default configuration', () => {
      const custom: AppSettings = {
        ...DEFAULT_SETTINGS,
        business_name: 'Custom Studio',
      };
      saveSettings(custom);
      assert.strictEqual(loadSettings().business_name, 'Custom Studio');

      const reset = resetSettings();
      assert.deepStrictEqual(reset, DEFAULT_SETTINGS);
      assert.strictEqual(loadSettings().business_name, DEFAULT_SETTINGS.business_name);
    });
  });

  describe('Currency Formatting Integration (Display-Only Discipline)', () => {
    it('formats USD integer cents correctly', () => {
      assert.strictEqual(formatCents(100000, 'USD'), '$1,000.00');
      assert.strictEqual(formatCentsCompact(100000, 'USD'), '$1,000');
    });

    it('formats EUR, GBP, CAD displays without altering stored integer cents', () => {
      const amountCents = 250050; // $2,500.50

      assert.strictEqual(formatCents(amountCents, 'EUR'), 'EUR 2,500.50');
      assert.strictEqual(formatCents(amountCents, 'GBP'), 'GBP 2,500.50');
      assert.strictEqual(formatCents(amountCents, 'CAD'), 'CAD 2,500.50');

      // Integer cents remain pristine
      assert.strictEqual(amountCents, 250050);
    });

    it('handles zero and negative amounts across currencies', () => {
      assert.strictEqual(formatCents(0, 'USD'), '$0.00');
      assert.strictEqual(formatCents(-50000, 'USD'), '-$500.00');
      assert.strictEqual(formatCents(-50000, 'EUR'), '-EUR 500.00');
    });
  });
});
