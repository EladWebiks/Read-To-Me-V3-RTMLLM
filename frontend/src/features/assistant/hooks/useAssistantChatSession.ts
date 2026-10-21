import { useState } from 'react'
import { useTheme } from 'next-themes'
import { useLocation, useNavigate } from 'react-router'
import type { ChatMessage, ConfirmationPayload } from '../api/chatApi'
import { useAssistantStore } from '../assistantStore'
import { useHydrateConversation, useNewChatReset } from './chatLifecycle'
import {
  useCancelAssistant,
  useChatFeedbackState,
  useClearLocalChat,
} from './chatSessionState'
import { useUiContext } from './useUiContext'

/** Shared local state for the open assistant chat panel. */
export function useAssistantChatSession() {
  const conversationId = useAssistantStore((s) => s.conversationId)
  const setConversationId = useAssistantStore((s) => s.setConversationId)
  const newChatNonce = useAssistantStore((s) => s.newChatNonce)
  const uiContext = useUiContext()
  const { setTheme } = useTheme()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const feedback = useChatFeedbackState()
  const [pendingConfirm, setPendingConfirm] = useState<ConfirmationPayload | null>(null)
  const [abortRef] = useState(() => ({ current: null as AbortController | null }))
  const [sendingGateRef] = useState(() => ({ current: false }))

  useHydrateConversation(setMessages, setConversationId)
  const clearLocal = useClearLocalChat({
    setMessages,
    setDraft,
    setSending,
    setPendingConfirm,
    setError: feedback.setError,
    setLiveStatus: feedback.setLiveStatus,
    sendingGateRef,
  })
  useNewChatReset(newChatNonce, abortRef, clearLocal)
  const cancel = useCancelAssistant(
    abortRef,
    sendingGateRef,
    setMessages,
    setSending,
    feedback.setLiveStatus,
  )

  return {
    conversationId,
    setConversationId,
    uiContext,
    setTheme,
    navigate,
    pathname,
    messages,
    setMessages,
    draft,
    setDraft,
    sending,
    setSending,
    loadingHistory,
    setLoadingHistory,
    feedback,
    pendingConfirm,
    setPendingConfirm,
    abortRef,
    sendingGateRef,
    cancel,
  }
}
