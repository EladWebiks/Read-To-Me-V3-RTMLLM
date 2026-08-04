import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { useAssistantStore } from '../assistantStore'
import { ChatHistoryDrawer } from './ChatHistoryDrawer'

/** History drawer + loading scrim over the whole chat panel. */
export function AssistantHistoryLayer({
  open,
  onClose,
  loadConversation,
}: {
  open: boolean
  onClose: () => void
  loadConversation: (id: string) => Promise<void>
}) {
  const activeId = useAssistantStore((s) => s.conversationId)
  const [selecting, setSelecting] = useState(false)

  return (
    <>
      {selecting ? <HistoryLoadingScrim /> : null}
      <ChatHistoryDrawer
        open={open}
        activeId={activeId}
        selecting={selecting}
        onClose={onClose}
        onSelect={(id) => {
          void (async () => {
            setSelecting(true)
            try {
              await loadConversation(id)
              onClose()
            } finally {
              setSelecting(false)
            }
          })()
        }}
      />
    </>
  )
}

function HistoryLoadingScrim() {
  return (
    <div className="absolute inset-0 z-30 flex items-center justify-center bg-background/55 backdrop-blur-[2px]">
      <div className="flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5 text-sm shadow-sm">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading chat…
      </div>
    </div>
  )
}
