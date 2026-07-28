import { streamChat, streamConfirm, type ConfirmationPayload } from '../api/chatApi'
import { buildStreamHandlers, type StreamArgs } from './streamHandlers'

/** Run one SSE chat turn and update local message state. */
export async function runAssistantStream(
  args: StreamArgs & {
    text: string
    uiContext?: { path: string; book_id?: string; chapter_id?: string }
  },
  onAwaitingConfirm?: (payload: ConfirmationPayload) => void,
): Promise<void> {
  const controller = new AbortController()
  args.abortRef.current = controller
  try {
    await streamChat(
      args.text,
      args.conversationId,
      buildStreamHandlers(args, onAwaitingConfirm),
      controller.signal,
      args.uiContext,
    )
  } catch (err) {
    if (!controller.signal.aborted) {
      args.setError(err instanceof Error ? err.message : 'Chat failed')
    }
  } finally {
    args.abortRef.current = null
  }
}

/** Resume a paused turn after HITL OK/Cancel. */
export async function runConfirmStream(
  args: StreamArgs & {
    conversationId: string
    callId: string
    approved: boolean
    values?: Record<string, unknown>
  },
): Promise<void> {
  const controller = new AbortController()
  args.abortRef.current = controller
  try {
    await streamConfirm(
      args.conversationId,
      { callId: args.callId, approved: args.approved, values: args.values },
      buildStreamHandlers(args),
      controller.signal,
    )
  } catch (err) {
    if (!controller.signal.aborted) {
      args.setError(err instanceof Error ? err.message : 'Confirm failed')
    }
  } finally {
    args.abortRef.current = null
  }
}
