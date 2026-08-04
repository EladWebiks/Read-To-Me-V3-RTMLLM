import { useCallback, type Dispatch, type SetStateAction } from 'react'
import {
  getConversation,
  type ChatMessage,
  type ConfirmationPayload,
} from '../api/chatApi'

type LoadDeps = {
  abortRef: { current: AbortController | null }
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>
  setConversationId: (id: string | null) => void
  setDraft: (value: string) => void
  setSending: (value: boolean) => void
  setPendingConfirm: (value: ConfirmationPayload | null) => void
  setError: (value: string | null) => void
  setLiveStatus: (value: string | null) => void
  setLoadingHistory: (value: boolean) => void
}

/** Load a past conversation into the open chat panel. */
export function useLoadConversation(deps: LoadDeps) {
  const {
    abortRef,
    setMessages,
    setConversationId,
    setDraft,
    setSending,
    setPendingConfirm,
    setError,
    setLiveStatus,
    setLoadingHistory,
  } = deps
  return useCallback(
    async (conversationId: string) => {
      abortRef.current?.abort()
      abortRef.current = null
      setLoadingHistory(true)
      setError(null)
      setLiveStatus(null)
      setSending(false)
      setPendingConfirm(null)
      setDraft('')
      try {
        const conv = await getConversation(conversationId)
        setConversationId(conv.id)
        setMessages(conv.messages)
      } catch (err) {
        setError("Couldn't load that conversation.")
        throw err
      } finally {
        setLoadingHistory(false)
      }
    },
    [
      abortRef,
      setConversationId,
      setDraft,
      setError,
      setLiveStatus,
      setLoadingHistory,
      setMessages,
      setPendingConfirm,
      setSending,
    ],
  )
}
