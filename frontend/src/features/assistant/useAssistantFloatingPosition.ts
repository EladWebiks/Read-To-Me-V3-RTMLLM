import { useLayoutEffect, useRef, type RefObject } from 'react'
import { animate, type MotionValue } from 'motion/react'
import {
  clampPosition,
  panelSizeOrFallback,
  resolveFloatingPosition,
  type AssistantPoint,
} from './assistantGeometry'
import { expandedPanelRect } from './expandedPanelRect'
import { assistantLayoutTransition } from './assistantPanelStyle'

export type PanelMotion = {
  x: MotionValue<number>
  y: MotionValue<number>
  width: MotionValue<number>
  height: MotionValue<number>
}

type DragGate = { onDragStart: () => void; onDragEnd: () => void }

function applyRect(
  motion: PanelMotion,
  rect: { x: number; y: number; width: number; height: number },
  tween: boolean,
) {
  const { x, y, width, height } = motion
  if (tween) {
    void animate(x, rect.x, assistantLayoutTransition)
    void animate(y, rect.y, assistantLayoutTransition)
    void animate(width, rect.width, assistantLayoutTransition)
    void animate(height, rect.height, assistantLayoutTransition)
    return
  }
  x.set(rect.x)
  y.set(rect.y)
  width.set(rect.width)
  height.set(rect.height)
}

/** Drive panel x/y/width/height for float vs fullscreen. */
export function useAssistantFloatingPosition(
  expanded: boolean,
  position: AssistantPoint | null,
  panelRef: RefObject<HTMLDivElement | null>,
  motion: PanelMotion,
): DragGate {
  const draggingRef = useRef(false)
  const expandedRef = useRef(expanded)
  const bootedRef = useRef(false)

  useLayoutEffect(() => {
    const wasExpanded = expandedRef.current
    expandedRef.current = expanded
    const tween = bootedRef.current && wasExpanded !== expanded

    if (expanded) {
      applyRect(motion, expandedPanelRect(), tween)
      bootedRef.current = true
      return
    }
    if (draggingRef.current) return
    const size = panelSizeOrFallback(undefined, undefined)
    const next = resolveFloatingPosition(position, size.width, size.height)
    applyRect(motion, { ...next, ...size }, tween)
    bootedRef.current = true
  }, [expanded, position, panelRef, motion])

  useFloatResize(expanded, draggingRef, motion)
  useExpandedResize(expanded, motion)

  return {
    onDragStart: () => {
      draggingRef.current = true
    },
    onDragEnd: () => {
      draggingRef.current = false
    },
  }
}

function useFloatResize(
  expanded: boolean,
  draggingRef: { current: boolean },
  motion: PanelMotion,
) {
  const { x, y } = motion
  useLayoutEffect(() => {
    if (expanded) return
    function reclampLive() {
      if (draggingRef.current) return
      const size = panelSizeOrFallback(undefined, undefined)
      const next = clampPosition(x.get(), y.get(), size.width, size.height)
      applyRect(motion, { ...next, ...size }, false)
    }
    window.addEventListener('resize', reclampLive)
    return () => window.removeEventListener('resize', reclampLive)
  }, [expanded, draggingRef, motion, x, y])
}

function useExpandedResize(expanded: boolean, motion: PanelMotion) {
  useLayoutEffect(() => {
    if (!expanded) return
    function syncExpanded() {
      applyRect(motion, expandedPanelRect(), false)
    }
    window.addEventListener('resize', syncExpanded)
    return () => window.removeEventListener('resize', syncExpanded)
  }, [expanded, motion])
}
