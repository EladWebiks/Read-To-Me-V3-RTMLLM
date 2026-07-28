import { useCallback, useRef, useState } from 'react'
import type { ChatMessage, ConfirmationPayload } from '../api/chatApi'
import { useAssistantStore } from '../assistantStore'
import { useHydrateConversation, useNewChatReset } from './chatLifecycle'
import { useChatActions } from './useChatActions'
import { uiContextPayload, useUiContext } from './useUiContext'

/** Local chat state + SSE streaming (tools + HITL). */
export function useAssistantChat() {
  const conversationId = useAssistantStore((s) => s.conversationId)
  const setConversationId = useAssistantStore((s) => s.setConversationId)
  const newChatNonce = useAssistantStore((s) => s.newChatNonce)
  const uiContext = useUiContext()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [liveStatus, setLiveStatus] = useState<string | null>(null)
  const [pendingConfirm, setPendingConfirm] = useState<ConfirmationPayload | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  useHydrateConversation(setMessages, setConversationId)

  const clearLocal = useCallback(() => {
    setMessages([])
    setDraft('')
    setError(null)
    setSending(false)
    setLiveStatus(null)
    setPendingConfirm(null)
  }, [])
  useNewChatReset(newChatNonce, abortRef, clearLocal)

  const { send, resolveConfirm } = useChatActions({
    conversationId,
    draft,
    setDraft,
    sending,
    setSending,
    pendingConfirm,
    setPendingConfirm,
    setMessages,
    setError,
    setLiveStatus,
    setConversationId,
    abortRef,
    uiContext: uiContextPayload(uiContext),
  })

  return {
    messages,
    draft,
    setDraft,
    sending,
    error,
    liveStatus,
    pendingConfirm,
    send,
    resolveConfirm,
  }
}
