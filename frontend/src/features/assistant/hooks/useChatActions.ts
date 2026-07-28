import { useCallback } from 'react'
import {
  streamConfirmResolve,
  streamUserText,
  type ChatActionArgs,
} from './chatActionStreams'

export type { ChatActionArgs }

/** Send + confirm actions for the assistant chat hook. */
export function useChatActions(args: ChatActionArgs) {
  const sendText = useCallback(
    async (raw: string) => {
      const text = raw.trim()
      if (!text || args.sending || args.pendingConfirm) return
      await streamUserText(args, text)
    },
    [args],
  )

  const send = useCallback(async () => {
    const text = args.draft.trim()
    if (!text || args.sending || args.pendingConfirm) return
    args.setDraft('')
    await sendText(text)
  }, [args, sendText])

  const resolveConfirm = useCallback(
    async (approved: boolean, values?: Record<string, unknown>) => {
      if (!args.pendingConfirm || !args.conversationId || args.sending) return
      await streamConfirmResolve(args, approved, values)
    },
    [args],
  )

  return { send, sendText, resolveConfirm }
}
