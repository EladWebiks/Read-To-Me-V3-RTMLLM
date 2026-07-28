import type { MotionValue } from 'motion/react'

export const assistantSpring = {
  type: 'spring' as const,
  stiffness: 380,
  damping: 34,
  mass: 0.85,
}

/** Soft size/position tween when expanding or shrinking the panel. */
export const assistantLayoutTransition = {
  type: 'spring' as const,
  stiffness: 300,
  damping: 34,
  mass: 0.9,
}

export function assistantPanelClass(): string {
  return 'assistant-panel pointer-events-auto fixed left-0 top-0 z-[60] flex flex-col overflow-hidden rounded-2xl border bg-card will-change-transform'
}

export function assistantPanelStyle(
  x: MotionValue<number>,
  y: MotionValue<number>,
  width: MotionValue<number>,
  height: MotionValue<number>,
) {
  return { x, y, width, height }
}
