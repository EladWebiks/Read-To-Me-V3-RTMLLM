import { apiGet } from '@/shared/lib/api'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

export type ChatRole = 'user' | 'assistant' | 'system'

export type ChatMessage = {
  id: string
  role: ChatRole
  content: string
  created_at?: string
}

export type Conversation = {
  id: string
  title: string | null
  messages: ChatMessage[]
}

export type ChatStreamHandlers = {
  onMeta: (conversationId: string) => void
  onDelta: (text: string) => void
  onDone: (payload: { messageId: string; conversationId: string }) => void
  onError: (detail: string) => void
}

export function getConversation(conversationId: string): Promise<Conversation> {
  return apiGet<Conversation>(`/api/chat/${conversationId}`)
}

/** POST /api/chat and parse SSE events (meta / delta / done / error). */
export async function streamChat(
  message: string,
  conversationId: string | null,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
    }),
    signal,
  })
  if (!response.ok || !response.body) {
    throw new Error(`Chat failed: ${response.status}`)
  }
  await readSse(response.body, handlers)
}

async function readSse(
  body: ReadableStream<Uint8Array>,
  handlers: ChatStreamHandlers,
): Promise<void> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() ?? ''
    for (const block of parts) {
      dispatchSseBlock(block, handlers)
    }
  }
}

function dispatchSseBlock(block: string, handlers: ChatStreamHandlers): void {
  const lines = block.split('\n')
  let event = 'message'
  const dataLines: string[] = []
  for (const line of lines) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
  }
  if (!dataLines.length) return
  const data = JSON.parse(dataLines.join('\n')) as Record<string, unknown>
  if (event === 'meta' && typeof data.conversation_id === 'string') {
    handlers.onMeta(data.conversation_id)
  } else if (event === 'delta' && typeof data.text === 'string') {
    handlers.onDelta(data.text)
  } else if (event === 'done') {
    handlers.onDone({
      messageId: String(data.message_id ?? ''),
      conversationId: String(data.conversation_id ?? ''),
    })
  } else if (event === 'error') {
    handlers.onError(String(data.detail ?? 'Chat error'))
  }
}
