import { viewportSize } from './assistantGeometry'

/** Fullscreen overlay inset in CSS pixels (`inset-3` / `sm:inset-4`). */
export function expandedPanelRect(): {
  x: number
  y: number
  width: number
  height: number
} {
  const margin = window.matchMedia('(min-width: 640px)').matches ? 16 : 12
  const { width, height } = viewportSize()
  return {
    x: margin,
    y: margin,
    width: Math.max(200, width - margin * 2),
    height: Math.max(240, height - margin * 2),
  }
}
