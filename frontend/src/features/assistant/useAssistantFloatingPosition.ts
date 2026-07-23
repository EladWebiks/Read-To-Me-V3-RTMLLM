import { useLayoutEffect, useRef, type RefObject } from 'react'
import { useMotionValue, type MotionValue } from 'motion/react'
import { defaultFloatingPosition } from './assistantGeometry'
import type { AssistantPosition } from './assistantStore'

/** Keep motion x/y in sync with store position (or default bottom-right). */
export function useAssistantFloatingPosition(
  expanded: boolean,
  position: AssistantPosition | null,
  panelRef: RefObject<HTMLDivElement | null>,
  x: MotionValue<number>,
  y: MotionValue<number>,
) {
  useLayoutEffect(() => {
    if (expanded) {
      x.set(0)
      y.set(0)
      return
    }
    const el = panelRef.current
    const next =
      position ?? defaultFloatingPosition(el?.offsetWidth ?? 448, el?.offsetHeight ?? 544)
    x.set(next.x)
    y.set(next.y)
  }, [expanded, position, panelRef, x, y])
}

export function useAssistantMotionValues() {
  const x = useMotionValue(0)
  const y = useMotionValue(0)
  const boundsRef = useRef<HTMLDivElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const titleRef = useRef<HTMLHeadingElement>(null)
  return { x, y, boundsRef, panelRef, titleRef }
}
