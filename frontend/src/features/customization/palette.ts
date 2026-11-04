import type { MutedColorId, MutedColorToken } from './types.ts';

/**
 * CashFlow AI Curated Color Palette
 *
 * Grounded directly in the CSS custom properties of CashFlow AI (index.css).
 * Provides muted, cohesive tones suitable for financial dashboard cards,
 * badges, and accent outlines in both dark and light modes.
 */
export const CURATED_PALETTE: Record<MutedColorId, MutedColorToken> = {
  blue: {
    id: 'blue',
    name: 'CashFlow Light Blue',
    cssVariable: 'var(--accent-blue)',
    value: '#38bdf8',
    borderClass: 'border-accent-blue',
    textClass: 'text-accent-blue',
    bgSubtle: 'rgba(56, 189, 248, 0.12)',
  },
  cyan: {
    id: 'cyan',
    name: 'Electric Cyan',
    cssVariable: 'var(--accent-blue-hover)',
    value: '#22d3ee',
    borderClass: 'border-accent-cyan',
    textClass: 'text-accent-cyan',
    bgSubtle: 'rgba(34, 211, 238, 0.12)',
  },
  pink: {
    id: 'pink',
    name: 'Soft Pink Accent',
    cssVariable: 'var(--accent-pink)',
    value: '#f472b6',
    borderClass: 'border-accent-pink',
    textClass: 'text-accent-pink',
    bgSubtle: 'rgba(244, 114, 182, 0.10)',
  },
  purple: {
    id: 'purple',
    name: 'Lavender Purple',
    cssVariable: 'var(--accent-purple)',
    value: '#a78bfa',
    borderClass: 'border-accent-purple',
    textClass: 'text-accent-purple',
    bgSubtle: 'rgba(167, 139, 250, 0.12)',
  },
  emerald: {
    id: 'emerald',
    name: 'Mint Emerald',
    cssVariable: 'var(--color-success)',
    value: '#34d399',
    borderClass: 'border-color-success',
    textClass: 'text-color-success',
    bgSubtle: 'rgba(52, 211, 153, 0.10)',
  },
  amber: {
    id: 'amber',
    name: 'Amber Warning',
    cssVariable: 'var(--color-warning)',
    value: '#fbbf24',
    borderClass: 'border-color-warning',
    textClass: 'text-color-warning',
    bgSubtle: 'rgba(251, 191, 36, 0.10)',
  },
  rose: {
    id: 'rose',
    name: 'Coral Danger',
    cssVariable: 'var(--color-danger)',
    value: '#f87171',
    borderClass: 'border-color-danger',
    textClass: 'text-color-danger',
    bgSubtle: 'rgba(248, 113, 113, 0.10)',
  },
  slate: {
    id: 'slate',
    name: 'Steel Slate',
    cssVariable: 'var(--text-secondary)',
    value: '#7896b0',
    borderClass: 'border-text-secondary',
    textClass: 'text-text-secondary',
    bgSubtle: 'rgba(120, 150, 176, 0.12)',
  },
};

export const PALETTE_COLOR_IDS: readonly MutedColorId[] = [
  'blue',
  'cyan',
  'pink',
  'purple',
  'emerald',
  'amber',
  'rose',
  'slate',
] as const;

export function getMutedColorToken(id: MutedColorId): MutedColorToken {
  return CURATED_PALETTE[id] || CURATED_PALETTE.blue;
}

export function isValidMutedColor(color: unknown): color is MutedColorId {
  return typeof color === 'string' && color in CURATED_PALETTE;
}
