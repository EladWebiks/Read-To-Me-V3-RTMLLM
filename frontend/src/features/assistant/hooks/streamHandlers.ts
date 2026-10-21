import type { Dispatch, MutableRefObject, SetStateAction } from 'react'
import { lastUserLang } from '@/shared/lib/textDirection'
import type {
  ChatMessage,
  ChatStreamHandlers,
  ChoicePayload,
  ClientAction,
  ConfirmationPayload,
} from '../api/chatApi'
import { chatErrorMessage } from '../logic/errorCopy'
import {
  appendChoice,
  appendConfirmation,
  appendToolResult,
  patchAssistant,
} from './streamMessagePatch'
import { applyToolSideEffects } from './toolSideEffects'

export type StreamArgs = {
  conversationId: string | null
  assistantId: string
  setConversationId: (id: string | null) => void
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>
  setError: (detail: string | null) => void
  setQuotaResetsAt: (resetsAt: string | null) => void
  setLiveStatus: (label: string | null) => void
  setSending?: (sending: boolean) => void
  abortRef: MutableRefObject<AbortController | null>
  onClientAction?: (action: ClientAction) => void
}

/** Shared SSE handler wiring for chat + confirm streams. */
export function buildStreamHandlers(
  args: StreamArgs,
  onAwaitingConfirm?: (payload: ConfirmationPayload) => void,
): ChatStreamHandlers {
  const {
    assistantId,
    setConversationId,
    setMessages,
    setLiveStatus,
    setSending,
    onClientAction,
  } = args
  return {
    onMeta: (id) => setConversationId(id),
    onDelta: (delta) => {
      setLiveStatus(null)
      patchAssistant(setMessages, assistantId, delta)
    },
    onStep: (label) => setLiveStatus(label),
    onToolResult: ({ name, ok, summary, clientAction }) => {
      applyToolSideEffects(name, ok)
      setLiveStatus(ok ? 'Writing your answer…' : 'Trying another approach…')
      setMessages((prev) =>
        appendToolResult(prev, assistantId, name, ok, summary, clientAction),
      )
      if (clientAction) onClientAction?.(clientAction)
    },
    onConfirmation: (payload) => {
      setLiveStatus(null)
      setSending?.(false)
      setMessages((prev) => appendConfirmation(prev, assistantId, payload))
      onAwaitingConfirm?.(payload)
    },
    onChoiceRequest: (payload: ChoicePayload) => {
      setLiveStatus(null)
      setSending?.(false)
      setMessages((prev) => appendChoice(prev, payload))
    },
    onDone: ({ messageId, status }) => {
      if (status !== 'awaiting_confirmation') setLiveStatus(null)
      if (status === 'awaiting_confirmation' || !messageId) return
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantId ? { ...m, id: messageId } : m)),
      )
    },
    onError: buildErrorHandler(args),
  }
}

/** Quota refusals become an inline marker + composer lock; the rest banner. */
function buildErrorHandler(args: StreamArgs): ChatStreamHandlers['onError'] {
  const { setMessages, setError, setQuotaResetsAt, setLiveStatus } = args
  return (detail, code, resetsAt) => {
    setLiveStatus(null)
    if (code === 'quota_exceeded') {
      setMessages((prev) => [
        ...prev,
        { id: `quota-${crypto.randomUUID()}`, role: 'quota_refusal', content: detail },
      ])
      setQuotaResetsAt(resetsAt ?? null)
      return
    }
    setMessages((prev) => {
      const lang = lastUserLang(prev)
      queueMicrotask(() => setError(chatErrorMessage(detail, code, resetsAt, lang)))
      return prev
    })
  }
}
