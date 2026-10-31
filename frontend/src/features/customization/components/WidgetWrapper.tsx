import React from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import {
  GripVertical,
  Lock,
  ShieldAlert,
  EyeOff,
} from 'lucide-react';
import type {
  MutedColorId,
  WidgetLayoutItem,
  WidgetSize,
} from '../types.ts';
import { WIDGET_REGISTRY } from '../widget-registry.ts';
import { ColorPickerPopover } from './ColorPickerPopover.tsx';

export interface WidgetWrapperProps {
  item: WidgetLayoutItem;
  isEditing: boolean;
  onChangeSize: (size: WidgetSize) => void;
  onChangeColor: (color: MutedColorId) => void;
  onRemove: () => void;
  children: React.ReactNode;
}

const ALL_SIZES: readonly WidgetSize[] = ['sm', 'md', 'lg', 'full'] as const;

export const WidgetWrapper: React.FC<WidgetWrapperProps> = ({
  item,
  isEditing,
  onChangeSize,
  onChangeColor,
  onRemove,
  children,
}) => {
  const def = WIDGET_REGISTRY[item.widgetId];

  // DND-Kit Sortable binding - strictly disabled outside edit mode
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: item.widgetId,
    disabled: !isEditing,
  });

  const sortableStyle: React.CSSProperties = {
    transform: CSS.Translate.toString(transform),
    transition,
    zIndex: isDragging ? 100 : undefined,
  };

  const sizeClass = `widget-size-${item.size}`;
  const accentClass = `accent-border-${item.accentColor || def?.defaultColor || 'blue'}`;

  const isRequired = Boolean(def?.isRequired);
  const isSafetyCritical = Boolean(def?.isSafetyCritical);

  return (
    <div
      ref={setNodeRef}
      style={sortableStyle}
      className={`widget-wrapper-item ${sizeClass} ${isEditing ? 'is-editing' : ''} ${
        isDragging ? 'is-dragging' : ''
      }`}
      data-testid={`widget-wrapper-${item.widgetId}`}
      {...(isEditing ? attributes : {})}
      {...(isEditing ? listeners : {})}
    >
      {/* Edit Mode Header Overlay */}
      {isEditing && (
        <div
          className="widget-edit-header"
          data-testid={`widget-edit-header-${item.widgetId}`}
          title="Click and hold to drag widget"
        >
          <div className="widget-edit-header-left">
            <div
              className="widget-drag-handle"
              title="Click and hold to drag widget"
              aria-label={`Drag handle for ${def?.title || item.widgetId}`}
              data-testid={`drag-handle-${item.widgetId}`}
            >
              <GripVertical size={14} />
              <span className="drag-handle-hint">Drag</span>
            </div>

            <span className="widget-title-text">{def?.title || item.widgetId}</span>

            {isRequired && (
              <span
                className="widget-safety-badge required"
                title="Mandatory safety requirement: cannot be hidden or removed"
              >
                <Lock size={10} />
                <span>Required</span>
              </span>
            )}

            {!isRequired && isSafetyCritical && (
              <span
                className="widget-safety-badge critical"
                title="Critical financial calculation or verification record"
              >
                <ShieldAlert size={10} />
                <span>Safety Critical</span>
              </span>
            )}
          </div>

          <div
            className="widget-edit-header-right"
            onPointerDown={(e) => e.stopPropagation()}
            onTouchStart={(e) => e.stopPropagation()}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Size Selector */}
            <div
              className="widget-size-selector"
              role="group"
              aria-label={`Size controls for ${def?.title || item.widgetId}`}
            >
              {ALL_SIZES.map((sz) => {
                const isAllowed = def ? def.allowedSizes.includes(sz) : true;
                const isActive = item.size === sz;
                return (
                  <button
                    key={sz}
                    type="button"
                    className={`size-pill-btn ${isActive ? 'active' : ''}`}
                    disabled={!isAllowed}
                    onClick={() => onChangeSize(sz)}
                    title={
                      isAllowed
                        ? `Set size to ${sz.toUpperCase()}`
                        : `Size ${sz.toUpperCase()} not allowed for this widget`
                    }
                    aria-pressed={isActive}
                    data-testid={`size-btn-${item.widgetId}-${sz}`}
                  >
                    {sz}
                  </button>
                );
              })}
            </div>

            {/* Accent Color Picker */}
            <ColorPickerPopover
              currentColor={item.accentColor || def?.defaultColor || 'blue'}
              onChangeColor={onChangeColor}
              title={`Choose accent color for ${def?.title || item.widgetId}`}
            />

            {/* Hide / Remove Button */}
            <button
              type="button"
              className="widget-action-icon-btn remove-btn"
              disabled={isRequired}
              onClick={onRemove}
              title={
                isRequired
                  ? 'Required regulatory or safety widget cannot be removed'
                  : 'Remove widget from page'
              }
              aria-label={
                isRequired
                  ? 'Required widget cannot be removed'
                  : `Remove ${def?.title || item.widgetId}`
              }
              data-testid={`remove-widget-${item.widgetId}`}
            >
              {isRequired ? <Lock size={13} /> : <EyeOff size={13} />}
            </button>
          </div>
        </div>
      )}

      {/* Actual Widget Content */}
      <div className={`widget-content-container ${accentClass}`}>
        {children}
      </div>
    </div>
  );
};

