import { useEffect, useRef, type Dispatch, type SetStateAction } from 'react'
import { getConversation, type ChatMessage } from '../api/chatApi'
import { useAssistantStore } from '../assistantStore'

/** Load persisted conversation once on mount. */
export function useHydrateConversation(
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>,
  setConversationId: (id: string | null) => void,
): void {
  const hydratedRef = useRef(false)
  useEffect(() => {
    if (hydratedRef.current) return
    hydratedRef.current = true
    const id = useAssistantStore.getState().conversationId
    if (!id) return
    let cancelled = false
    void getConversation(id)
      .then((conv) => {
        if (!cancelled) setMessages(conv.messages)
      })
      .catch(() => {
        if (!cancelled) setConversationId(null)
      })
    return () => {
      cancelled = true
    }
  }, [setConversationId, setMessages])
}

/** Clear local chat when header requests a new thread. */
export function useNewChatReset(
  newChatNonce: number,
  abortRef: { current: AbortController | null },
  clear: () => void,
): void {
  const seenNonceRef = useRef(newChatNonce)
  useEffect(() => {
    if (newChatNonce === seenNonceRef.current) return
    seenNonceRef.current = newChatNonce
    abortRef.current?.abort()
    clear()
  }, [abortRef, clear, newChatNonce])
}
