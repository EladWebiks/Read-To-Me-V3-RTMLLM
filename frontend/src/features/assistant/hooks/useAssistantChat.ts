import { useCallback } from 'react'
import type { ClientAction } from '../api/chatApi'
import { applyClientAction } from './clientActions'
import { useChatActions } from './useChatActions'
import { useLoadConversation } from './useLoadConversation'
import { uiContextPayload } from './useUiContext'
import { useAssistantChatSession } from './useAssistantChatSession'

/** Local chat state + SSE streaming (tools + HITL). */
export function useAssistantChat() {
  const session = useAssistantChatSession()
  const loadConversation = useLoadConversation({
    abortRef: session.abortRef,
    setMessages: session.setMessages,
    setConversationId: session.setConversationId,
    setDraft: session.setDraft,
    setSending: session.setSending,
    setPendingConfirm: session.setPendingConfirm,
    setError: session.feedback.setError,
    setLiveStatus: session.feedback.setLiveStatus,
    setLoadingHistory: session.setLoadingHistory,
  })

  const onClientAction = useCallback(
    (action: ClientAction) =>
      applyClientAction(action, session.pathname, session.navigate, session.setTheme),
    [session.navigate, session.pathname, session.setTheme],
  )

  const { send, sendText, resolveConfirm } = useChatActions({
    conversationId: session.conversationId,
    draft: session.draft,
    setDraft: session.setDraft,
    sending: session.sending,
    setSending: session.setSending,
    pendingConfirm: session.pendingConfirm,
    setPendingConfirm: session.setPendingConfirm,
    setMessages: session.setMessages,
    setError: session.feedback.setError,
    setQuotaResetsAt: session.feedback.setQuotaResetsAt,
    setLiveStatus: session.feedback.setLiveStatus,
    setConversationId: session.setConversationId,
    abortRef: session.abortRef,
    uiContext: uiContextPayload(session.uiContext),
    onClientAction,
  })

  return {
    messages: session.messages,
    draft: session.draft,
    setDraft: session.setDraft,
    sending: session.sending,
    loadingHistory: session.loadingHistory,
    loadConversation,
    ...session.feedback,
    pendingConfirm: session.pendingConfirm,
    send,
    sendText,
    resolveConfirm,
    cancel: session.cancel,
  }
}
