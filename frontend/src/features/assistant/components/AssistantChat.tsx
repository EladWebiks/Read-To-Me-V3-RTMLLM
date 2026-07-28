import { ASSISTANT_CHAT_COLUMN } from '../assistantGeometry'
import { useAssistantChat } from '../hooks/useAssistantChat'
import { AssistantComposer } from './AssistantComposer'
import { AssistantMessageList } from './AssistantMessageList'

/** Live assistant chat with tools + HITL form cards. */
export function AssistantChat({ expanded = false }: { expanded?: boolean }) {
  const chat = useAssistantChat()
  const blocked = Boolean(chat.pendingConfirm)

  return (
    <div
      className={`flex min-h-0 flex-1 flex-col ${
        expanded ? 'bg-muted/25 px-3 py-3 sm:px-4 sm:py-4' : ''
      }`}
    >
      <div
        className={
          expanded
            ? `${ASSISTANT_CHAT_COLUMN} overflow-hidden rounded-2xl border border-border bg-card shadow-sm ring-1 ring-black/[0.03]`
            : 'flex min-h-0 flex-1 flex-col'
        }
      >
        <div className="flex min-h-0 flex-1 flex-col">
          <AssistantMessageList
            messages={chat.messages}
            framed={expanded}
            error={chat.error}
            sending={chat.sending}
            liveStatus={chat.liveStatus}
            confirmBusy={chat.sending}
            onResolveConfirm={(approved, values) =>
              void chat.resolveConfirm(approved, values)
            }
          />
          <AssistantComposer
            draft={chat.draft}
            setDraft={chat.setDraft}
            sending={chat.sending}
            blocked={blocked}
            onSend={() => void chat.send()}
          />
        </div>
      </div>
    </div>
  )
}
