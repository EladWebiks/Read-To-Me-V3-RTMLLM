import type { MotionValue } from 'motion/react'
import { ASSISTANT_FLOAT_HEIGHT, ASSISTANT_FLOAT_WIDTH } from './assistantGeometry'

export const assistantSpring = {
  type: 'spring' as const,
  stiffness: 380,
  damping: 32,
}

export function assistantPanelClass(expanded: boolean): string {
  const base =
    'pointer-events-auto fixed z-[60] flex flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-2xl'
  return expanded ? `${base} inset-3 sm:inset-4` : `${base} left-0 top-0`
}

export function assistantPanelStyle(
  expanded: boolean,
  x: MotionValue<number>,
  y: MotionValue<number>,
) {
  if (expanded) return { x, y }
  return { x, y, width: ASSISTANT_FLOAT_WIDTH, height: ASSISTANT_FLOAT_HEIGHT }
}
