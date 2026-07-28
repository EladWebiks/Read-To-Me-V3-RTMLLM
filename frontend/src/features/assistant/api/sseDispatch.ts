import type { ChatStreamHandlers } from './chatTypes'
import {
  parseChoice,
  parseClientAction,
  parseConfirmation,
  parseSseBlock,
} from './sseParse'

/** Parse one SSE event block into chat handlers. */
export function dispatchSseBlock(block: string, handlers: ChatStreamHandlers): void {
  const { event, data } = parseSseBlock(block)
  if (!data) return
  const handled =
    handleSimple(event, data, handlers) ||
    handleToolish(event, data, handlers) ||
    handleTerminal(event, data, handlers)
  if (!handled && event === 'error') {
    handlers.onError(String(data.detail ?? 'Chat error'))
  }
}

function handleSimple(
  event: string,
  data: Record<string, unknown>,
  handlers: ChatStreamHandlers,
): boolean {
  if (event === 'meta' && typeof data.conversation_id === 'string') {
    handlers.onMeta(data.conversation_id)
    return true
  }
  if (event === 'delta' && typeof data.text === 'string') {
    handlers.onDelta(data.text)
    return true
  }
  if (event === 'step' && typeof data.label === 'string') {
    handlers.onStep?.(data.label)
    return true
  }
  return false
}

function handleToolish(
  event: string,
  data: Record<string, unknown>,
  handlers: ChatStreamHandlers,
): boolean {
  if (event === 'tool_result') {
    handlers.onToolResult?.({
      name: String(data.name ?? 'tool'),
      ok: Boolean(data.ok),
      summary: String(data.summary ?? ''),
      clientAction: parseClientAction(data.client_action),
    })
    return true
  }
  if (event === 'confirmation_request') {
    handlers.onConfirmation?.(parseConfirmation(data))
    return true
  }
  if (event === 'choice_request') {
    const choice = parseChoice(data)
    if (choice) handlers.onChoiceRequest?.(choice)
    return true
  }
  return false
}

function handleTerminal(
  event: string,
  data: Record<string, unknown>,
  handlers: ChatStreamHandlers,
): boolean {
  if (event !== 'done') return false
  handlers.onDone({
    messageId: String(data.message_id ?? ''),
    conversationId: String(data.conversation_id ?? ''),
    status: typeof data.status === 'string' ? data.status : undefined,
    callId: typeof data.call_id === 'string' ? data.call_id : undefined,
  })
  return true
}
