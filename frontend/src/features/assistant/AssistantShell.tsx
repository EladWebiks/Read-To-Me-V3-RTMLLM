import { useLayoutEffect } from 'react'
import { AnimatePresence, motion, useDragControls } from 'motion/react'
import { AssistantPanelFrame } from './AssistantPanelFrame'
import { clampPosition } from './assistantGeometry'
import { useAssistantStore } from './assistantStore'
import {
  useAssistantFloatingPosition,
  useAssistantMotionValues,
} from './useAssistantFloatingPosition'

/** Open assistant shell: scrim + floating / fullscreen panel. */
export function AssistantShell() {
  const expanded = useAssistantStore((s) => s.expanded)
  const position = useAssistantStore((s) => s.position)
  const setOpen = useAssistantStore((s) => s.setOpen)
  const setExpanded = useAssistantStore((s) => s.setExpanded)
  const toggleExpanded = useAssistantStore((s) => s.toggleExpanded)
  const setPosition = useAssistantStore((s) => s.setPosition)
  const dragControls = useDragControls()
  const { x, y, boundsRef, panelRef, titleRef } = useAssistantMotionValues()
  useAssistantFloatingPosition(expanded, position, panelRef, x, y)
  useLayoutEffect(() => {
    titleRef.current?.focus()
  }, [titleRef])

  return (
    <motion.div
      className="pointer-events-none fixed inset-0 z-[55]"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.15 }}
    >
      <div ref={boundsRef} className="pointer-events-none absolute inset-0" aria-hidden />
      <AnimatePresence>
        {expanded ? (
          <motion.div
            key="scrim"
            className="pointer-events-auto absolute inset-0 bg-black/45"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={() => setExpanded(false)}
          />
        ) : null}
      </AnimatePresence>
      <AssistantPanelFrame
        expanded={expanded}
        panelRef={panelRef}
        titleRef={titleRef}
        boundsRef={boundsRef}
        x={x}
        y={y}
        dragControls={dragControls}
        onDragEnd={() => {
          const el = panelRef.current
          setPosition(
            clampPosition(
              x.get(),
              y.get(),
              el?.offsetWidth ?? 448,
              el?.offsetHeight ?? 544,
            ),
          )
        }}
        onToggleExpanded={toggleExpanded}
        onClose={() => setOpen(false)}
      />
    </motion.div>
  )
}
