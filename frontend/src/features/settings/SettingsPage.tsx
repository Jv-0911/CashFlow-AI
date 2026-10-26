import React, { useState } from 'react';
import {
  Save,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  SlidersHorizontal,
  HardDrive,
} from 'lucide-react';
import {
  type AppSettings,
  loadSettings,
  saveSettings,
  resetSettings,
  validateSettings,
} from './settings-storage';
import { BusinessProfileCard } from './BusinessProfileCard';
import { PolicyGovernanceCard } from './PolicyGovernanceCard';
import { DisplayPreferencesCard } from './DisplayPreferencesCard';
import { useTheme } from '../../context';
import '../../styles/settings.css';

export const SettingsPage: React.FC = () => {
  const [settings, setSettings] = useState<AppSettings>(loadSettings);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [feedback, setFeedback] = useState<{
    type: 'success' | 'error';
    message: string;
  } | null>(null);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState<boolean>(false);

  const { setTheme } = useTheme();


  const handleChange = <K extends keyof AppSettings>(field: K, value: AppSettings[K]) => {
    setSettings((prev) => ({
      ...prev,
      [field]: value,
    }));
    setHasUnsavedChanges(true);

    // Clear error for field if fixed
    if (errors[field]) {
      setErrors((prev) => {
        const next = { ...prev };
        delete next[field];
        return next;
      });
    }
  };

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();

    const validation = validateSettings(settings);
    if (!validation.valid) {
      setErrors(validation.errors);
      setFeedback({
        type: 'error',
        message: 'Please resolve validation errors before saving.',
      });
      return;
    }

    const result = saveSettings(settings);
    if (result.success) {
      setErrors({});
      setHasUnsavedChanges(false);
      setFeedback({
        type: 'success',
        message: 'Preferences successfully saved to local browser storage.',
      });
      // Auto-clear message after 4s
      setTimeout(() => {
        setFeedback((curr) => (curr?.type === 'success' ? null : curr));
      }, 4000);
    } else {
      setErrors(result.errors || {});
      setFeedback({
        type: 'error',
        message: 'Failed to write settings to local storage.',
      });
    }
  };

  const handleReset = () => {
    if (
      window.confirm(
        'Are you sure you want to restore factory default settings? All custom local preferences will be overwritten.'
      )
    ) {
      const defaults = resetSettings();
      setSettings(defaults);
      setErrors({});
      setTheme(defaults.theme);
      setHasUnsavedChanges(false);
      setFeedback({
        type: 'success',
        message: 'Workspace settings reset to factory defaults.',
      });
      setTimeout(() => {
        setFeedback((curr) => (curr?.type === 'success' ? null : curr));
      }, 4000);
    }
  };

  return (
    <div className="settings-page">
      {/* Page Header */}
      <div className="settings-header">
        <div>
          <div className="settings-badge">
            <SlidersHorizontal size={13} />
            <span>Workspace Preferences</span>
          </div>
          <h1 className="settings-title">Settings & Configuration</h1>
          <p className="settings-subtitle">
            Configure local workspace metadata, liquidity policy thresholds, and display formatting.
          </p>
        </div>

        <div className="header-actions">
          <button
            type="button"
            className="btn-secondary"
            onClick={handleReset}
            title="Reset all settings to default values"
          >
            <RotateCcw size={15} />
            <span>Reset Defaults</span>
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={handleSave}
            disabled={!hasUnsavedChanges}
            title={hasUnsavedChanges ? 'Save changes' : 'No unsaved changes'}
          >
            <Save size={15} />
            <span>Save Preferences</span>
          </button>
        </div>
      </div>

      {/* Local Storage Clarification Banner */}
      <div className="storage-scope-banner">
        <HardDrive size={16} className="text-accent flex-shrink-0" />
        <div className="scope-copy">
          <strong>Local Browser Preferences:</strong> These settings are stored locally in your
          browser (Tenant: <code>demo_shop_001</code>). They do not persist to a remote backend server
          or modify server-side business rules.
        </div>
      </div>

      {/* Save Feedback Toast */}
      {feedback && (
        <div className={`feedback-alert ${feedback.type}`} role="status">
          {feedback.type === 'success' ? (
            <CheckCircle2 size={16} className="flex-shrink-0" />
          ) : (
            <AlertTriangle size={16} className="flex-shrink-0" />
          )}
          <span>{feedback.message}</span>
        </div>
      )}

      {/* Main Settings Form */}
      <form onSubmit={handleSave} className="settings-sections-list">
        <BusinessProfileCard
          settings={settings}
          errors={errors}
          onChange={handleChange}
        />

        <PolicyGovernanceCard
          settings={settings}
          errors={errors}
          onChange={handleChange}
        />

        <DisplayPreferencesCard
          settings={settings}
          errors={errors}
          onChange={handleChange}
        />

        {/* Bottom Action Footer for convenience */}
        <div className="settings-footer-bar">
          <div className="footer-status-text">
            {hasUnsavedChanges ? (
              <span className="unsaved-indicator">• You have unsaved changes</span>
            ) : (
              <span className="saved-indicator">✓ All changes saved locally</span>
            )}
          </div>
          <div className="footer-actions">
            <button
              type="button"
              className="btn-secondary"
              onClick={handleReset}
            >
              <RotateCcw size={15} />
              <span>Reset Defaults</span>
            </button>
            <button
              type="submit"
              className="btn-primary"
              disabled={!hasUnsavedChanges}
            >
              <Save size={15} />
              <span>Save Preferences</span>
            </button>
          </div>
        </div>
      </form>
    </div>
  );
};

export default SettingsPage;
