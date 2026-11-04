import React from 'react';
import { Building2, User, Mail, ShieldAlert } from 'lucide-react';
import type { AppSettings } from './settings-storage';

interface BusinessProfileCardProps {
  settings: AppSettings;
  errors: Record<string, string>;
  onChange: <K extends keyof AppSettings>(field: K, value: AppSettings[K]) => void;
}

export const BusinessProfileCard: React.FC<BusinessProfileCardProps> = ({
  settings,
  errors,
  onChange,
}) => {
  return (
    <div className="settings-section-card">
      <div className="section-header">
        <Building2 size={18} className="text-accent" />
        <div>
          <h3 className="section-title">Business Profile & Workspace Identity</h3>
          <p className="section-desc">
            Primary organization identity details used for reports and notifications.
          </p>
        </div>
      </div>

      <div className="settings-fields-grid">
        {/* Business Name */}
        <div className="settings-field">
          <label htmlFor="settings-business-name" className="field-label">
            Organization / Business Name
          </label>
          <div className="field-input-wrapper">
            <input
              id="settings-business-name"
              type="text"
              className={`settings-input ${errors.business_name ? 'input-error' : ''}`}
              value={settings.business_name}
              onChange={(e) => onChange('business_name', e.target.value)}
              placeholder="e.g. Acme Corporation"
            />
          </div>
          {errors.business_name && (
            <span className="field-error-text">{errors.business_name}</span>
          )}
        </div>

        {/* Owner / Contact Name */}
        <div className="settings-field">
          <label htmlFor="settings-owner-name" className="field-label">
            Primary Contact / Financial Lead
          </label>
          <div className="field-input-wrapper">
            <User size={14} className="input-icon-left" />
            <input
              id="settings-owner-name"
              type="text"
              className={`settings-input with-icon ${errors.owner_name ? 'input-error' : ''}`}
              value={settings.owner_name}
              onChange={(e) => onChange('owner_name', e.target.value)}
              placeholder="e.g. Jane Doe"
            />
          </div>
          {errors.owner_name && (
            <span className="field-error-text">{errors.owner_name}</span>
          )}
        </div>

        {/* Business Email */}
        <div className="settings-field full-width">
          <label htmlFor="settings-business-email" className="field-label">
            Notification & Treasury Email
          </label>
          <div className="field-input-wrapper">
            <Mail size={14} className="input-icon-left" />
            <input
              id="settings-business-email"
              type="email"
              className={`settings-input with-icon ${errors.business_email ? 'input-error' : ''}`}
              value={settings.business_email}
              onChange={(e) => onChange('business_email', e.target.value)}
              placeholder="treasury@example.com"
            />
          </div>
          {errors.business_email && (
            <span className="field-error-text">{errors.business_email}</span>
          )}
        </div>
      </div>

      {/* Tenancy & Storage Clarification Notice */}
      <div className="settings-notice-box">
        <ShieldAlert size={15} className="text-muted flex-shrink-0" />
        <div className="notice-copy">
          <strong>Local Browser Preferences:</strong> These settings configure your current browser
          workspace display (Tenant: <code>demo_shop_001</code>). They do not imply remote server-side
          persistence or change backend multi-tenant permissions.
        </div>
      </div>
    </div>
  );
};
