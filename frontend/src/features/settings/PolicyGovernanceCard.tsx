import React from 'react';
import { Shield, Bell, AlertCircle } from 'lucide-react';
import type { AppSettings } from './settings-storage';
import { formatCents } from '../../utils/currency';

interface PolicyGovernanceCardProps {
  settings: AppSettings;
  errors: Record<string, string>;
  onChange: <K extends keyof AppSettings>(field: K, value: AppSettings[K]) => void;
}

export const PolicyGovernanceCard: React.FC<PolicyGovernanceCardProps> = ({
  settings,
  errors,
  onChange,
}) => {
  const alertDayOptions = [3, 7, 14, 30];

  return (
    <div className="settings-section-card">
      <div className="section-header">
        <Shield size={18} className="text-warning" />
        <div>
          <h3 className="section-title">Liquidity Policy & Breach Alerts</h3>
          <p className="section-desc">
            Define baseline liquidity threshold targets and early warning horizons.
          </p>
        </div>
      </div>

      <div className="settings-fields-grid">
        {/* Safety Reserve Target */}
        <div className="settings-field">
          <div className="field-label-row">
            <label htmlFor="settings-safety-reserve" className="field-label">
              Safety Reserve Policy Target
            </label>
            <span className="field-badge font-mono text-warning">
              {formatCents(settings.safety_reserve_cents, settings.currency)}
            </span>
          </div>
          <div className="field-input-wrapper">
            <input
              id="settings-safety-reserve"
              type="number"
              min="0"
              step="100"
              className={`settings-input font-mono ${
                errors.safety_reserve_cents ? 'input-error' : ''
              }`}
              value={Math.round(settings.safety_reserve_cents / 100)}
              onChange={(e) => {
                const dollars = Math.max(0, parseInt(e.target.value, 10) || 0);
                onChange('safety_reserve_cents', dollars * 100);
              }}
              placeholder="1000"
            />
          </div>
          <span className="field-hint">
            Minimum required cash buffer. Projected balances below this trigger breach alerts.
          </span>
          {errors.safety_reserve_cents && (
            <span className="field-error-text">{errors.safety_reserve_cents}</span>
          )}
        </div>

        {/* Breach Alert Horizon */}
        <div className="settings-field">
          <div className="field-label-row">
            <label className="field-label">
              <Bell size={13} style={{ display: 'inline', marginRight: 4 }} />
              Breach Early Warning Horizon
            </label>
            <span className="field-badge font-mono">
              {settings.breach_alert_days} Days Ahead
            </span>
          </div>
          <div className="segmented-options-group">
            {alertDayOptions.map((days) => (
              <button
                key={days}
                type="button"
                className={`segment-btn ${settings.breach_alert_days === days ? 'active' : ''}`}
                onClick={() => onChange('breach_alert_days', days)}
              >
                {days}D
              </button>
            ))}
          </div>
          <span className="field-hint">
            Alert horizon: Trigger warning notifications when a breach is projected within this window.
          </span>
          {errors.breach_alert_days && (
            <span className="field-error-text">{errors.breach_alert_days}</span>
          )}
        </div>
      </div>

      <div className="policy-info-box">
        <AlertCircle size={14} className="text-muted flex-shrink-0" />
        <span className="policy-info-text">
          Safety reserve changes apply across Forecast, AI Rescue, and Scenario Simulation modules.
        </span>
      </div>
    </div>
  );
};
