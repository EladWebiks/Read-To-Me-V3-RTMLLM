import { useRef, type RefObject } from 'react'
import { motion, type DragControls, type MotionValue } from 'motion/react'
import { useTranslation } from 'react-i18next'
import { AssistantPanelChrome } from './components/AssistantPanelChrome'
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
export function AssistantPanelFrame({
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
}: Props) {
  const loadRef = useRef<(id: string) => Promise<void>>(async () => {})
  const { t } = useTranslation('assistant')

  return (
    <motion.div
      ref={panelRef}
      role="dialog"
      aria-modal={expanded}
      aria-label={t('ariaLabel')}
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
      className={`${assistantPanelClass()} relative overflow-hidden`}
    >
      <AssistantPanelChrome
        expanded={expanded}
        titleRef={titleRef}
        dragControls={dragControls}
        onToggleExpanded={onToggleExpanded}
        onClose={onClose}
        registerLoad={(fn) => {
          loadRef.current = fn
        }}
        loadConversation={(id) => loadRef.current(id)}
      />
    </motion.div>
  )
}
