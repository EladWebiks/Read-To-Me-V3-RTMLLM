/** Default floating size helpers for the assistant shell. */
export const ASSISTANT_FLOAT_WIDTH = 'min(28rem, calc(100vw - 1rem))'
export const ASSISTANT_FLOAT_HEIGHT =
  'min(34rem, calc(100dvh - 4.5rem - env(safe-area-inset-top, 0px) - env(safe-area-inset-bottom, 0px)))'

/** Shorter on phones so vertical drag has room. */
export const ASSISTANT_FLOAT_HEIGHT_COMPACT =
  'min(28rem, calc(100dvh - 8rem - env(safe-area-inset-top, 0px) - env(safe-area-inset-bottom, 0px)))'

/** Centered chat column inside the expanded overlay. */
export const ASSISTANT_CHAT_COLUMN =
  'mx-auto flex h-full min-h-0 w-full max-w-xl flex-col'

/** Tailwind `sm` — below this: centered + vertical-only drag. */
export const ASSISTANT_COMPACT_MQ = '(max-width: 639px)'

export type AssistantPoint = { x: number; y: number }

export function viewportSize(): { width: number; height: number } {
  return { width: window.innerWidth, height: window.innerHeight }
}

export function isCompactViewport(): boolean {
  return window.matchMedia(ASSISTANT_COMPACT_MQ).matches
}

/** Prefer measured size; fall back to a viewport-safe estimate (avoids off-screen on mobile). */
export function panelSizeOrFallback(
  measuredW: number | undefined,
  measuredH: number | undefined,
): { width: number; height: number } {
  const { width: vw, height: vh } = viewportSize()
  const width =
    measuredW && measuredW > 0 ? measuredW : Math.min(448, Math.max(200, vw - 16))
  const height =
    measuredH && measuredH > 0
      ? measuredH
      : Math.min(
          isCompactViewport() ? 448 : 544,
          Math.max(240, vh - (isCompactViewport() ? 128 : 72)),
        )
  return { width, height }
}

function centeredX(widthPx: number): number {
  const { width: vw } = viewportSize()
  return Math.max(8, Math.round((vw - widthPx) / 2))
}

export function defaultFloatingPosition(
  widthPx: number,
  heightPx: number,
): AssistantPoint {
  const margin = 12
  const { width: vw, height: vh } = viewportSize()
  if (isCompactViewport()) {
    return {
      x: centeredX(widthPx),
      y: Math.max(margin, Math.round((vh - heightPx) / 2)),
    }
  }
  return {
    x: Math.max(margin, vw - widthPx - margin),
    y: Math.max(margin, vh - heightPx - margin),
  }
}

export function clampPosition(
  x: number,
  y: number,
  widthPx: number,
  heightPx: number,
): AssistantPoint {
  const margin = 8
  const { width: vw, height: vh } = viewportSize()
  const maxX = Math.max(margin, vw - widthPx - margin)
  const maxY = Math.max(margin, vh - heightPx - margin)
  const next = {
    x: Math.min(Math.max(margin, x), maxX),
    y: Math.min(Math.max(margin, y), maxY),
  }
  if (isCompactViewport()) {
    return { x: centeredX(widthPx), y: next.y }
  }
  return next
}

/** Default placement, or stored point — always clamped to the current viewport. */
export function resolveFloatingPosition(
  position: AssistantPoint | null,
  widthPx: number,
  heightPx: number,
): AssistantPoint {
  if (isCompactViewport()) {
    const y = position?.y ?? defaultFloatingPosition(widthPx, heightPx).y
    return clampPosition(0, y, widthPx, heightPx)
  }
  const next = position ?? defaultFloatingPosition(widthPx, heightPx)
  return clampPosition(next.x, next.y, widthPx, heightPx)
}
