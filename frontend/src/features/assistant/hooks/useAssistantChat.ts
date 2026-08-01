import { useCallback, useState } from 'react'
import { useTheme } from 'next-themes'
import { useLocation, useNavigate } from 'react-router'
import type { ChatMessage, ClientAction, ConfirmationPayload } from '../api/chatApi'
import { useAssistantStore } from '../assistantStore'
import { useHydrateConversation, useNewChatReset } from './chatLifecycle'
import {
  useCancelAssistant,
  useChatFeedbackState,
  useClearLocalChat,
} from './chatSessionState'
import { applyClientAction } from './clientActions'
import { useChatActions } from './useChatActions'
import { uiContextPayload, useUiContext } from './useUiContext'

/** Local chat state + SSE streaming (tools + HITL). */
export function useAssistantChat() {
  const conversationId = useAssistantStore((s) => s.conversationId)
  const setConversationId = useAssistantStore((s) => s.setConversationId)
  const newChatNonce = useAssistantStore((s) => s.newChatNonce)
  const uiContext = useUiContext()
  const { setTheme } = useTheme()
  const [navigate, pathname] = useAssistantNavigation()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const feedback = useChatFeedbackState()
  const { setError, setLiveStatus, setQuotaResetsAt } = feedback
  const [pendingConfirm, setPendingConfirm] = useState<ConfirmationPayload | null>(null)
  const [abortRef] = useState(() => ({ current: null as AbortController | null }))

  useHydrateConversation(setMessages, setConversationId)

  const clearLocal = useClearLocalChat({
    setMessages,
    setDraft,
    setSending,
    setPendingConfirm,
    setError,
    setLiveStatus,
  })
  useNewChatReset(newChatNonce, abortRef, clearLocal)

  const cancel = useCancelAssistant(abortRef, setMessages, setSending, setLiveStatus)

  const onClientAction = useCallback(
    (action: ClientAction) => applyClientAction(action, pathname, navigate, setTheme),
    [navigate, pathname, setTheme],
  )

  const { send, sendText, resolveConfirm } = useChatActions({
    conversationId,
    draft,
    setDraft,
    sending,
    setSending,
    pendingConfirm,
    setPendingConfirm,
    setMessages,
    setError,
    setQuotaResetsAt,
    setLiveStatus,
    setConversationId,
    abortRef,
    uiContext: uiContextPayload(uiContext),
    onClientAction,
  })

  return {
    messages,
    draft,
    setDraft,
    sending,
    ...feedback,
    pendingConfirm,
    send,
    sendText,
    resolveConfirm,
    cancel,
  }
}

function useAssistantNavigation() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  return [navigate, pathname] as const
}
