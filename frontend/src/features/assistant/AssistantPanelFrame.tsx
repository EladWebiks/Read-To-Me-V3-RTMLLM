import { type PointerEvent, type RefObject } from 'react'
import { motion, type DragControls, type MotionValue } from 'motion/react'
import { AssistantChatPlaceholder } from './AssistantChatPlaceholder'
import { AssistantHeader } from './AssistantHeader'
import {
  assistantPanelClass,
  assistantPanelStyle,
  assistantSpring,
} from './assistantPanelStyle'

type Props = {
  expanded: boolean
  panelRef: RefObject<HTMLDivElement | null>
  titleRef: RefObject<HTMLHeadingElement | null>
  boundsRef: RefObject<HTMLDivElement | null>
  x: MotionValue<number>
  y: MotionValue<number>
  dragControls: DragControls
  onDragEnd: () => void
  onToggleExpanded: () => void
  onClose: () => void
}

/** Draggable floating / fullscreen chat panel frame. */
export function AssistantPanelFrame(props: Props) {
  const {
    expanded,
    panelRef,
    titleRef,
    boundsRef,
    x,
    y,
    dragControls,
    onDragEnd,
    onToggleExpanded,
    onClose,
  } = props

  return (
    <motion.div
      ref={panelRef}
      layout
      layoutId="assistant-panel"
      role="dialog"
      aria-modal={expanded}
      aria-label="Assistant"
      drag={!expanded}
      dragControls={dragControls}
      dragListener={false}
      dragConstraints={boundsRef}
      dragMomentum={false}
      dragElastic={0.04}
      onDragEnd={onDragEnd}
      initial={{ opacity: 0, scale: 0.94 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.96 }}
      transition={assistantSpring}
      style={assistantPanelStyle(expanded, x, y)}
      className={assistantPanelClass(expanded)}
    >
      <AssistantHeader
        expanded={expanded}
        titleRef={titleRef}
        onToggleExpanded={onToggleExpanded}
        onClose={onClose}
        dragHandleProps={
          expanded
            ? undefined
            : { onPointerDown: (e: PointerEvent) => dragControls.start(e) }
        }
      />
      <AssistantChatPlaceholder expanded={expanded} />
    </motion.div>
  )
}
