import { useLayoutEffect, useRef, useState, type RefObject } from 'react'
import { useMotionValue, type MotionValue } from 'motion/react'
import {
  ASSISTANT_COMPACT_MQ,
  clampPosition,
  isCompactViewport,
  panelSizeOrFallback,
  resolveFloatingPosition,
  type AssistantPoint,
} from './assistantGeometry'

type DragGate = {
  onDragStart: () => void
  onDragEnd: () => void
}

/**
 * Sync placement from the store on open/position change only.
 * Resize reclamps the live motion values — never rewinds to a stale store point
 * (mobile URL-bar resize was snapping the panel mid-drag).
 */
export function useAssistantFloatingPosition(
  expanded: boolean,
  position: AssistantPoint | null,
  panelRef: RefObject<HTMLDivElement | null>,
  x: MotionValue<number>,
  y: MotionValue<number>,
): DragGate {
  const draggingRef = useRef(false)

  useLayoutEffect(() => {
    if (expanded) {
      x.set(0)
      y.set(0)
      return
    }
    if (draggingRef.current) return
    const el = panelRef.current
    const { width, height } = panelSizeOrFallback(el?.offsetWidth, el?.offsetHeight)
    const next = resolveFloatingPosition(position, width, height)
    x.set(next.x)
    y.set(next.y)
  }, [expanded, position, panelRef, x, y])

  useLayoutEffect(() => {
    if (expanded) return

    function reclampLive() {
      if (draggingRef.current) return
      const el = panelRef.current
      const { width, height } = panelSizeOrFallback(el?.offsetWidth, el?.offsetHeight)
      const next = clampPosition(x.get(), y.get(), width, height)
      x.set(next.x)
      y.set(next.y)
    }

    const mq = window.matchMedia(ASSISTANT_COMPACT_MQ)
    mq.addEventListener('change', reclampLive)
    window.addEventListener('resize', reclampLive)
    return () => {
      mq.removeEventListener('change', reclampLive)
      window.removeEventListener('resize', reclampLive)
    }
  }, [expanded, panelRef, x, y])

  return {
    onDragStart: () => {
      draggingRef.current = true
    },
    onDragEnd: () => {
      draggingRef.current = false
    },
  }
}

export function useCompactViewport(): boolean {
  const [compact, setCompact] = useState(isCompactViewport)
  useLayoutEffect(() => {
    const mq = window.matchMedia(ASSISTANT_COMPACT_MQ)
    function sync() {
      setCompact(mq.matches)
    }
    sync()
    mq.addEventListener('change', sync)
    return () => mq.removeEventListener('change', sync)
  }, [])
  return compact
}

export function useAssistantMotionValues() {
  const x = useMotionValue(0)
  const y = useMotionValue(0)
  const boundsRef = useRef<HTMLDivElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const titleRef = useRef<HTMLHeadingElement>(null)
  return { x, y, boundsRef, panelRef, titleRef }
}
