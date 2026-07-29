import type { Dispatch, MutableRefObject, SetStateAction } from 'react'
import type { ChatMessage, ClientAction, ConfirmationPayload } from '../api/chatApi'
import { markConfirmStatus } from './confirmHelpers'
import { runAssistantStream, runConfirmStream } from './runAssistantStream'

export type ChatActionArgs = {
  conversationId: string | null
  draft: string
  setDraft: (v: string) => void
  sending: boolean
  setSending: (v: boolean) => void
  pendingConfirm: ConfirmationPayload | null
  setPendingConfirm: (v: ConfirmationPayload | null) => void
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>
  setError: (v: string | null) => void
  setLiveStatus: (v: string | null) => void
  setConversationId: (id: string | null) => void
  abortRef: MutableRefObject<AbortController | null>
  uiContext: { path: string; book_id?: string; chapter_id?: string }
  onClientAction?: (action: ClientAction) => void
}

function localId(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`
}

/** Stream a user text turn. */
export async function streamUserText(args: ChatActionArgs, text: string): Promise<void> {
  args.setError(null)
  args.setLiveStatus('Thinking…')
  args.setSending(true)
  const assistantId = localId('assistant')
  args.setMessages((prev) => [
    ...prev,
    { id: localId('user'), role: 'user', content: text },
  ])
  await runAssistantStream(
    {
      text,
      conversationId: args.conversationId,
      assistantId,
      setConversationId: args.setConversationId,
      setMessages: args.setMessages,
      setError: args.setError,
      setLiveStatus: args.setLiveStatus,
      setSending: args.setSending,
      abortRef: args.abortRef,
      uiContext: args.uiContext,
      onClientAction: args.onClientAction,
    },
    (payload) => args.setPendingConfirm(payload),
  )
}

/** Resume after HITL OK/Cancel. */
export async function streamConfirmResolve(
  args: ChatActionArgs,
  approved: boolean,
  values?: Record<string, unknown>,
): Promise<void> {
  if (!args.pendingConfirm || !args.conversationId) return
  const callId = args.pendingConfirm.callId
  args.setPendingConfirm(null)
  args.setLiveStatus('Thinking…')
  args.setSending(true)
  args.setError(null)
  markConfirmStatus(args.setMessages, callId, approved ? 'approved' : 'rejected')
  const assistantId = localId('assistant')
  await runConfirmStream({
    conversationId: args.conversationId,
    callId,
    approved,
    values,
    assistantId,
    setConversationId: args.setConversationId,
    setMessages: args.setMessages,
    setError: args.setError,
    setLiveStatus: args.setLiveStatus,
    setSending: args.setSending,
    abortRef: args.abortRef,
    onClientAction: args.onClientAction,
  })
}
