/** Default floating size helpers for the assistant shell. */
export const ASSISTANT_FLOAT_WIDTH = 'min(28rem, calc(100vw - 1.5rem))'
export const ASSISTANT_FLOAT_HEIGHT = 'min(34rem, calc(100dvh - 6rem))'

/** Centered chat column inside the expanded overlay. */
export const ASSISTANT_CHAT_COLUMN =
  'mx-auto flex h-full min-h-0 w-full max-w-xl flex-col'

export function defaultFloatingPosition(
  widthPx: number,
  heightPx: number,
): { x: number; y: number } {
  const margin = 16
  return {
    x: Math.max(margin, window.innerWidth - widthPx - margin),
    y: Math.max(margin, window.innerHeight - heightPx - margin),
  }
}

export function clampPosition(
  x: number,
  y: number,
  widthPx: number,
  heightPx: number,
): { x: number; y: number } {
  const margin = 8
  const maxX = Math.max(margin, window.innerWidth - widthPx - margin)
  const maxY = Math.max(margin, window.innerHeight - heightPx - margin)
  return {
    x: Math.min(Math.max(margin, x), maxX),
    y: Math.min(Math.max(margin, y), maxY),
  }
}
