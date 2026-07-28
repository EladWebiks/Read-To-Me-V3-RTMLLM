import type { Dispatch, SetStateAction } from 'react'
import type { ChatMessage, ClientAction, ConfirmationPayload } from '../api/chatApi'

export function appendToolResult(
  prev: ChatMessage[],
  assistantId: string,
  name: string,
  ok: boolean,
  summary: string,
  clientAction?: ClientAction,
): ChatMessage[] {
  const toolMsg: ChatMessage = {
    id: localId('tool'),
    role: 'tool',
    content: summary,
    toolName: name,
    toolOk: ok,
    clientAction,
  }
  const idx = prev.findIndex((m) => m.id === assistantId)
  if (idx === -1) return [...prev, toolMsg]
  const next = [...prev]
  next.splice(idx, 0, toolMsg)
  return next
}

export function appendConfirmation(
  prev: ChatMessage[],
  assistantId: string,
  payload: ConfirmationPayload,
): ChatMessage[] {
  const withoutEmpty = prev.filter(
    (m) => !(m.id === assistantId && m.role === 'assistant' && !m.content),
  )
  return [
    ...withoutEmpty,
    {
      id: payload.callId || localId('confirm'),
      role: 'confirmation',
      content: payload.summary,
      confirmation: payload,
    },
  ]
}

export function patchAssistant(
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>,
  assistantId: string,
  delta: string,
): void {
  setMessages((prev) => {
    if (!prev.some((m) => m.id === assistantId)) {
      return [...prev, { id: assistantId, role: 'assistant', content: delta }]
    }
    return prev.map((m) =>
      m.id === assistantId ? { ...m, content: m.content + delta } : m,
    )
  })
}

function localId(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`
}
