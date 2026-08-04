import type { PointerEvent, RefObject } from 'react'
import { useState } from 'react'
import type { DragControls } from 'motion/react'
import { useAssistantStore } from '../assistantStore'
import { AssistantHeader } from '../AssistantHeader'
import { AssistantChat } from './AssistantChat'
import { AssistantHistoryLayer } from './AssistantHistoryLayer'

/** Header + chat + history overlay inside the floating panel. */
export function AssistantPanelChrome({
  expanded,
  titleRef,
  dragControls,
  onToggleExpanded,
  onClose,
  registerLoad,
  loadConversation,
}: {
  expanded: boolean
  titleRef: RefObject<HTMLHeadingElement | null>
  dragControls: DragControls
  onToggleExpanded: () => void
  onClose: () => void
  registerLoad: (fn: (id: string) => Promise<void>) => void
  loadConversation: (id: string) => Promise<void>
}) {
  const [historyOpen, setHistoryOpen] = useState(false)
  const requestNewChat = useAssistantStore((s) => s.requestNewChat)

  return (
    <>
      <AssistantHeader
        expanded={expanded}
        titleRef={titleRef}
        onToggleExpanded={onToggleExpanded}
        onClose={onClose}
        historyOpen={historyOpen}
        onOpenHistory={() => setHistoryOpen((open) => !open)}
        onNewChat={() => {
          setHistoryOpen(false)
          requestNewChat()
        }}
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
      <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden">
        <AssistantChat expanded={expanded} registerLoad={registerLoad} />
        <AssistantHistoryLayer
          open={historyOpen}
          onClose={() => setHistoryOpen(false)}
          loadConversation={loadConversation}
        />
      </div>
    </>
  )
}
