import React, { useEffect } from 'react';
import {
  X,
  Plus,
  Check,
  Lock,
  ShieldAlert,
} from 'lucide-react';
import type {
  DashboardPageId,
  PageLayout,
  WidgetId,
} from '../types.ts';
import { getWidgetsForPage } from '../widget-registry.ts';

export interface AddWidgetDrawerProps {
  isOpen: boolean;
  pageId: DashboardPageId;
  pageName: string;
  currentLayout: PageLayout;
  onAddWidget: (widgetId: WidgetId) => void;
  onClose: () => void;
}

export const AddWidgetDrawer: React.FC<AddWidgetDrawerProps> = ({
  isOpen,
  pageId,
  pageName,
  currentLayout,
  onAddWidget,
  onClose,
}) => {
  // Close drawer on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const compatibleWidgets = getWidgetsForPage(pageId);

  // Set of currently visible widget IDs in the layout
  const visibleWidgetIds = new Set(
    currentLayout.widgets.filter((w) => w.visible).map((w) => w.widgetId)
  );

  return (
    <>
      {/* Backdrop */}
      <div
        className="add-widget-drawer-backdrop"
        onClick={onClose}
        aria-hidden="true"
        data-testid="add-widget-drawer-backdrop"
      />

      {/* Slide-over Drawer Panel */}
      <aside
        className="add-widget-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="drawer-heading"
        data-testid="add-widget-drawer-panel"
      >
        <div className="drawer-header">
          <div className="drawer-title-group">
            <h3 id="drawer-heading">Widget Library</h3>
            <p>Modular components for {pageName}</p>
          </div>
          <button
            type="button"
            className="drawer-close-btn"
            onClick={onClose}
            aria-label="Close widget library drawer"
            data-testid="drawer-close-btn"
          >
            <X size={18} />
          </button>
        </div>

        <div className="drawer-body">
          {compatibleWidgets.map((widget) => {
            const isVisible = visibleWidgetIds.has(widget.id);

            return (
              <div
                key={widget.id}
                className="drawer-widget-card"
                data-testid={`drawer-card-${widget.id}`}
              >
                <div className="drawer-widget-card-header">
                  <span className="drawer-widget-title">{widget.title}</span>
                  <div style={{ display: 'flex', gap: 6 }}>
                    {widget.isRequired && (
                      <span className="widget-safety-badge required">
                        <Lock size={10} />
                        <span>Required</span>
                      </span>
                    )}
                    {!widget.isRequired && widget.isSafetyCritical && (
                      <span className="widget-safety-badge critical">
                        <ShieldAlert size={10} />
                        <span>Safety Critical</span>
                      </span>
                    )}
                  </div>
                </div>

                <p className="drawer-widget-desc">{widget.description}</p>

                <div className="drawer-widget-footer">
                  <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                    Sizes: {widget.allowedSizes.join(', ').toUpperCase()}
                  </span>

                  {isVisible ? (
                    <span className="drawer-placed-pill" data-testid={`drawer-status-${widget.id}`}>
                      <Check size={12} />
                      <span>Active on Page</span>
                    </span>
                  ) : (
                    <button
                      type="button"
                      className="drawer-add-btn"
                      onClick={() => onAddWidget(widget.id)}
                      data-testid={`drawer-add-btn-${widget.id}`}
                    >
                      <Plus size={12} />
                      <span>Add to Page</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </aside>
    </>
  );
};
