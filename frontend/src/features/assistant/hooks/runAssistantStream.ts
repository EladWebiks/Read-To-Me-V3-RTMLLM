import type { Dispatch, MutableRefObject, SetStateAction } from 'react'
import { streamChat, type ChatMessage } from '../api/chatApi'

type Args = {
  text: string
  conversationId: string | null
  assistantId: string
  setConversationId: (id: string | null) => void
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>
  setError: (detail: string | null) => void
  abortRef: MutableRefObject<AbortController | null>
}

/** Run one SSE chat turn and update local message state. */
export async function runAssistantStream(args: Args): Promise<void> {
  const {
    text,
    conversationId,
    assistantId,
    setConversationId,
    setMessages,
    setError,
    abortRef,
  } = args
  const controller = new AbortController()
  abortRef.current = controller
  try {
    await streamChat(
      text,
      conversationId,
      {
        onMeta: (id) => setConversationId(id),
        onDelta: (delta) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: m.content + delta } : m,
            ),
          )
        },
        onDone: ({ messageId }) => {
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, id: messageId } : m)),
          )
        },
        onError: (detail) => setError(detail),
      },
      controller.signal,
    )
  } catch (err) {
    if (!controller.signal.aborted) {
      setError(err instanceof Error ? err.message : 'Chat failed')
    }
  } finally {
    abortRef.current = null
  }
}
