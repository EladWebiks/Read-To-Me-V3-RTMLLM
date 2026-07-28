import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { useMotionValue } from 'motion/react'
import { ASSISTANT_COMPACT_MQ, isCompactViewport } from './assistantGeometry'
import type { PanelMotion } from './useAssistantFloatingPosition'

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
  const width = useMotionValue(360)
  const height = useMotionValue(480)
  const boundsRef = useRef<HTMLDivElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const titleRef = useRef<HTMLHeadingElement>(null)
  const panel = useMemo(
    (): PanelMotion => ({ x, y, width, height }),
    [x, y, width, height],
  )
  return { panel, boundsRef, panelRef, titleRef }
}
