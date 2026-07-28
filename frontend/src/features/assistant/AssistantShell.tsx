import { useLayoutEffect, type ReactNode } from 'react'
import { AnimatePresence, motion, useDragControls } from 'motion/react'
import { AssistantPanelFrame } from './AssistantPanelFrame'
import { clampPosition, panelSizeOrFallback } from './assistantGeometry'
import { useAssistantStore } from './assistantStore'
import { useAssistantFloatingPosition } from './useAssistantFloatingPosition'
import { useAssistantMotionValues, useCompactViewport } from './useAssistantMotion'

/** Open assistant shell: scrim + floating / fullscreen panel. */
export function AssistantShell() {
  const expanded = useAssistantStore((s) => s.expanded)
  const position = useAssistantStore((s) => s.position)
  const setOpen = useAssistantStore((s) => s.setOpen)
  const setExpanded = useAssistantStore((s) => s.setExpanded)
  const toggleExpanded = useAssistantStore((s) => s.toggleExpanded)
  const setPosition = useAssistantStore((s) => s.setPosition)
  const compact = useCompactViewport()
  const dragControls = useDragControls()
  const { panel, boundsRef, panelRef, titleRef } = useAssistantMotionValues()
  const dragGate = useAssistantFloatingPosition(expanded, position, panelRef, panel)

  useLayoutEffect(() => {
    titleRef.current?.focus()
  }, [titleRef])

  return (
    <ShellChrome>
      <div ref={boundsRef} className="pointer-events-none absolute inset-0" aria-hidden />
      <AnimatePresence>
        {expanded ? (
          <motion.div
            key="scrim"
            className="pointer-events-auto absolute inset-0 bg-black/45"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.22 }}
            onClick={() => setExpanded(false)}
          />
        ) : null}
      </AnimatePresence>
      <AssistantPanelFrame
        expanded={expanded}
        compact={compact}
        panelRef={panelRef}
        titleRef={titleRef}
        boundsRef={boundsRef}
        x={panel.x}
        y={panel.y}
        width={panel.width}
        height={panel.height}
        dragControls={dragControls}
        onDragStart={dragGate.onDragStart}
        onDragEnd={() => {
          dragGate.onDragEnd()
          const size = panelSizeOrFallback(panel.width.get(), panel.height.get())
          setPosition(
            clampPosition(panel.x.get(), panel.y.get(), size.width, size.height),
          )
        }}
        onToggleExpanded={toggleExpanded}
        onClose={() => setOpen(false)}
      />
    </ShellChrome>
  )
}

function ShellChrome({ children }: { children: ReactNode }) {
  return (
    <motion.div
      className="pointer-events-none fixed inset-0 z-[55]"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.15 }}
    >
      {children}
    </motion.div>
  )
}
