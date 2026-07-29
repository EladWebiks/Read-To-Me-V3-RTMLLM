import type { ChatMessage } from '../api/chatApi'

/** Tool internals stay hidden; only actionable outcomes become durable cards. */
export function isVisibleToolMessage(message: ChatMessage): boolean {
  if (message.role !== 'tool') return true
  return Boolean(message.clientAction)
}
