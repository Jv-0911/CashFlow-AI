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
  DndContext,
  closestCenter,
  type DragEndEvent,
} from '@dnd-kit/core';
import { SortableContext, rectSortingStrategy } from '@dnd-kit/sortable';
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
import {
  useEditLayout,
  useCustomizationSensors,
  EditToolbar,
  WidgetWrapper,
  AddWidgetDrawer,
  type SettingsWidgetId,
} from '../customization';
import '../../styles/settings.css';
import '../../styles/customization.css';

export const SettingsPage: React.FC = () => {
  const [settings, setSettings] = useState<AppSettings>(loadSettings);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [feedback, setFeedback] = useState<{
    type: 'success' | 'error';
    message: string;
  } | null>(null);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState<boolean>(false);

  const { setTheme } = useTheme();

  // Milestone 10.3 Edit Mode & Customization
  const {
    isEditing,
    activeLayout,
    drawerOpen,
    setDrawerOpen,
    hasUnsavedChanges: hasUnsavedCustomizations,
    startEditing,
    cancelEditing,
    saveEditing,
    reorderWidgets,
    changeWidgetSize,
    changeWidgetColor,
    removeWidget,
    addWidget,
    resetDraftToDefaults,
  } = useEditLayout('settings');

  const sensors = useCustomizationSensors();

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      reorderWidgets(String(active.id), String(over.id));
    }
  };

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

  const renderWidgetContent = (widgetId: SettingsWidgetId) => {
    switch (widgetId) {
      case 'settings-business-profile':
        return (
          <BusinessProfileCard
            settings={settings}
            errors={errors}
            onChange={handleChange}
          />
        );

      case 'settings-policy-governance':
        return (
          <PolicyGovernanceCard
            settings={settings}
            errors={errors}
            onChange={handleChange}
          />
        );

      case 'settings-display-preferences':
        return (
          <DisplayPreferencesCard
            settings={settings}
            errors={errors}
            onChange={handleChange}
          />
        );

      default:
        return null;
    }
  };

  const visibleWidgets = activeLayout.widgets.filter((w) => w.visible);

  return (
    <div className="settings-page">
      {/* Page Header */}
      <div className="settings-header" style={{ marginBottom: isEditing ? 8 : 16 }}>
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
          {!isEditing && (
            <EditToolbar
              isEditing={false}
              pageName="Settings"
              hasUnsavedChanges={false}
              onStartEditing={startEditing}
              onCancelEditing={cancelEditing}
              onSaveEditing={saveEditing}
              onOpenAddWidget={() => setDrawerOpen(true)}
              onResetDefaults={resetDraftToDefaults}
            />
          )}
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

      {/* Edit Mode Sticky Banner */}
      {isEditing && (
        <EditToolbar
          isEditing={true}
          pageName="Settings"
          hasUnsavedChanges={hasUnsavedCustomizations}
          onStartEditing={startEditing}
          onCancelEditing={cancelEditing}
          onSaveEditing={saveEditing}
          onOpenAddWidget={() => setDrawerOpen(true)}
          onResetDefaults={resetDraftToDefaults}
        />
      )}

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
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={visibleWidgets.map((item) => item.widgetId)}
            strategy={rectSortingStrategy}
          >
            <div className="customization-dashboard-grid" data-editing={isEditing}>
              {visibleWidgets.map((item) => {
                const content = renderWidgetContent(item.widgetId as SettingsWidgetId);
                if (!content) return null;
                return (
                  <WidgetWrapper
                    key={item.widgetId}
                    item={item}
                    isEditing={isEditing}
                    onChangeSize={(size) => changeWidgetSize(item.widgetId, size)}
                    onChangeColor={(color) => changeWidgetColor(item.widgetId, color)}
                    onRemove={() => removeWidget(item.widgetId)}
                  >
                    {content}
                  </WidgetWrapper>
                );
              })}
            </div>
          </SortableContext>
        </DndContext>

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

      {/* Add Widget Drawer */}
      <AddWidgetDrawer
        isOpen={drawerOpen}
        pageId="settings"
        pageName="Settings"
        currentLayout={activeLayout}
        onClose={() => setDrawerOpen(false)}
        onAddWidget={(id) => addWidget(id)}
      />
    </div>
  );
};

export default SettingsPage;
