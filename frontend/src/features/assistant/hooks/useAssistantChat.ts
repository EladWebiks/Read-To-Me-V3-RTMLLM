import { useCallback, useState, type Dispatch, type SetStateAction } from 'react'
import { useTheme } from 'next-themes'
import { useLocation, useNavigate } from 'react-router'
import type { ChatMessage, ClientAction, ConfirmationPayload } from '../api/chatApi'
import { useAssistantStore } from '../assistantStore'
import { useHydrateConversation, useNewChatReset } from './chatLifecycle'
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
  const [error, setError] = useState<string | null>(null)
  const [liveStatus, setLiveStatus] = useState<string | null>(null)
  const [pendingConfirm, setPendingConfirm] = useState<ConfirmationPayload | null>(null)
  const [abortRef] = useState(() => ({ current: null as AbortController | null }))

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
    error,
    liveStatus,
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

function useCancelAssistant(
  abortRef: { current: AbortController | null },
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>,
  setSending: (value: boolean) => void,
  setLiveStatus: (value: string | null) => void,
) {
  return useCallback(() => {
    if (!abortRef.current) return
    abortRef.current.abort()
    abortRef.current = null
    setSending(false)
    setLiveStatus(null)
    setMessages((prev) => [
      ...prev,
      {
        id: `cancelled-${crypto.randomUUID()}`,
        role: 'cancelled',
        content: 'Response canceled.',
      },
    ])
  }, [abortRef, setLiveStatus, setMessages, setSending])
}
