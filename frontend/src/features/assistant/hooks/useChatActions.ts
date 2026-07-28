import {
  useCallback,
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
} from 'react'
import type { ChatMessage, ConfirmationPayload } from '../api/chatApi'
import { markConfirmStatus } from './confirmHelpers'
import { runAssistantStream, runConfirmStream } from './runAssistantStream'

type Args = {
  conversationId: string | null
  draft: string
  setDraft: (v: string) => void
  sending: boolean
  setSending: (v: boolean) => void
  pendingConfirm: ConfirmationPayload | null
  setPendingConfirm: (v: ConfirmationPayload | null) => void
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>
  setError: (v: string | null) => void
  setLiveStatus: (v: string | null) => void
  setConversationId: (id: string | null) => void
  abortRef: MutableRefObject<AbortController | null>
  uiContext: { path: string; book_id?: string; chapter_id?: string }
}

function localId(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`
}

/** Send + confirm actions for the assistant chat hook. */
export function useChatActions(args: Args) {
  const send = useCallback(async () => {
    const text = args.draft.trim()
    if (!text || args.sending || args.pendingConfirm) return
    args.setDraft('')
    args.setError(null)
    args.setLiveStatus('Thinking…')
    args.setSending(true)
    const assistantId = localId('assistant')
    args.setMessages((prev) => [
      ...prev,
      { id: localId('user'), role: 'user', content: text },
    ])
    await runAssistantStream(
      {
        text,
        conversationId: args.conversationId,
        assistantId,
        setConversationId: args.setConversationId,
        setMessages: args.setMessages,
        setError: args.setError,
        setLiveStatus: args.setLiveStatus,
        abortRef: args.abortRef,
        uiContext: args.uiContext,
      },
      (payload) => args.setPendingConfirm(payload),
    )
    args.setLiveStatus(null)
    args.setSending(false)
  }, [args])

  const resolveConfirm = useCallback(
    async (approved: boolean, values?: Record<string, unknown>) => {
      if (!args.pendingConfirm || !args.conversationId || args.sending) return
      const callId = args.pendingConfirm.callId
      args.setPendingConfirm(null)
      args.setLiveStatus('Thinking…')
      args.setSending(true)
      args.setError(null)
      markConfirmStatus(args.setMessages, callId, approved ? 'approved' : 'rejected')
      const assistantId = localId('assistant')
      await runConfirmStream({
        conversationId: args.conversationId,
        callId,
        approved,
        values,
        assistantId,
        setConversationId: args.setConversationId,
        setMessages: args.setMessages,
        setError: args.setError,
        setLiveStatus: args.setLiveStatus,
        abortRef: args.abortRef,
      })
      args.setLiveStatus(null)
      args.setSending(false)
    },
    [args],
  )

  return { send, resolveConfirm }
}
