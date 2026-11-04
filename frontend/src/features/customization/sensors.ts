import {
  PointerSensor,
  TouchSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import { sortableKeyboardCoordinates } from '@dnd-kit/sortable';

/**
 * Standard sensor configuration for CashFlow AI visual layout editor.
 *
 * - PointerSensor: desktop mouse & pen dragging with a 5px activation threshold
 *   to distinguish intentional drags from clicks on size/color/remove buttons.
 * - TouchSensor: mobile & tablet touch dragging with a 150ms press-and-hold delay
 *   and 6px tolerance, allowing natural page scrolling without accidental drag lock.
 * - KeyboardSensor: accessible keyboard reordering via Space/Enter + Arrow keys.
 */
export function useCustomizationSensors() {
  return useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 5,
      },
    }),
    useSensor(TouchSensor, {
      activationConstraint: {
        delay: 150,
        tolerance: 6,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );
}
