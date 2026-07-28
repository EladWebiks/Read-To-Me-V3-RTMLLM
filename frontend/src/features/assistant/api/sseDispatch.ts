import type { ChatStreamHandlers, ClientAction, ConfirmationPayload } from './chatTypes'

/** Parse one SSE event block into chat handlers. */
export function dispatchSseBlock(block: string, handlers: ChatStreamHandlers): void {
  const { event, data } = parseSseBlock(block)
  if (!data) return
  routeSseEvent(event, data, handlers)
}

function routeSseEvent(
  event: string,
  data: Record<string, unknown>,
  handlers: ChatStreamHandlers,
): void {
  if (event === 'meta' && typeof data.conversation_id === 'string') {
    handlers.onMeta(data.conversation_id)
    return
  }
  if (event === 'delta' && typeof data.text === 'string') {
    handlers.onDelta(data.text)
    return
  }
  if (event === 'step' && typeof data.label === 'string') {
    handlers.onStep?.(data.label)
    return
  }
  if (event === 'tool_result') {
    handlers.onToolResult?.({
      name: String(data.name ?? 'tool'),
      ok: Boolean(data.ok),
      summary: String(data.summary ?? ''),
      clientAction: parseClientAction(data.client_action),
    })
    return
  }
  if (event === 'confirmation_request') {
    handlers.onConfirmation?.(parseConfirmation(data))
    return
  }
  if (event === 'done') {
    handlers.onDone({
      messageId: String(data.message_id ?? ''),
      conversationId: String(data.conversation_id ?? ''),
      status: typeof data.status === 'string' ? data.status : undefined,
      callId: typeof data.call_id === 'string' ? data.call_id : undefined,
    })
    return
  }
  if (event === 'error') handlers.onError(String(data.detail ?? 'Chat error'))
}

function parseClientAction(raw: unknown): ClientAction | undefined {
  if (!raw || typeof raw !== 'object') return undefined
  const obj = raw as Record<string, unknown>
  const path = obj.path
  const label = obj.label
  const type = obj.type
  if (typeof path !== 'string' || typeof label !== 'string' || typeof type !== 'string') {
    return undefined
  }
  if (!path.startsWith('/')) return undefined
  return { type, path, label }
}

function parseSseBlock(block: string): {
  event: string
  data: Record<string, unknown> | null
} {
  const lines = block.split('\n')
  let event = 'message'
  const dataLines: string[] = []
  for (const line of lines) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
  }
  if (!dataLines.length) return { event, data: null }
  return { event, data: JSON.parse(dataLines.join('\n')) as Record<string, unknown> }
}

function parseConfirmation(data: Record<string, unknown>): ConfirmationPayload {
  const formRaw = data.form
  const form =
    formRaw && typeof formRaw === 'object'
      ? (formRaw as ConfirmationPayload['form'])
      : null
  return {
    callId: String(data.call_id ?? ''),
    tool: String(data.tool ?? ''),
    risk: String(data.risk ?? ''),
    summary: String(data.summary ?? 'Confirm action'),
    args: (data.args as Record<string, unknown>) ?? {},
    form,
    status: 'pending',
  }
}
