import { type PointerEvent, type RefObject } from 'react'
import { motion, type DragControls, type MotionValue } from 'motion/react'
import { AssistantChat } from './components/AssistantChat'
import { AssistantHeader } from './AssistantHeader'
import { assistantPanelClass, assistantPanelStyle } from './assistantPanelStyle'

type Props = {
  expanded: boolean
  compact: boolean
  panelRef: RefObject<HTMLDivElement | null>
  titleRef: RefObject<HTMLHeadingElement | null>
  boundsRef: RefObject<HTMLDivElement | null>
  x: MotionValue<number>
  y: MotionValue<number>
  width: MotionValue<number>
  height: MotionValue<number>
  dragControls: DragControls
  onDragStart: () => void
  onDragEnd: () => void
  onToggleExpanded: () => void
  onClose: () => void
}

/** Draggable floating / fullscreen chat panel frame. */
export function AssistantPanelFrame(props: Props) {
  const {
    expanded,
    compact,
    panelRef,
    titleRef,
    boundsRef,
    x,
    y,
    width,
    height,
    dragControls,
    onDragStart,
    onDragEnd,
    onToggleExpanded,
    onClose,
  } = props

  return (
    <motion.div
      ref={panelRef}
      role="dialog"
      aria-modal={expanded}
      aria-label="Assistant"
      drag={expanded ? false : compact ? 'y' : true}
      dragControls={dragControls}
      dragListener={false}
      dragConstraints={expanded || compact ? undefined : boundsRef}
      dragMomentum={false}
      dragElastic={0}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.15 }}
      style={assistantPanelStyle(x, y, width, height)}
      className={assistantPanelClass()}
    >
      <AssistantHeader
        expanded={expanded}
        titleRef={titleRef}
        onToggleExpanded={onToggleExpanded}
        onClose={onClose}
        dragHandleProps={
          expanded
            ? undefined
            : {
                onPointerDown: (e: PointerEvent) => {
                  e.preventDefault()
                  dragControls.start(e, { snapToCursor: false })
                },
              }
        }
      />
      <AssistantChat expanded={expanded} />
    </motion.div>
  )
}
