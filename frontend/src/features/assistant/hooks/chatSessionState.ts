import { useCallback, useState, type Dispatch, type SetStateAction } from 'react'
import type { ChatMessage, ConfirmationPayload } from '../api/chatApi'

/** Banner error, live status line, and the session-scoped quota lock. */
export function useChatFeedbackState() {
  const [error, setError] = useState<string | null>(null)
  const [liveStatus, setLiveStatus] = useState<string | null>(null)
  // Live quota refusal for this session; the composer lock also reads the
  // ['me','usage'] query so it survives a reload (derived in render).
  const [quotaResetsAt, setQuotaResetsAt] = useState<string | null>(null)
  return { error, setError, liveStatus, setLiveStatus, quotaResetsAt, setQuotaResetsAt }
}

type ClearDeps = {
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>
  setDraft: (value: string) => void
  setSending: (value: boolean) => void
  setError: (value: string | null) => void
  setLiveStatus: (value: string | null) => void
  setPendingConfirm: (value: ConfirmationPayload | null) => void
  sendingGateRef: { current: boolean }
}

/** Reset local chat state for a fresh thread. */
export function useClearLocalChat(deps: ClearDeps) {
  const {
    setMessages,
    setDraft,
    setSending,
    setError,
    setLiveStatus,
    setPendingConfirm,
    sendingGateRef,
  } = deps
  return useCallback(() => {
    sendingGateRef.current = false
    setMessages([])
    setDraft('')
    setError(null)
    setSending(false)
    setLiveStatus(null)
    setPendingConfirm(null)
  }, [
    sendingGateRef,
    setMessages,
    setDraft,
    setError,
    setSending,
    setLiveStatus,
    setPendingConfirm,
  ])
}

export function useCancelAssistant(
  abortRef: { current: AbortController | null },
  sendingGateRef: { current: boolean },
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>,
  setSending: (value: boolean) => void,
  setLiveStatus: (value: string | null) => void,
) {
  return useCallback(() => {
    if (!abortRef.current) return
    abortRef.current.abort()
    abortRef.current = null
    sendingGateRef.current = false
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
  }, [abortRef, sendingGateRef, setLiveStatus, setMessages, setSending])
}
