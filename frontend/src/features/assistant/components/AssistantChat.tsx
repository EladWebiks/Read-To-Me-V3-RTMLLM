import { useEffect } from 'react'
import { useMeUsage } from '@/features/usage'
import { chatUiLang, lastUserLang, type ChatUiLang } from '@/shared/lib/textDirection'
import { ASSISTANT_CHAT_COLUMN } from '../assistantGeometry'
import type { ChatMessage } from '../api/chatApi'
import { useAssistantChat } from '../hooks/useAssistantChat'
import { ChatUiLangProvider } from '../hooks/ChatUiLangProvider'
import { quotaLock } from '../logic/quotaState'
import { AssistantComposer } from './AssistantComposer'
import { AssistantMessageList } from './AssistantMessageList'

function resolveUiLang(draft: string, messages: ChatMessage[]): ChatUiLang {
  return draft.trim() ? chatUiLang(draft) : lastUserLang(messages)
}

/** Live assistant chat with tools + HITL form cards. */
export function AssistantChat({
  expanded = false,
  registerLoad,
}: {
  expanded?: boolean
  registerLoad?: (fn: (id: string) => Promise<void>) => void
}) {
  const chat = useAssistantChat()
  const usage = useMeUsage()
  const blocked = Boolean(chat.pendingConfirm)
  const uiLang = resolveUiLang(chat.draft, chat.messages)
  const quotaNotice = quotaLock(usage.data, chat.quotaResetsAt, uiLang)

  useEffect(() => {
    registerLoad?.(chat.loadConversation)
  }, [chat.loadConversation, registerLoad])

  return (
    <ChatUiLangProvider lang={uiLang}>
      <div
        className={`flex min-h-0 flex-1 flex-col ${
          expanded ? 'bg-muted/25 px-3 py-3 sm:px-4 sm:py-4' : ''
        }`}
      >
        <ChatColumn
          expanded={expanded}
          chat={chat}
          blocked={blocked}
          quotaNotice={quotaNotice}
        />
      </div>
    </ChatUiLangProvider>
  )
}

function ChatColumn({
  expanded,
  chat,
  blocked,
  quotaNotice,
}: {
  expanded: boolean
  chat: ReturnType<typeof useAssistantChat>
  blocked: boolean
  quotaNotice: string | null
}) {
  return (
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
          sending={chat.sending || chat.loadingHistory}
          liveStatus={chat.liveStatus}
          confirmBusy={chat.sending}
          choicesDisabled={Boolean(chat.pendingConfirm)}
          onResolveConfirm={(approved, values) =>
            void chat.resolveConfirm(approved, values)
          }
          onPickChoice={(label) => void chat.sendText(label)}
        />
        <AssistantComposer
          draft={chat.draft}
          setDraft={chat.setDraft}
          sending={chat.sending || chat.loadingHistory}
          status={chat.liveStatus}
          blocked={blocked}
          quotaNotice={quotaNotice}
          onSend={() => void chat.send()}
          onCancel={chat.cancel}
        />
      </div>
    </div>
  )
}
