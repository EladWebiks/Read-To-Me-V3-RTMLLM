import type { ChatMessage } from '../api/chatApi'
import { ConfirmationCard } from './ConfirmationCard'
import { AssistantProse, UserBubble } from './chatTurnParts'
import { ToolResultCard } from './ToolResultCard'

type Props = {
  message: ChatMessage
  streaming?: boolean
  confirmBusy?: boolean
  onResolveConfirm?: (approved: boolean, values?: Record<string, unknown>) => void
}

/** One chat turn — user bubbled; assistant prose; HITL / tool cards. */
export function ChatTurn({
  message,
  streaming = false,
  confirmBusy = false,
  onResolveConfirm,
}: Props) {
  if (message.role === 'user') return <UserBubble content={message.content} />
  if (message.role === 'confirmation' && message.confirmation) {
    return (
      <ConfirmationCard
        payload={message.confirmation}
        busy={confirmBusy}
        onResolve={onResolveConfirm ?? (() => undefined)}
      />
    )
  }
  if (message.role === 'tool') {
    return (
      <ToolResultCard
        name={message.toolName ?? 'tool'}
        ok={message.toolOk !== false}
        summary={message.content}
        clientAction={message.clientAction}
      />
    )
  }
  return <AssistantProse content={message.content} streaming={streaming} />
}
