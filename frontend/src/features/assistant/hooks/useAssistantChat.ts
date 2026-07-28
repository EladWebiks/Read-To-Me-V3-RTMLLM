import { useCallback, useRef, useState } from 'react'
import type { ChatMessage } from '../api/chatApi'
import { useAssistantStore } from '../assistantStore'
import { useHydrateConversation, useNewChatReset } from './chatLifecycle'
import { runAssistantStream } from './runAssistantStream'

function localId(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`
}

/** Local chat state + SSE streaming against /api/chat. */
export function useAssistantChat() {
  const conversationId = useAssistantStore((s) => s.conversationId)
  const setConversationId = useAssistantStore((s) => s.setConversationId)
  const newChatNonce = useAssistantStore((s) => s.newChatNonce)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  useHydrateConversation(setMessages, setConversationId)

  const clearLocal = useCallback(() => {
    setMessages([])
    setDraft('')
    setError(null)
    setSending(false)
  }, [])
  useNewChatReset(newChatNonce, abortRef, clearLocal)

  const send = useCallback(async () => {
    const text = draft.trim()
    if (!text || sending) return
    setDraft('')
    setError(null)
    setSending(true)
    const assistantId = localId('assistant')
    setMessages((prev) => [
      ...prev,
      { id: localId('user'), role: 'user', content: text },
      { id: assistantId, role: 'assistant', content: '' },
    ])
    await runAssistantStream({
      text,
      conversationId,
      assistantId,
      setConversationId,
      setMessages,
      setError,
      abortRef,
    })
    setSending(false)
  }, [conversationId, draft, sending, setConversationId])

  return { messages, draft, setDraft, sending, error, send }
}
