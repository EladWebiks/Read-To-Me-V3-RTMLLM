import { ASSISTANT_CHAT_COLUMN } from '../assistantGeometry'
import { useAssistantChat } from '../hooks/useAssistantChat'
import { AssistantComposer } from './AssistantComposer'
import { AssistantMessageList } from './AssistantMessageList'

/** Live assistant chat (tool-less B2). */
export function AssistantChat({ expanded = false }: { expanded?: boolean }) {
  const chat = useAssistantChat()

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
        <ChatBody framed={expanded} chat={chat} />
      </div>
    </div>
  )
}

type ChatApi = ReturnType<typeof useAssistantChat>

function ChatBody({ framed, chat }: { framed: boolean; chat: ChatApi }) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <AssistantMessageList
        messages={chat.messages}
        framed={framed}
        error={chat.error}
        sending={chat.sending}
      />
      <AssistantComposer
        draft={chat.draft}
        setDraft={chat.setDraft}
        sending={chat.sending}
        onSend={() => void chat.send()}
      />
    </div>
  )
}
