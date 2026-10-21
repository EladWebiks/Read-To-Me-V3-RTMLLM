import { apiDelete, apiGet } from '@/shared/lib/api'
import type { ChatStreamHandlers, Conversation } from './chatTypes'
import { dispatchSseBlock } from './sseDispatch'

export type {
  ChatMessage,
  ChatRole,
  ChatStreamHandlers,
  ChoiceOption,
  ChoicePayload,
  ClientAction,
  ConfirmationFormField,
  ConfirmationPayload,
  Conversation,
  DonePayload,
} from './chatTypes'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

export function getConversation(conversationId: string): Promise<Conversation> {
  return apiGet<Conversation>(`/api/chat/${conversationId}`)
}

export type ConversationSummary = {
  id: string
  title: string | null
  updated_at: string
}

export type ConversationList = {
  items: ConversationSummary[]
  total: number
  limit: number
  offset: number
}

export function listConversations(limit = 50, offset = 0): Promise<ConversationList> {
  return apiGet<ConversationList>(`/api/chat?limit=${limit}&offset=${offset}`)
}

export function deleteConversation(conversationId: string): Promise<void> {
  return apiDelete(`/api/chat/${conversationId}`)
}

/** POST /api/chat and parse SSE events. */
export async function streamChat(
  message: string,
  conversationId: string | null,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
  uiContext?: { path: string; book_id?: string; chapter_id?: string },
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
      ui_context: uiContext ?? null,
    }),
    signal,
  })
  if (!response.ok || !response.body) {
    throw new Error(`Chat failed: ${response.status}`)
  }
  await readSse(response.body, handlers)
}

/** POST /api/chat/{id}/confirm — resume after HITL. */
export async function streamConfirm(
  conversationId: string,
  body: { callId: string; approved: boolean; values?: Record<string, unknown> },
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/chat/${conversationId}/confirm`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      call_id: body.callId,
      approved: body.approved,
      values: body.values ?? null,
    }),
    signal,
  })
  if (!response.ok || !response.body) {
    throw new Error(`Confirm failed: ${response.status}`)
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
    for (const block of parts) dispatchSseBlock(block, handlers)
  }
}
