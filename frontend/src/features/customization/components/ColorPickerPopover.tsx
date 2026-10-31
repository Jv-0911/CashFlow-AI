import React, { useState, useRef, useEffect } from 'react';
import type { MutedColorId } from '../types.ts';
import { CURATED_PALETTE, PALETTE_COLOR_IDS } from '../palette.ts';

export interface ColorPickerPopoverProps {
  currentColor: MutedColorId;
  onChangeColor: (color: MutedColorId) => void;
  title?: string;
}

export const ColorPickerPopover: React.FC<ColorPickerPopoverProps> = ({
  currentColor,
  onChangeColor,
  title = 'Change Accent Color',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleOutside);
    }
    return () => document.removeEventListener('mousedown', handleOutside);
  }, [isOpen]);

  const activeToken = CURATED_PALETTE[currentColor] || CURATED_PALETTE.blue;

  return (
    <div className="color-picker-popover-trigger" ref={containerRef}>
      <button
        type="button"
        className="color-swatch-preview-btn"
        style={{ backgroundColor: activeToken.value }}
        onClick={() => setIsOpen((prev) => !prev)}
        title={title}
        aria-label={`Current accent color: ${activeToken.name}. Click to change.`}
        aria-expanded={isOpen}
      />

      {isOpen && (
        <div className="color-swatch-popover-menu" role="dialog" aria-label="Curated color options">
          {PALETTE_COLOR_IDS.map((colorId) => {
            const token = CURATED_PALETTE[colorId];
            const isActive = colorId === currentColor;
            return (
              <button
                key={colorId}
                type="button"
                className={`color-swatch-dot ${isActive ? 'active' : ''}`}
                style={{ backgroundColor: token.value }}
                onClick={() => {
                  onChangeColor(colorId);
                  setIsOpen(false);
                }}
                title={token.name}
                aria-label={token.name}
              />
            );
          })}
        </div>
      )}
    </div>
  );
};
