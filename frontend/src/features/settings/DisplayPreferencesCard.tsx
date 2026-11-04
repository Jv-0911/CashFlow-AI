import React from 'react';
import { Palette, Moon, Sun, DollarSign, Info } from 'lucide-react';
import type { AppSettings, SupportedCurrency } from './settings-storage';
import { useTheme } from '../../context';

interface DisplayPreferencesCardProps {
  settings: AppSettings;
  errors: Record<string, string>;
  onChange: <K extends keyof AppSettings>(field: K, value: AppSettings[K]) => void;
}

export const DisplayPreferencesCard: React.FC<DisplayPreferencesCardProps> = ({
  settings,
  errors,
  onChange,
}) => {
  const { theme, setTheme } = useTheme();

  const handleThemeChange = (newTheme: 'dark' | 'light') => {
    setTheme(newTheme);
    onChange('theme', newTheme);
  };

  const currencyOptions: { code: SupportedCurrency; label: string; symbol: string }[] = [
    { code: 'USD', label: 'US Dollar', symbol: '$' },
    { code: 'EUR', label: 'Euro', symbol: '€' },
    { code: 'GBP', label: 'British Pound', symbol: '£' },
    { code: 'CAD', label: 'Canadian Dollar', symbol: 'CA$' },
  ];

  return (
    <div className="settings-section-card">
      <div className="section-header">
        <Palette size={18} className="text-accent" />
        <div>
          <h3 className="section-title">Display & Appearance Preferences</h3>
          <p className="section-desc">
            Customize visual themes and monetary notation across dashboard views.
          </p>
        </div>
      </div>

      <div className="settings-fields-grid">
        {/* Theme Preference */}
        <div className="settings-field">
          <label className="field-label">Interface Visual Theme</label>
          <div className="theme-toggle-group">
            <button
              type="button"
              className={`theme-option-btn ${theme === 'dark' ? 'active' : ''}`}
              onClick={() => handleThemeChange('dark')}
              aria-label="Set dark mode"
            >
              <Moon size={16} />
              <span>Dark Theme (Default)</span>
            </button>
            <button
              type="button"
              className={`theme-option-btn ${theme === 'light' ? 'active' : ''}`}
              onClick={() => handleThemeChange('light')}
              aria-label="Set light mode"
            >
              <Sun size={16} />
              <span>Light Theme</span>
            </button>
          </div>
          <span className="field-hint">
            Active theme: <strong>{theme === 'dark' ? 'Dark Mode (OLED Slate)' : 'Light Mode (Clean)'}</strong>
          </span>
        </div>

        {/* Currency Display Preference */}
        <div className="settings-field">
          <div className="field-label-row">
            <label htmlFor="settings-currency-select" className="field-label">
              <DollarSign size={13} style={{ display: 'inline', marginRight: 4 }} />
              Display Currency Format
            </label>
            <span className="field-badge font-mono">{settings.currency}</span>
          </div>
          <div className="currency-grid">
            {currencyOptions.map((curr) => (
              <button
                key={curr.code}
                type="button"
                className={`currency-option-card ${
                  settings.currency === curr.code ? 'active' : ''
                }`}
                onClick={() => onChange('currency', curr.code)}
              >
                <span className="currency-code">{curr.code}</span>
                <span className="currency-symbol">{curr.symbol}</span>
                <span className="currency-name">{curr.label}</span>
              </button>
            ))}
          </div>
          {errors.currency && (
            <span className="field-error-text">{errors.currency}</span>
          )}
        </div>
      </div>

      {/* FX Disclaimer */}
      <div className="settings-notice-box">
        <Info size={15} className="text-muted flex-shrink-0" />
        <div className="notice-copy">
          <strong>Display Formatting Only:</strong> Currency selection updates symbol formatting
          and presentation. It does not perform foreign exchange (FX) conversion or alter
          underlying integer-cent ledger amounts.
        </div>
      </div>
    </div>
  );
};
