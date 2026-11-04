import React from 'react';
import {
  SlidersHorizontal,
  Plus,
  RotateCcw,
  X,
  Save,
} from 'lucide-react';

export interface EditToolbarProps {
  isEditing: boolean;
  pageName: string;
  hasUnsavedChanges: boolean;
  onStartEditing: () => void;
  onCancelEditing: () => void;
  onSaveEditing: () => void;
  onOpenAddWidget: () => void;
  onResetDefaults: () => void;
}

export const EditToolbar: React.FC<EditToolbarProps> = ({
  isEditing,
  pageName,
  hasUnsavedChanges,
  onStartEditing,
  onCancelEditing,
  onSaveEditing,
  onOpenAddWidget,
  onResetDefaults,
}) => {
  if (!isEditing) {
    return (
      <button
        type="button"
        className="edit-dashboard-trigger-btn"
        onClick={onStartEditing}
        aria-label="Customize dashboard layout"
        data-testid="customize-dashboard-btn"
      >
        <SlidersHorizontal size={14} />
        <span>Customize Dashboard</span>
      </button>
    );
  }

  return (
    <div className="edit-toolbar-banner" role="toolbar" aria-label="Dashboard customization toolbar">
      <div className="edit-toolbar-left">
        <span className="edit-mode-pill">
          <SlidersHorizontal size={12} />
          <span>Edit Mode</span>
        </span>
        <span className="edit-mode-status-text">
          {pageName} Dashboard
          {hasUnsavedChanges && (
            <span style={{ marginLeft: 8, display: 'inline-flex', alignItems: 'center', gap: 5 }}>
              <span className="unsaved-dot" />
              <span style={{ color: '#fbbf24', fontWeight: 600, fontSize: 11 }}>Unsaved Edits</span>
            </span>
          )}
        </span>
      </div>

      <div className="edit-toolbar-actions">
        <button
          type="button"
          className="toolbar-btn toolbar-btn-secondary"
          onClick={onOpenAddWidget}
          title="Add or restore hidden widgets to this page"
          data-testid="add-widget-btn"
        >
          <Plus size={14} />
          <span>Add Widget</span>
        </button>

        <button
          type="button"
          className="toolbar-btn toolbar-btn-secondary"
          onClick={onResetDefaults}
          title="Reset this page to its default canonical layout"
          data-testid="reset-layout-btn"
        >
          <RotateCcw size={14} />
          <span>Reset Defaults</span>
        </button>

        <button
          type="button"
          className="toolbar-btn toolbar-btn-cancel"
          onClick={onCancelEditing}
          title="Cancel all changes and restore previous layout"
          data-testid="cancel-edit-btn"
        >
          <X size={14} />
          <span>Cancel</span>
        </button>

        <button
          type="button"
          className="toolbar-btn toolbar-btn-save"
          onClick={onSaveEditing}
          title="Save and persist layout changes"
          data-testid="save-layout-btn"
        >
          <Save size={14} />
          <span>Save Changes</span>
        </button>
      </div>
    </div>
  );
};
