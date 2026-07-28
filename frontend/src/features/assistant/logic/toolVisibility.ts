import type { ChatMessage } from '../api/chatApi'

/** Durable tool cards only when the user needs an outcome chip or an error. */
export function isVisibleToolMessage(message: ChatMessage): boolean {
  if (message.role !== 'tool') return true
  if (message.toolName === 'propose_choices') return false
  if (message.toolOk === false) return true
  return Boolean(message.clientAction)
}
